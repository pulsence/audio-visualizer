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
from typing import Any, Dict, Optional

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
                self.signals.completed.emit({
                    "output_path": str(result.output_path),
                    "width": result.width,
                    "height": result.height,
                    "duration_ms": result.duration_ms,
                    "quality": self._spec.config.quality,
                    "has_alpha": self._spec.config.quality != "medium",
                })
            else:
                self.signals.failed.emit(
                    result.error or "Unknown render error",
                    {"detail": result.error},
                )

        except Exception as exc:
            if self._cancel_flag.is_set():
                self.signals.canceled.emit("Cancelled during render")
            else:
                logger.exception("CaptionRenderWorker failed: %s", exc)
                self.signals.failed.emit(str(exc), {"detail": str(exc)})

        finally:
            self._bridge.detach()
