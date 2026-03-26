"""Standalone queued preview renderer for Render Composition.

This module intentionally avoids QWidget/QTimer dependencies so it can be
tested as a renderer in isolation. The UI submits preview-frame requests and
receives resolved image layers back through a callback.
"""
from __future__ import annotations

from dataclasses import dataclass
import logging
import queue
import shutil
import subprocess
import threading
from typing import Callable

from PySide6.QtGui import QImage

from audio_visualizer.ui.tabs.renderComposition.evaluation import (
    evaluate_visual_layer,
)
from audio_visualizer.ui.tabs.renderComposition.matte import apply_matte_to_image
from audio_visualizer.ui.tabs.renderComposition.model import CompositionLayer

logger = logging.getLogger(__name__)

try:
    import av
except ImportError:
    av = None  # type: ignore[assignment]


@dataclass(slots=True)
class PreviewRenderRequest:
    token: object
    position_ms: int
    output_width: int
    output_height: int
    layers: list[dict]


@dataclass(slots=True)
class PreviewRenderResult:
    token: object
    position_ms: int
    composed_layers: list[dict]
    layer_images: dict[str, QImage]


_PYAV_PREVIEW_DECODE_LOCK = threading.Lock()


def _layer_source_position_ms(layer: dict, composition_ms: int) -> int | None:
    cl = CompositionLayer(
        start_ms=int(layer.get("start_ms", 0)),
        end_ms=int(layer.get("end_ms", 0)),
        source_duration_ms=int(layer.get("source_duration_ms", 0)),
        behavior_after_end=layer.get("behavior_after_end", "hide"),
    )
    result = evaluate_visual_layer(cl, composition_ms)
    return result.source_time_ms


def _layer_to_composed_entry(
    layer: dict,
    image: QImage,
    *,
    output_width: int,
    output_height: int,
) -> dict:
    layer_width = layer.get("width", image.width())
    layer_height = layer.get("height", image.height())
    center_x = layer.get("center_x", 0)
    center_y = layer.get("center_y", 0)
    return {
        "id": layer.get("id", ""),
        "qimage": image,
        "x": (output_width / 2) + center_x - (layer_width / 2),
        "y": (output_height / 2) + center_y - (layer_height / 2),
        "w": layer_width,
        "h": layer_height,
        "z_order": layer.get("z_order", 0),
        "opacity": layer.get("opacity", 1.0),
    }


def _decode_frame_via_ffmpeg(source_path: str, source_ms: int) -> QImage | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not source_path:
        return None
    seconds = max(0.0, source_ms / 1000.0)
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        source_path,
        "-ss",
        f"{seconds:.3f}",
        "-frames:v",
        "1",
        "-f",
        "image2pipe",
        "-vcodec",
        "png",
        "-",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except Exception:
        logger.exception(
            "Standalone preview FFmpeg decode failed for %s at %d ms.",
            source_path,
            source_ms,
        )
        return None
    if result.returncode != 0 or not result.stdout:
        logger.warning(
            "Standalone preview FFmpeg decode returned %d for %s at %d ms: %s",
            result.returncode,
            source_path,
            source_ms,
            (result.stderr or b"").decode("utf-8", errors="replace").strip(),
        )
        return None
    image = QImage.fromData(result.stdout, "PNG")
    return image if not image.isNull() else None


def _decode_frame_via_pyav(source_path: str, source_ms: int) -> QImage | None:
    if av is None or not source_path:
        return None
    with _PYAV_PREVIEW_DECODE_LOCK:
        container = None
        try:
            container = av.open(source_path)
            video_stream = next(
                (stream for stream in container.streams if stream.type == "video"),
                None,
            )
            if video_stream is None:
                return None
            if source_ms > 0:
                container.seek(int(source_ms * 1000), stream=video_stream, backward=True)

            best_image: QImage | None = None
            for frame in container.decode(video_stream):
                pts_ms = (
                    int(frame.pts * float(frame.time_base) * 1000)
                    if frame.pts is not None
                    else 0
                )
                best_image = _frame_to_qimage(frame)
                if pts_ms >= source_ms:
                    break
            return best_image
        except Exception:
            logger.exception(
                "Standalone preview PyAV decode failed for %s at %d ms.",
                source_path,
                source_ms,
            )
            return None
        finally:
            if container is not None:
                try:
                    container.close()
                except Exception:
                    logger.debug(
                        "Standalone preview PyAV container close failed for %s.",
                        source_path,
                        exc_info=True,
                    )


def _frame_to_qimage(frame) -> QImage | None:
    try:
        rgba_frame = frame.reformat(format="rgba")
        arr = rgba_frame.to_ndarray()
        height, width, _ = arr.shape
        return QImage(
            arr.tobytes(),
            width,
            height,
            width * 4,
            QImage.Format.Format_RGBA8888,
        ).copy()
    except Exception:
        logger.debug("Standalone preview frame conversion failed.", exc_info=True)
        return None


def decode_video_frame(source_path: str, source_ms: int) -> QImage | None:
    image = _decode_frame_via_ffmpeg(source_path, source_ms)
    if image is not None:
        return image
    return _decode_frame_via_pyav(source_path, source_ms)


def render_preview_request(request: PreviewRenderRequest) -> PreviewRenderResult:
    composed_layers: list[dict] = []
    layer_images: dict[str, QImage] = {}
    for layer in request.layers:
        if not layer.get("enabled", True):
            continue
        source_ms = _layer_source_position_ms(layer, request.position_ms)
        if source_ms is None:
            continue

        layer_id = layer.get("id", "")
        image: QImage | None
        if layer.get("source_kind") == "image":
            image = QImage(layer.get("path", ""))
            if image.isNull():
                image = None
        else:
            image = decode_video_frame(layer.get("path", ""), source_ms)
        if image is None or image.isNull():
            continue
        image = apply_matte_to_image(image, layer.get("matte_settings"))
        if image is None or image.isNull():
            continue

        layer_images[layer_id] = image
        composed_layers.append(
            _layer_to_composed_entry(
                layer,
                image,
                output_width=request.output_width,
                output_height=request.output_height,
            )
        )

    return PreviewRenderResult(
        token=request.token,
        position_ms=request.position_ms,
        composed_layers=composed_layers,
        layer_images=layer_images,
    )


class StandalonePreviewRenderer:
    """FIFO preview renderer that runs requests off the GUI thread."""

    def __init__(
        self,
        on_result: Callable[[PreviewRenderResult], None] | None = None,
    ) -> None:
        self._on_result = on_result
        self._queue: queue.Queue[PreviewRenderRequest | None] = queue.Queue()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="RenderCompositionPreview",
        )
        self._thread.start()

    def submit(self, request: PreviewRenderRequest) -> None:
        self._queue.put(request)

    def close(self) -> None:
        self._stop_event.set()
        self._queue.put(None)
        self._thread.join(timeout=1.0)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            request = self._queue.get()
            if request is None:
                return
            result = render_preview_request(request)
            if self._on_result is not None:
                self._on_result(result)
