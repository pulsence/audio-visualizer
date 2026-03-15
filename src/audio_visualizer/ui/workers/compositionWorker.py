"""Composition render worker — FFmpeg subprocess runner.

Builds the FFmpeg command from a :class:`CompositionModel`, executes it
in a subprocess, parses progress output, and reports status through
:class:`WorkerSignals`.
"""
from __future__ import annotations

import copy
import logging
import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal

from audio_visualizer.ui.tabs.renderComposition.filterGraph import (
    build_ffmpeg_command,
)
from audio_visualizer.ui.tabs.renderComposition.model import CompositionModel

logger = logging.getLogger(__name__)

# Regex to extract time= from FFmpeg stderr progress
_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+)\.(\d+)")


class _CompositionSignals(QObject):
    """Qt signals emitted by :class:`CompositionWorker`."""

    progress = Signal(float, str, dict)
    completed = Signal(dict)
    failed = Signal(str, dict)
    canceled = Signal(str)


class CompositionWorker(QRunnable):
    """QRunnable that renders a composition via FFmpeg subprocess.

    Parameters
    ----------
    model : CompositionModel
        The composition model to render.
    output_path : str | Path
        Destination file path for the rendered video.
    """

    def __init__(
        self,
        model: CompositionModel,
        output_path: str | Path,
    ) -> None:
        super().__init__()
        self.setAutoDelete(True)

        self._model = copy.deepcopy(model)
        self._output_path = str(output_path)
        self._cancel_flag = threading.Event()
        self._process: subprocess.Popen | None = None
        self.signals = _CompositionSignals()

    # ------------------------------------------------------------------
    # Cancel support
    # ------------------------------------------------------------------

    def cancel(self) -> None:
        """Request cancellation — terminates the FFmpeg subprocess."""
        self._cancel_flag.set()
        proc = self._process
        if proc is not None:
            try:
                proc.terminate()
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Build and execute the FFmpeg command."""
        try:
            self._do_render()
        except Exception as exc:
            logger.exception("Composition render failed unexpectedly.")
            self.signals.failed.emit(str(exc), {})

    def _do_render(self) -> None:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            self.signals.failed.emit(
                "ffmpeg not found on PATH. Install FFmpeg to render compositions.",
                {},
            )
            return

        cmd = build_ffmpeg_command(self._model, self._output_path)
        logger.info("FFmpeg command: %s", " ".join(cmd))

        self.signals.progress.emit(0.0, "Starting FFmpeg...", {})

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as exc:
            self.signals.failed.emit(f"Failed to start FFmpeg: {exc}", {})
            return

        if self._cancel_flag.is_set():
            self._cleanup()
            self.signals.canceled.emit("Render canceled before start.")
            return

        duration_s = self._model.get_duration_ms() / 1000.0
        if duration_s <= 0:
            duration_s = 10.0

        # Read stderr for progress
        stderr_lines: list[str] = []
        try:
            assert self._process.stderr is not None
            for line in self._process.stderr:
                if self._cancel_flag.is_set():
                    self._cleanup()
                    self.signals.canceled.emit("Render canceled.")
                    return

                stderr_lines.append(line)
                progress = self._parse_progress(line, duration_s)
                if progress is not None:
                    self.signals.progress.emit(
                        progress,
                        f"Rendering... {progress:.0f}%",
                        {},
                    )
        except Exception as exc:
            logger.warning("Error reading FFmpeg output: %s", exc)

        returncode = self._process.wait()
        self._process = None

        if self._cancel_flag.is_set():
            self.signals.canceled.emit("Render canceled.")
            return

        if returncode != 0:
            stderr_text = "".join(stderr_lines[-20:])
            self.signals.failed.emit(
                f"FFmpeg exited with code {returncode}:\n{stderr_text}",
                {},
            )
            return

        self.signals.progress.emit(100.0, "Render complete.", {})
        self.signals.completed.emit({
            "output_path": self._output_path,
        })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_progress(self, line: str, duration_s: float) -> float | None:
        """Parse an FFmpeg progress line and return percent complete."""
        match = _TIME_RE.search(line)
        if match is None:
            return None

        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        centiseconds = int(match.group(4))

        current_s = hours * 3600 + minutes * 60 + seconds + centiseconds / 100.0
        if duration_s <= 0:
            return 0.0

        percent = min(100.0, (current_s / duration_s) * 100.0)
        return percent

    def _cleanup(self) -> None:
        """Terminate and clean up the subprocess."""
        proc = self._process
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    proc.kill()
                except OSError:
                    pass
            self._process = None
