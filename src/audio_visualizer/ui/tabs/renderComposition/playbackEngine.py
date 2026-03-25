"""Real-time GPU-composited playback engine for Render Composition.

Provides :class:`PlaybackEngine` — the coordinator that manages video
decode workers, audio decode/mixing/playback, and an OpenGL compositor
widget — and :class:`CompositorWidget` — a ``QOpenGLWidget`` that
composites decoded video frames into layered output.

The engine falls back gracefully when OpenGL or sounddevice are
unavailable.  Tests can instantiate the engine with
``allow_audio=False`` to avoid requiring a physical audio device.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any

import numpy as np

from PySide6.QtCore import QObject, QTimer, Signal, Qt, QRect, QRectF
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtWidgets import QWidget

from audio_visualizer.ui.tabs.renderComposition.evaluation import (
    evaluate_visual_layer,
    evaluate_audio_layer,
)
from audio_visualizer.ui.tabs.renderComposition.model import (
    CompositionAudioLayer,
    CompositionLayer,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional imports gated through capabilities
# ---------------------------------------------------------------------------

_HAS_OPENGL_WIDGET = False
_HAS_OPENGL_BLITTER = False
_HAS_SOUNDDEVICE = False
_HAS_PYAV = False

try:
    from PySide6.QtOpenGLWidgets import QOpenGLWidget

    _HAS_OPENGL_WIDGET = True
except ImportError:
    QOpenGLWidget = None  # type: ignore[assignment,misc]

try:
    from PySide6.QtOpenGL import QOpenGLTexture, QOpenGLTextureBlitter

    _HAS_OPENGL_BLITTER = True
except ImportError:
    QOpenGLTexture = None  # type: ignore[assignment,misc]
    QOpenGLTextureBlitter = None  # type: ignore[assignment,misc]

try:
    import sounddevice as sd

    _HAS_SOUNDDEVICE = True
except ImportError:
    sd = None  # type: ignore[assignment]

try:
    import av

    _HAS_PYAV = True
except ImportError:
    av = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_FRAME_QUEUE = 4
_AUDIO_BLOCK_SIZE = 1024
_AUDIO_SAMPLE_RATE = 44100
_AUDIO_CHANNELS = 2
_DISPLAY_FPS = 30
_MAX_FRAME_HISTORY = 12
_OPENGL_COLOR_BUFFER_BIT = 0x00004000
_OPENGL_BLEND = 0x0BE2
_OPENGL_SRC_ALPHA = 0x0302
_OPENGL_ONE_MINUS_SRC_ALPHA = 0x0303


# ---------------------------------------------------------------------------
# Video decode worker
# ---------------------------------------------------------------------------


class _VideoDecodeWorker(threading.Thread):
    """Decode video frames for a single layer using PyAV.

    Decoded frames are pushed to a bounded queue as (pts_ms, QImage) tuples.
    """

    def __init__(
        self,
        source_path: str,
        frame_queue: queue.Queue,
        start_source_ms: int = 0,
        *,
        layer_id: str = "",
    ) -> None:
        super().__init__(daemon=True, name=f"VideoDecode-{layer_id[:8]}")
        self.source_path = source_path
        self.frame_queue = frame_queue
        self.start_source_ms = start_source_ms
        self.layer_id = layer_id

        self._stop_event = threading.Event()
        self._seek_event = threading.Event()
        self._seek_ms: int = 0
        self._lock = threading.Lock()

    def run(self) -> None:
        if av is None:
            return
        try:
            container = av.open(self.source_path)
            video_stream = None
            for s in container.streams:
                if s.type == "video":
                    video_stream = s
                    break
            if video_stream is None:
                container.close()
                return

            # Seek to the initial source-time offset for this layer.
            if self.start_source_ms > 0:
                container.seek(
                    int(self.start_source_ms * 1000),
                    stream=video_stream,
                    backward=True,
                )

            for frame in container.decode(video_stream):
                if self._stop_event.is_set():
                    break

                # Handle pending seek
                if self._seek_event.is_set():
                    with self._lock:
                        seek_ms = self._seek_ms
                        self._seek_event.clear()
                    # Flush queue
                    while not self.frame_queue.empty():
                        try:
                            self.frame_queue.get_nowait()
                        except queue.Empty:
                            break
                    container.seek(int(seek_ms * 1000), stream=video_stream, backward=True)
                    continue

                pts_ms = int(frame.pts * float(frame.time_base) * 1000) if frame.pts is not None else 0
                img = self._frame_to_qimage(frame)
                if img is not None:
                    try:
                        self.frame_queue.put((pts_ms, img), timeout=0.5)
                    except queue.Full:
                        pass  # drop frame if consumer is slow

            container.close()
        except Exception:
            logger.debug("Video decode worker failed for %s", self.source_path, exc_info=True)

    def seek(self, ms: int) -> None:
        with self._lock:
            self._seek_ms = ms
            self._seek_event.set()

    def stop(self) -> None:
        self._stop_event.set()

    @staticmethod
    def _frame_to_qimage(frame) -> QImage | None:
        try:
            rgba_frame = frame.reformat(format="rgba")
            arr = rgba_frame.to_ndarray()
            h, w, _ = arr.shape
            return QImage(
                arr.tobytes(), w, h, w * 4, QImage.Format.Format_RGBA8888
            ).copy()
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Audio decode and playback
# ---------------------------------------------------------------------------


class _AudioPlayer:
    """Manages audio decode and sounddevice playback.

    Acts as the master clock: call :meth:`current_ms` to read the
    authoritative playback position.
    """

    def __init__(self, audio_layers: list[dict], *, allow_device: bool = True) -> None:
        self._layers = audio_layers  # list of dicts with path, start_ms, volume, muted, duration_ms
        self._allow_device = allow_device and _HAS_SOUNDDEVICE
        self._stream: Any | None = None

        self._lock = threading.Lock()
        self._position_ms: float = 0.0
        self._playing = False
        self._decoded_audio: dict[str, np.ndarray] = {}
        self._sample_rate = _AUDIO_SAMPLE_RATE
        self._channels = _AUDIO_CHANNELS
        self._clock_started_at: float | None = None
        self._clock_base_ms: float = 0.0

        # Pre-decode all audio layers
        self._decode_all()

    def _decode_all(self) -> None:
        """Pre-decode all audio layers into numpy arrays."""
        if av is None:
            return
        for layer_info in self._layers:
            path = layer_info.get("path")
            if not path:
                continue
            layer_id = layer_info.get("id", path)
            try:
                container = av.open(path)
                audio_stream = None
                for s in container.streams:
                    if s.type == "audio":
                        audio_stream = s
                        break
                if audio_stream is None:
                    container.close()
                    continue

                resampler = av.AudioResampler(
                    format="flt",
                    layout="stereo",
                    rate=self._sample_rate,
                )

                chunks: list[np.ndarray] = []
                for frame in container.decode(audio_stream):
                    resampled = resampler.resample(frame)
                    for rf in resampled:
                        arr = rf.to_ndarray()
                        if arr.ndim == 2:
                            arr = arr.T  # shape (samples, channels)
                        chunks.append(arr.astype(np.float32))

                container.close()
                if chunks:
                    self._decoded_audio[layer_id] = np.concatenate(chunks)
            except Exception:
                logger.debug("Audio pre-decode failed for %s", path, exc_info=True)

    def start(self, position_ms: float = 0.0) -> None:
        with self._lock:
            self._position_ms = position_ms
            self._playing = True
            self._clock_base_ms = position_ms
            self._clock_started_at = time.monotonic()

        if not self._allow_device:
            return

        try:
            self._stream = sd.OutputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                blocksize=_AUDIO_BLOCK_SIZE,
                dtype="float32",
                callback=self._audio_callback,
            )
            self._stream.start()
        except Exception:
            logger.debug("sounddevice stream start failed", exc_info=True)
            self._stream = None

    def stop(self) -> None:
        current_ms = self.current_ms()
        with self._lock:
            self._playing = False
            self._position_ms = current_ms
            self._clock_base_ms = current_ms
            self._clock_started_at = None
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def seek(self, ms: float) -> None:
        with self._lock:
            self._position_ms = ms
            self._clock_base_ms = ms
            self._clock_started_at = time.monotonic()

    def current_ms(self) -> float:
        with self._lock:
            if self._playing and self._stream is None and self._clock_started_at is not None:
                elapsed_ms = (time.monotonic() - self._clock_started_at) * 1000.0
                return self._clock_base_ms + elapsed_ms
            return self._position_ms

    @property
    def playing(self) -> bool:
        with self._lock:
            return self._playing

    def _audio_callback(self, outdata: np.ndarray, frames: int, time_info: Any, status: Any) -> None:
        with self._lock:
            if not self._playing:
                outdata[:] = 0
                return
            pos_ms = self._position_ms

        mixed = np.zeros((frames, self._channels), dtype=np.float32)

        for layer_info in self._layers:
            if layer_info.get("muted", False):
                continue
            layer_id = layer_info.get("id", layer_info.get("path", ""))
            audio_data = self._decoded_audio.get(layer_id)
            if audio_data is None:
                continue

            volume = layer_info.get("volume", 1.0)

            # Use shared evaluation contract for activity check
            al = CompositionAudioLayer(
                start_ms=int(layer_info.get("start_ms", 0)),
                duration_ms=int(layer_info.get("duration_ms", 0)),
                use_full_length=int(layer_info.get("duration_ms", 0)) <= 0,
                source_duration_ms=int(layer_info.get("duration_ms", 0)),
            )
            ev = evaluate_audio_layer(al, int(pos_ms))
            if not ev.is_active or ev.source_time_ms is None:
                continue
            offset_ms = ev.source_time_ms

            sample_offset = int(offset_ms * self._sample_rate / 1000)
            if sample_offset >= len(audio_data):
                continue

            available = min(frames, len(audio_data) - sample_offset)
            if available <= 0:
                continue

            chunk = audio_data[sample_offset: sample_offset + available]
            if chunk.ndim == 1:
                chunk = np.column_stack([chunk, chunk])
            elif chunk.shape[1] == 1:
                chunk = np.column_stack([chunk[:, 0], chunk[:, 0]])

            mixed[:available] += chunk[:available] * volume

        # Clip to prevent distortion
        np.clip(mixed, -1.0, 1.0, out=mixed)
        outdata[:] = mixed

        # Advance position
        advance_ms = (frames / self._sample_rate) * 1000
        with self._lock:
            self._position_ms += advance_ms


# ---------------------------------------------------------------------------
# Compositor widget
# ---------------------------------------------------------------------------


_CompositorBase = QOpenGLWidget if _HAS_OPENGL_WIDGET else QWidget


class CompositorWidget(_CompositorBase):
    """Lightweight compositor that draws decoded frames as layered images.

    When Qt OpenGL support is available and ``use_opengl=True``, the widget
    uploads frames into ``QOpenGLTexture`` objects and composites them with
    ``QOpenGLTextureBlitter``. A QWidget/QPainter fallback remains available
    for environments that cannot host a valid OpenGL context.
    """

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        parent: QWidget | None = None,
        *,
        use_opengl: bool = True,
    ) -> None:
        super().__init__(parent)
        self._comp_width = width
        self._comp_height = height
        self._layers: list[dict] = []  # [{id, qimage, x, y, w, h, z_order, opacity}]
        self.setMinimumSize(320, 180)
        self.setAutoFillBackground(True)
        self._use_opengl = use_opengl and _HAS_OPENGL_WIDGET and _HAS_OPENGL_BLITTER
        self._gl_ready = False
        self._gl_error = ""
        self._blitter: QOpenGLTextureBlitter | None = None
        self._textures: dict[str, QOpenGLTexture] = {}
        self._texture_cache_keys: dict[str, int] = {}
        self._texture_sizes: dict[str, tuple[int, int]] = {}

    def set_composition_size(self, w: int, h: int) -> None:
        self._comp_width = w
        self._comp_height = h
        if self.isVisible():
            self.update()

    def set_layers(self, layers: list[dict]) -> None:
        """Set the current frame layers for compositing.

        Each dict should contain: ``qimage``, ``x``, ``y``, ``w``, ``h``,
        ``z_order``, ``opacity``.
        """
        self._layers = sorted(layers, key=lambda l: l.get("z_order", 0))
        if self.isVisible():
            self.update()

    def clear(self) -> None:
        self._layers = []
        if self.isVisible():
            self.update()

    def paintEvent(self, event) -> None:
        if self._use_opengl and _HAS_OPENGL_WIDGET:
            return super().paintEvent(event)
        self._paint_with_qpainter()

    def initializeGL(self) -> None:
        if not self._use_opengl:
            return
        try:
            self._blitter = QOpenGLTextureBlitter()
            if not self._blitter.create():
                raise RuntimeError("Qt OpenGL texture blitter could not be created.")
            self._gl_ready = True
            self._gl_error = ""
            context = self.context() if hasattr(self, "context") else None
            if context is not None:
                try:
                    context.aboutToBeDestroyed.connect(self._cleanup_gl_resources)
                except Exception:
                    logger.debug("Failed to connect GL cleanup hook.", exc_info=True)
        except Exception as exc:
            logger.warning("OpenGL compositor initialization failed.", exc_info=True)
            self._gl_ready = False
            self._gl_error = str(exc)

    def paintGL(self) -> None:
        if not self._use_opengl or not self._gl_ready or self._blitter is None:
            self._paint_with_qpainter()
            return

        context = self.context() if hasattr(self, "context") else None
        functions = context.functions() if context is not None else None
        if functions is None:
            self._paint_with_qpainter()
            return

        dpr = self.devicePixelRatioF()
        viewport = QRect(0, 0, int(self.width() * dpr), int(self.height() * dpr))

        functions.glViewport(0, 0, viewport.width(), viewport.height())
        functions.glClearColor(0.0, 0.0, 0.0, 1.0)
        functions.glClear(_OPENGL_COLOR_BUFFER_BIT)

        if not self._layers:
            self._destroy_orphan_textures(set())
            painter = QPainter(self)
            painter.setPen(QColor(120, 120, 120))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No preview")
            painter.end()
            return

        functions.glEnable(_OPENGL_BLEND)
        functions.glBlendFunc(_OPENGL_SRC_ALPHA, _OPENGL_ONE_MINUS_SRC_ALPHA)

        active_ids: set[str] = set()
        self._blitter.bind()
        try:
            for index, layer in enumerate(self._layers):
                img: QImage | None = layer.get("qimage")
                if img is None or img.isNull():
                    continue

                layer_id = str(layer.get("id") or f"layer-{index}")
                texture = self._ensure_texture(layer_id, img)
                active_ids.add(layer_id)

                opacity = float(layer.get("opacity", 1.0))
                lx = float(layer.get("x", 0.0))
                ly = float(layer.get("y", 0.0))
                lw = float(layer.get("w", img.width()))
                lh = float(layer.get("h", img.height()))
                dx, dy, dw, dh = self._composition_rect_in_widget(lx, ly, lw, lh)
                target_rect = QRectF(dx * dpr, dy * dpr, dw * dpr, dh * dpr)
                target_transform = QOpenGLTextureBlitter.targetTransform(target_rect, viewport)

                self._blitter.setOpacity(opacity)
                self._blitter.blit(
                    texture.textureId(),
                    target_transform,
                    QOpenGLTextureBlitter.Origin.OriginTopLeft,
                )
        finally:
            self._blitter.release()

        self._destroy_orphan_textures(active_ids)

    def _paint_with_qpainter(self) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Black background
        painter.fillRect(self.rect(), QColor(0, 0, 0))

        if not self._layers:
            painter.setPen(QColor(120, 120, 120))
            text = "No preview"
            fallback_reason = self._build_fallback_reason()
            if fallback_reason:
                text = f"{text}\n{fallback_reason}"
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)
            painter.end()
            return

        for layer in self._layers:
            img: QImage | None = layer.get("qimage")
            if img is None or img.isNull():
                continue

            opacity = layer.get("opacity", 1.0)
            painter.setOpacity(opacity)

            lx = layer.get("x", 0)
            ly = layer.get("y", 0)
            lw = layer.get("w", img.width())
            lh = layer.get("h", img.height())

            dx, dy, dw, dh = self._composition_rect_in_widget(lx, ly, lw, lh)
            painter.drawImage(QRectF(dx, dy, dw, dh), img)

        painter.setOpacity(1.0)
        painter.end()

    def _composition_rect_in_widget(
        self,
        lx: float,
        ly: float,
        lw: float,
        lh: float,
    ) -> tuple[float, float, float, float]:
        """Map composition-space coordinates into the widget viewport."""
        widget_w = max(1.0, float(self.width()))
        widget_h = max(1.0, float(self.height()))
        scale = min(widget_w / max(1, self._comp_width), widget_h / max(1, self._comp_height))
        offset_x = (widget_w - self._comp_width * scale) / 2.0
        offset_y = (widget_h - self._comp_height * scale) / 2.0
        return (
            offset_x + lx * scale,
            offset_y + ly * scale,
            lw * scale,
            lh * scale,
        )

    def is_live_compositing_available(self) -> bool:
        """Return True when the OpenGL compositor path is available for playback."""
        if not self._use_opengl:
            return False
        if self._gl_error:
            return False
        if hasattr(self, "isValid"):
            try:
                return bool(self.isValid())
            except Exception:
                return self._gl_ready
        return self._gl_ready

    def unavailable_reason(self) -> str:
        """Return a human-readable reason when live compositing is unavailable."""
        return self._build_fallback_reason()

    def _build_fallback_reason(self) -> str:
        if self._gl_error:
            return f"OpenGL compositor failed: {self._gl_error}"
        if not _HAS_OPENGL_WIDGET:
            return "OpenGL preview unavailable: QOpenGLWidget is not installed."
        if not _HAS_OPENGL_BLITTER:
            return "OpenGL preview unavailable: QOpenGLTextureBlitter is not installed."
        if self._use_opengl and hasattr(self, "isValid"):
            try:
                if not self.isValid():
                    return "OpenGL preview unavailable: Qt could not create a valid OpenGL context."
            except Exception:
                pass
        if self._use_opengl:
            return ""
        return "OpenGL compositing is disabled."

    def _ensure_texture(self, layer_id: str, image: QImage) -> QOpenGLTexture:
        """Return an uploaded texture for *layer_id*, recreating when needed.

        Always destroys and recreates the texture when the image data
        changes.  In-place ``setData()`` is avoided because Qt's
        ``QOpenGLTexture`` rejects format/size changes on allocated
        storage, which triggers noisy errors during rapid frame updates.
        """
        if QOpenGLTexture is None:
            raise RuntimeError("QOpenGLTexture is unavailable")

        normalized = image.convertToFormat(QImage.Format.Format_RGBA8888)
        image_size = (normalized.width(), normalized.height())
        image_key = int(normalized.cacheKey())

        cached_key = self._texture_cache_keys.get(layer_id)
        cached_size = self._texture_sizes.get(layer_id)

        if cached_key == image_key and cached_size == image_size:
            texture = self._textures.get(layer_id)
            if texture is not None:
                return texture

        # Destroy the old texture and create a fresh one
        old = self._textures.pop(layer_id, None)
        if old is not None:
            old.destroy()

        texture = QOpenGLTexture(
            normalized,
            QOpenGLTexture.MipMapGeneration.DontGenerateMipMaps,
        )
        texture.setMinMagFilters(
            QOpenGLTexture.Filter.Linear,
            QOpenGLTexture.Filter.Linear,
        )
        texture.setWrapMode(QOpenGLTexture.WrapMode.ClampToEdge)

        self._textures[layer_id] = texture
        self._texture_cache_keys[layer_id] = image_key
        self._texture_sizes[layer_id] = image_size
        return texture

    def _destroy_orphan_textures(self, active_ids: set[str]) -> None:
        stale_ids = [layer_id for layer_id in self._textures if layer_id not in active_ids]
        for layer_id in stale_ids:
            texture = self._textures.pop(layer_id)
            texture.destroy()
            self._texture_cache_keys.pop(layer_id, None)
            self._texture_sizes.pop(layer_id, None)

    def _cleanup_gl_resources(self) -> None:
        if not self._use_opengl:
            return
        try:
            if hasattr(self, "makeCurrent"):
                self.makeCurrent()
        except Exception:
            logger.debug("Failed to make GL context current for cleanup.", exc_info=True)

        self._destroy_orphan_textures(set())
        if self._blitter is not None and self._blitter.isCreated():
            self._blitter.destroy()
        self._blitter = None
        self._gl_ready = False

        try:
            if hasattr(self, "doneCurrent"):
                self.doneCurrent()
        except Exception:
            logger.debug("Failed to release GL context after cleanup.", exc_info=True)


# ---------------------------------------------------------------------------
# Playback engine
# ---------------------------------------------------------------------------


class PlaybackEngine(QObject):
    """Coordinates video decode, audio playback, and compositor updates.

    Signals
    -------
    position_changed(int)
        Emitted periodically with the current playback position in ms.
    playback_finished()
        Emitted when playback reaches the end of the composition.
    state_changed(str)
        Emitted when the state changes. Payload is ``"playing"``,
        ``"paused"``, or ``"stopped"``.
    """

    position_changed = Signal(int)
    playback_finished = Signal()
    state_changed = Signal(str)

    def __init__(
        self,
        compositor: CompositorWidget,
        *,
        allow_audio: bool = True,
    ) -> None:
        super().__init__()
        self._compositor = compositor
        self._allow_audio = allow_audio

        self._state: str = "stopped"  # "stopped", "playing", "paused"
        self._duration_ms: int = 0
        self._position_ms: float = 0.0

        # Model data set via load()
        self._visual_layers: list[dict] = []
        self._audio_layers: list[dict] = []

        # Decode workers
        self._video_workers: dict[str, _VideoDecodeWorker] = {}
        self._frame_queues: dict[str, queue.Queue] = {}
        self._frame_buffers: dict[str, list[tuple[int, QImage]]] = {}
        self._static_images: dict[str, QImage] = {}

        # Audio
        self._audio_player: _AudioPlayer | None = None

        # Display timer
        self._display_timer = QTimer()
        self._display_timer.setInterval(int(1000 / _DISPLAY_FPS))
        self._display_timer.timeout.connect(self._on_display_tick)

        # Guard against feedback loops when syncing position
        self._suppress_position_signal = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> str:
        return self._state

    @property
    def duration_ms(self) -> int:
        return self._duration_ms

    def availability(self) -> tuple[bool, str]:
        """Return whether real-time playback is currently available."""
        if av is None:
            return (False, "Real-time playback unavailable: PyAV is not installed.")
        if not self._compositor.is_live_compositing_available():
            return (False, self._compositor.unavailable_reason())
        return (True, "")

    def load(
        self,
        visual_layers: list[dict],
        audio_layers: list[dict],
        duration_ms: int,
        output_width: int = 1920,
        output_height: int = 1080,
    ) -> None:
        """Load composition data for playback.

        *visual_layers* — list of dicts with ``id``, ``path``, ``start_ms``,
        ``end_ms``, ``center_x``, ``center_y``, ``width``, ``height``,
        ``z_order``, ``opacity``, ``enabled``.

        *audio_layers* — list of dicts with ``id``, ``path``, ``start_ms``,
        ``duration_ms``, ``volume``, ``muted``, ``enabled``.
        """
        self.stop()
        self._visual_layers = visual_layers
        self._audio_layers = audio_layers
        self._duration_ms = duration_ms
        self._compositor.set_composition_size(output_width, output_height)
        self._position_ms = 0.0

    def play(self) -> bool:
        if self._state == "playing":
            return True
        if not self._visual_layers and not self._audio_layers:
            return False

        available, _reason = self.availability()
        if not available:
            return False

        try:
            self._start_decode_workers()
            self._start_audio()
            self._render_frame_at(int(self._position_ms))
        except Exception:
            logger.exception("Failed to start playback")
            self._stop_workers()
            if self._audio_player:
                try:
                    self._audio_player.stop()
                except Exception:
                    pass
                self._audio_player = None
            return False

        self._state = "playing"
        self._display_timer.start()
        self.state_changed.emit("playing")
        return True

    def pause(self) -> None:
        if self._state != "playing":
            return
        self._state = "paused"
        self._display_timer.stop()
        if self._audio_player:
            self._audio_player.stop()
        self.state_changed.emit("paused")

    def stop(self) -> None:
        self._state = "stopped"
        self._display_timer.stop()
        self._stop_workers()
        if self._audio_player:
            self._audio_player.stop()
            self._audio_player = None
        self._position_ms = 0.0
        self._compositor.clear()
        self.state_changed.emit("stopped")

    def seek(self, ms: int) -> None:
        """Seek to *ms* position.  Works in any state."""
        ms = max(0, min(ms, self._duration_ms))
        self._position_ms = float(ms)

        # Seek audio
        if self._audio_player:
            self._audio_player.seek(float(ms))

        # Seek video workers
        for layer_id, worker in self._video_workers.items():
            layer = self._visual_layer_by_id(layer_id)
            if layer is None:
                continue
            worker.seek(self._worker_seek_ms(layer, ms))

        # If paused or stopped, render the frame at this position
        if self._state != "playing":
            self._render_frame_at(ms)

        self._suppress_position_signal = True
        self.position_changed.emit(int(ms))
        self._suppress_position_signal = False

    def seek_from_timeline(self, ms: int) -> None:
        """Seek triggered by timeline interaction — does not re-emit position."""
        if self._duration_ms <= 0:
            return  # No composition loaded
        ms = max(0, min(ms, self._duration_ms))
        self._position_ms = float(ms)
        if self._audio_player:
            self._audio_player.seek(float(ms))
        for layer_id, worker in self._video_workers.items():
            layer = self._visual_layer_by_id(layer_id)
            if layer is None:
                continue
            worker.seek(self._worker_seek_ms(layer, ms))
        if self._state != "playing":
            self._render_frame_at(ms)

    def toggle_play_pause(self) -> bool:
        if self._state == "playing":
            self.pause()
            return True
        return self.play()

    def jump_to_start(self) -> None:
        self.seek(0)

    def jump_to_end(self) -> None:
        self.seek(self._duration_ms)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _start_decode_workers(self) -> None:
        self._stop_workers()
        self._frame_queues.clear()
        self._frame_buffers.clear()
        self._static_images.clear()

        for vl in self._visual_layers:
            if not vl.get("enabled", True) or not vl.get("path"):
                continue
            layer_id = vl.get("id", "")
            if vl.get("source_kind") == "image":
                image = QImage(vl["path"])
                if not image.isNull():
                    self._static_images[layer_id] = image
                continue
            q: queue.Queue = queue.Queue(maxsize=_MAX_FRAME_QUEUE)
            self._frame_queues[layer_id] = q
            worker = _VideoDecodeWorker(
                vl["path"],
                q,
                start_source_ms=self._worker_seek_ms(vl, int(self._position_ms)),
                layer_id=layer_id,
            )
            self._video_workers[layer_id] = worker
            worker.start()

    def _stop_workers(self) -> None:
        for w in self._video_workers.values():
            w.stop()
        # Don't join — they are daemon threads
        self._video_workers.clear()
        self._frame_queues.clear()
        self._frame_buffers.clear()
        self._static_images.clear()

    def _start_audio(self) -> None:
        if self._audio_player:
            self._audio_player.stop()

        enabled_audio = [
            al for al in self._audio_layers if al.get("enabled", True)
        ]
        if not enabled_audio:
            self._audio_player = None
            return

        self._audio_player = _AudioPlayer(
            enabled_audio, allow_device=self._allow_audio
        )
        self._audio_player.start(self._position_ms)

    def _on_display_tick(self) -> None:
        """Called at display FPS to composite and display the current frame."""
        if self._state != "playing":
            return

        try:
            # Read master clock
            if self._audio_player and self._audio_player.playing:
                self._position_ms = self._audio_player.current_ms()
            else:
                # No audio master — advance by timer interval
                self._position_ms += self._display_timer.interval()

            pos_ms = int(self._position_ms)

            # Check for end of composition
            if pos_ms >= self._duration_ms:
                self.stop()
                self.playback_finished.emit()
                return

            self._render_frame_at(pos_ms)
            self.position_changed.emit(pos_ms)
        except Exception:
            logger.exception("Display tick failed, stopping playback")
            self.stop()

    def _render_frame_at(self, pos_ms: int) -> None:
        """Composite and display all visible layers at *pos_ms*."""
        if not self._visual_layers:
            return
        if not self._compositor.isVisible():
            return
        self._drain_frame_queues()

        comp_layers: list[dict] = []
        for vl in self._visual_layers:
            if not vl.get("enabled", True):
                continue
            layer_id = vl.get("id", "")
            source_ms = self._layer_source_position_ms(vl, pos_ms)
            if source_ms is None:
                continue

            try:
                img = self._image_for_layer_at(vl, source_ms)
            except Exception:
                logger.debug("Failed to get image for layer %s", layer_id, exc_info=True)
                continue
            if img is None or img.isNull():
                continue

            # Convert center-origin coords to top-left for compositing
            comp_w = self._compositor._comp_width
            comp_h = self._compositor._comp_height
            lw = vl.get("width", img.width())
            lh = vl.get("height", img.height())
            cx = vl.get("center_x", 0)
            cy = vl.get("center_y", 0)
            tl_x = (comp_w / 2) + cx - (lw / 2)
            tl_y = (comp_h / 2) + cy - (lh / 2)

            comp_layers.append({
                "id": layer_id,
                "qimage": img,
                "x": tl_x,
                "y": tl_y,
                "w": lw,
                "h": lh,
                "z_order": vl.get("z_order", 0),
                "opacity": vl.get("opacity", 1.0),
            })

        self._compositor.set_layers(comp_layers)

    def _drain_frame_queues(self) -> None:
        """Drain decoded frames into per-layer rolling frame buffers."""
        for layer_id, q in self._frame_queues.items():
            buffer = self._frame_buffers.setdefault(layer_id, [])
            while True:
                try:
                    buffer.append(q.get_nowait())
                except queue.Empty:
                    break
            if len(buffer) > _MAX_FRAME_HISTORY:
                del buffer[:-_MAX_FRAME_HISTORY]

    def _image_for_layer_at(self, layer: dict, source_ms: int) -> QImage | None:
        """Return the best frame/image for *layer* at *source_ms*."""
        layer_id = layer.get("id", "")
        if layer.get("source_kind") == "image":
            image = self._static_images.get(layer_id)
            if image is None and layer.get("path"):
                image = QImage(layer["path"])
                if not image.isNull():
                    self._static_images[layer_id] = image
            return image

        buffered = self._select_buffered_frame(layer_id, source_ms)
        if buffered is not None:
            return buffered

        if self._state != "playing":
            return self._decode_frame_at(layer.get("path", ""), source_ms)
        return None

    def _select_buffered_frame(self, layer_id: str, source_ms: int) -> QImage | None:
        """Return the best buffered frame for *layer_id* at *source_ms*."""
        frames = self._frame_buffers.get(layer_id)
        if not frames:
            return None

        candidate: tuple[int, QImage] | None = None
        for pts_ms, image in frames:
            if pts_ms <= source_ms:
                candidate = (pts_ms, image)
            else:
                break

        if candidate is not None:
            self._frame_buffers[layer_id] = [
                frame for frame in frames
                if frame[0] >= max(0, candidate[0] - 1000)
            ][-_MAX_FRAME_HISTORY:]
            return candidate[1]

        return frames[0][1]

    def _decode_frame_at(self, source_path: str, source_ms: int) -> QImage | None:
        """Synchronously decode the closest frame at *source_ms* for paused seeking."""
        if av is None or not source_path:
            return None
        try:
            container = av.open(source_path)
            video_stream = next((stream for stream in container.streams if stream.type == "video"), None)
            if video_stream is None:
                container.close()
                return None
            if source_ms > 0:
                container.seek(int(source_ms * 1000), stream=video_stream, backward=True)

            best_image: QImage | None = None
            for frame in container.decode(video_stream):
                pts_ms = int(frame.pts * float(frame.time_base) * 1000) if frame.pts is not None else 0
                best_image = _VideoDecodeWorker._frame_to_qimage(frame)
                if pts_ms >= source_ms:
                    break
            container.close()
            return best_image
        except Exception:
            logger.debug("Synchronous frame decode failed for %s", source_path, exc_info=True)
            return None

    def _layer_source_position_ms(self, layer: dict, composition_ms: int) -> int | None:
        """Map composition time to source time for a visual layer.

        Delegates to the shared :func:`evaluate_visual_layer` contract
        so preview and export use identical timing semantics.
        """
        cl = CompositionLayer(
            start_ms=int(layer.get("start_ms", 0)),
            end_ms=int(layer.get("end_ms", 0)),
            source_duration_ms=int(layer.get("source_duration_ms", 0)),
            behavior_after_end=layer.get("behavior_after_end", "hide"),
        )
        result = evaluate_visual_layer(cl, composition_ms)
        return result.source_time_ms

    def _worker_seek_ms(self, layer: dict, composition_ms: int) -> int:
        """Return the source seek target for a decode worker."""
        source_ms = self._layer_source_position_ms(layer, composition_ms)
        if source_ms is None:
            return 0
        return source_ms

    def _visual_layer_by_id(self, layer_id: str) -> dict | None:
        """Return the visual-layer dict for *layer_id*, if any."""
        for layer in self._visual_layers:
            if layer.get("id") == layer_id:
                return layer
        return None

    def layer_image_at(self, layer_id: str, position_ms: int) -> QImage | None:
        """Return the decoded frame for a single layer at *position_ms*.

        This is used by the Layer preview tab to display individual layer
        frames synchronized with the playhead.
        """
        layer = self._visual_layer_by_id(layer_id)
        if layer is None:
            return None
        source_ms = self._layer_source_position_ms(layer, position_ms)
        if source_ms is None:
            return None
        return self._image_for_layer_at(layer, source_ms)
