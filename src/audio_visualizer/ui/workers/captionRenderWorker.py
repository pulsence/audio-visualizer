"""Caption Render worker — cancellable FFmpeg-based subtitle rendering.

Wraps render_subtitle() from captionApi in a QRunnable, forwarding
progress via AppEventEmitter + WorkerBridge.  Supports cancellation
by terminating the FFmpeg subprocess.
"""
from __future__ import annotations

import logging
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QRunnable

from audio_visualizer.events import AppEvent, AppEventEmitter, EventLevel, EventType
from audio_visualizer.caption.captionApi import RenderConfig, RenderResult, render_subtitle
from audio_visualizer.caption.core.config import PresetConfig
from audio_visualizer.ui.workers.workerBridge import WorkerBridge, WorkerSignals

logger = logging.getLogger(__name__)


@dataclass
class CaptionRenderJobSpec:
    """Parameters for a single caption render job."""

    subtitle_path: Path
    output_path: Path
    config: RenderConfig
    preset_override: Optional[PresetConfig] = None
    audio_path: Optional[Path] = None
    delivery_output_path: Optional[Path] = None
    delivery_audio_path: Optional[Path] = None


class CaptionRenderWorker(QRunnable):
    """QRunnable that renders a caption overlay video.

    Wraps the caption package's render_subtitle() call, providing
    progress forwarding via WorkerBridge and cancellation support
    by capturing and terminating the FFmpeg subprocess.

    Parameters
    ----------
    spec:
        Job specification with paths and config.
    emitter:
        Shared event emitter for progress reporting.
    """

    def __init__(
        self,
        spec: CaptionRenderJobSpec,
        emitter: AppEventEmitter,
    ) -> None:
        super().__init__()
        self.setAutoDelete(True)

        self._spec = spec
        self._emitter = emitter
        self._cancel_flag = threading.Event()
        self.signals = WorkerSignals()
        self._bridge = WorkerBridge(emitter, self.signals)
        self._captured_process: Optional[subprocess.Popen] = None

    # ------------------------------------------------------------------
    # Cancel support
    # ------------------------------------------------------------------

    def cancel(self) -> None:
        """Request cancellation. Terminates the FFmpeg subprocess if running."""
        self._cancel_flag.set()
        proc = self._captured_process
        if proc is not None:
            try:
                proc.terminate()
                logger.info("Terminated FFmpeg subprocess (pid=%s)", proc.pid)
            except OSError:
                pass

    @property
    def is_canceled(self) -> bool:
        """Return True if cancel has been requested."""
        return self._cancel_flag.is_set()

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Execute the caption render on the thread-pool thread."""
        self._bridge.attach()

        try:
            if self._cancel_flag.is_set():
                self.signals.canceled.emit("Cancelled before start")
                return

            self._emitter.emit(AppEvent(
                event_type=EventType.STAGE,
                message="Starting caption render",
                data={"stage_number": 0, "total_stages": 1},
            ))

            # Monkey-patch subprocess.Popen to capture the process handle
            original_popen = subprocess.Popen
            worker = self

            class _CapturingPopen(subprocess.Popen):
                def __init__(self_proc, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    worker._captured_process = self_proc

            subprocess.Popen = _CapturingPopen  # type: ignore[misc]

            try:
                result = render_subtitle(
                    input_path=self._spec.subtitle_path,
                    output_path=self._spec.output_path,
                    config=self._spec.config,
                    emitter=self._emitter,
                    preset_override=self._spec.preset_override,
                )
            finally:
                subprocess.Popen = original_popen  # type: ignore[misc]
                self._captured_process = None

            # Check cancel after render
            if self._cancel_flag.is_set():
                # Clean up partial output
                if self._spec.output_path.exists():
                    try:
                        self._spec.output_path.unlink()
                    except OSError:
                        pass
                self.signals.canceled.emit("Cancelled during render")
                return

            if result.success:
                delivery_path = self._spec.delivery_output_path or result.output_path
                if delivery_path is None:
                    raise RuntimeError("Caption render did not produce an output path.")

                if (
                    self._spec.delivery_output_path is not None
                    or self._spec.delivery_audio_path is not None
                ):
                    self._create_delivery_output(
                        overlay_path=result.output_path,
                        delivery_path=delivery_path,
                        audio_path=self._spec.delivery_audio_path,
                    )

                self.signals.completed.emit({
                    "output_path": str(delivery_path),
                    "delivery_path": str(delivery_path),
                    "overlay_path": str(result.output_path),
                    "width": result.width,
                    "height": result.height,
                    "duration_ms": result.duration_ms,
                    "quality": self._spec.config.quality,
                    "has_alpha": self._spec.config.quality != "medium",
                    "overlay_has_alpha": self._spec.config.quality != "medium",
                    "delivery_has_audio": self._spec.delivery_audio_path is not None,
                })
            else:
                self.signals.failed.emit(
                    result.error or "Unknown render error",
                    {"detail": result.error},
                )

        except Exception as exc:
            if self._cancel_flag.is_set():
                for path in (self._spec.output_path, self._spec.delivery_output_path):
                    if path and path.exists():
                        path.unlink(missing_ok=True)
                self.signals.canceled.emit("Cancelled during render")
            else:
                logger.exception("CaptionRenderWorker failed: %s", exc)
                self.signals.failed.emit(str(exc), {"detail": str(exc)})

        finally:
            self._bridge.detach()

    def _create_delivery_output(
        self,
        overlay_path: Path,
        delivery_path: Path,
        audio_path: Optional[Path],
    ) -> None:
        """Create the user-facing MP4 delivery artifact from the overlay render."""
        if self._cancel_flag.is_set():
            raise RuntimeError("Cancelled during render")

        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(overlay_path),
        ]
        if audio_path is not None:
            ffmpeg_cmd.extend(["-i", str(audio_path)])

        ffmpeg_cmd.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
            ]
        )
        if audio_path is not None:
            ffmpeg_cmd.extend(
                [
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-shortest",
                ]
            )
        else:
            ffmpeg_cmd.append("-an")

        ffmpeg_cmd.extend(
            [
                "-movflags",
                "+faststart",
                str(delivery_path),
            ]
        )

        self._emitter.emit(
            AppEvent(
                event_type=EventType.STAGE,
                message="Preparing delivery MP4",
                data={"stage_number": 1, "total_stages": 2},
            )
        )

        proc = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self._captured_process = proc
        _stdout, stderr = proc.communicate()
        self._captured_process = None

        if self._cancel_flag.is_set():
            if delivery_path.exists():
                delivery_path.unlink(missing_ok=True)
            raise RuntimeError("Cancelled during render")

        if proc.returncode != 0:
            if delivery_path.exists():
                delivery_path.unlink(missing_ok=True)
            detail = (stderr or "").strip()[-500:]
            raise RuntimeError(
                f"Failed to create MP4 delivery output: {detail or 'ffmpeg exited with an error.'}"
            )
