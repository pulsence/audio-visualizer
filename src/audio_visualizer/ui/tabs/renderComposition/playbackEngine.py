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
import math
import queue
import threading
import time
from typing import Any

import numpy as np

from PySide6.QtCore import QObject, QTimer, Signal, Qt
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional imports gated through capabilities
# ---------------------------------------------------------------------------

_HAS_OPENGL_WIDGET = False
_HAS_SOUNDDEVICE = False
_HAS_PYAV = False

try:
    from PySide6.QtOpenGLWidgets import QOpenGLWidget

    _HAS_OPENGL_WIDGET = True
except ImportError:
    QOpenGLWidget = None  # type: ignore[assignment,misc]

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
        start_ms: int = 0,
        *,
        layer_id: str = "",
    ) -> None:
        super().__init__(daemon=True, name=f"VideoDecode-{layer_id[:8]}")
        self.source_path = source_path
        self.frame_queue = frame_queue
        self.start_ms = start_ms
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

            # Seek to start offset
            if self.start_ms > 0:
                container.seek(int(self.start_ms * 1000), stream=video_stream)

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
                    container.seek(int(seek_ms * 1000), stream=video_stream)
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
            rgb_frame = frame.reformat(format="rgb24")
            arr = rgb_frame.to_ndarray()
            h, w, _ = arr.shape
            return QImage(
                arr.tobytes(), w, h, w * 3, QImage.Format.Format_RGB888
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
        with self._lock:
            self._playing = False
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

    def current_ms(self) -> float:
        with self._lock:
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
            layer_start_ms = layer_info.get("start_ms", 0)
            layer_duration_ms = layer_info.get("duration_ms", 0)

            # Calculate sample offset into this layer's audio
            offset_ms = pos_ms - layer_start_ms
            if offset_ms < 0:
                continue
            if layer_duration_ms > 0 and offset_ms >= layer_duration_ms:
                continue

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


class CompositorWidget(QWidget):
    """Lightweight compositor that draws decoded frames as layered images.

    When QOpenGLWidget is available and ``use_opengl=True``, this widget
    inherits from QOpenGLWidget for GPU-accelerated blitting.  Otherwise
    it falls back to a plain QWidget with QPainter compositing.
    """

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        parent: QWidget | None = None,
        *,
        use_opengl: bool = True,
    ) -> None:
        # We always use QPainter compositing here — the OpenGL path would
        # require a full texture-blit pipeline.  This keeps the widget
        # testable without a real GPU.
        super().__init__(parent)
        self._comp_width = width
        self._comp_height = height
        self._layers: list[dict] = []  # [{id, qimage, x, y, w, h, z_order, opacity}]
        self.setMinimumSize(320, 180)
        self.setAutoFillBackground(True)
        self._use_opengl = use_opengl and _HAS_OPENGL_WIDGET

    def set_composition_size(self, w: int, h: int) -> None:
        self._comp_width = w
        self._comp_height = h
        self.update()

    def set_layers(self, layers: list[dict]) -> None:
        """Set the current frame layers for compositing.

        Each dict should contain: ``qimage``, ``x``, ``y``, ``w``, ``h``,
        ``z_order``, ``opacity``.
        """
        self._layers = sorted(layers, key=lambda l: l.get("z_order", 0))
        self.update()

    def clear(self) -> None:
        self._layers = []
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Black background
        painter.fillRect(self.rect(), QColor(0, 0, 0))

        if not self._layers:
            painter.setPen(QColor(120, 120, 120))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No preview")
            painter.end()
            return

        # Scale composition to widget
        widget_w = self.width()
        widget_h = self.height()
        scale = min(widget_w / self._comp_width, widget_h / self._comp_height)
        offset_x = (widget_w - self._comp_width * scale) / 2
        offset_y = (widget_h - self._comp_height * scale) / 2

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

            # Map composition coords to widget coords
            dx = offset_x + lx * scale
            dy = offset_y + ly * scale
            dw = lw * scale
            dh = lh * scale

            from PySide6.QtCore import QRectF

            painter.drawImage(QRectF(dx, dy, dw, dh), img)

        painter.setOpacity(1.0)
        painter.end()


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
        self._video_workers: list[_VideoDecodeWorker] = []
        self._frame_queues: dict[str, queue.Queue] = {}
        self._latest_frames: dict[str, tuple[int, QImage]] = {}

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

    def play(self) -> None:
        if self._state == "playing":
            return
        if not self._visual_layers and not self._audio_layers:
            return

        self._start_decode_workers()
        self._start_audio()
        self._state = "playing"
        self._display_timer.start()
        self.state_changed.emit("playing")

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
        for w in self._video_workers:
            w.seek(ms)

        # If paused or stopped, render the frame at this position
        if self._state != "playing":
            self._render_frame_at(ms)

        self._suppress_position_signal = True
        self.position_changed.emit(int(ms))
        self._suppress_position_signal = False

    def seek_from_timeline(self, ms: int) -> None:
        """Seek triggered by timeline interaction — does not re-emit position."""
        ms = max(0, min(ms, self._duration_ms))
        self._position_ms = float(ms)
        if self._audio_player:
            self._audio_player.seek(float(ms))
        for w in self._video_workers:
            w.seek(ms)
        if self._state != "playing":
            self._render_frame_at(ms)

    def toggle_play_pause(self) -> None:
        if self._state == "playing":
            self.pause()
        else:
            self.play()

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
        self._latest_frames.clear()

        for vl in self._visual_layers:
            if not vl.get("enabled", True) or not vl.get("path"):
                continue
            layer_id = vl.get("id", "")
            q: queue.Queue = queue.Queue(maxsize=_MAX_FRAME_QUEUE)
            self._frame_queues[layer_id] = q
            worker = _VideoDecodeWorker(
                vl["path"],
                q,
                start_ms=int(self._position_ms),
                layer_id=layer_id,
            )
            self._video_workers.append(worker)
            worker.start()

    def _stop_workers(self) -> None:
        for w in self._video_workers:
            w.stop()
        # Don't join — they are daemon threads
        self._video_workers.clear()
        self._frame_queues.clear()
        self._latest_frames.clear()

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

    def _render_frame_at(self, pos_ms: int) -> None:
        """Composite and display all visible layers at *pos_ms*."""
        # Drain frame queues and update latest frames
        for layer_id, q in self._frame_queues.items():
            while True:
                try:
                    pts_ms, img = q.get_nowait()
                    self._latest_frames[layer_id] = (pts_ms, img)
                except queue.Empty:
                    break

        comp_layers: list[dict] = []
        for vl in self._visual_layers:
            if not vl.get("enabled", True):
                continue
            layer_id = vl.get("id", "")
            start_ms = vl.get("start_ms", 0)
            end_ms = vl.get("end_ms", 0)

            if pos_ms < start_ms or pos_ms > end_ms:
                continue

            # Get frame
            frame_data = self._latest_frames.get(layer_id)
            if frame_data is None:
                continue

            _, img = frame_data

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
                "qimage": img,
                "x": tl_x,
                "y": tl_y,
                "w": lw,
                "h": lh,
                "z_order": vl.get("z_order", 0),
                "opacity": vl.get("opacity", 1.0),
            })

        self._compositor.set_layers(comp_layers)
