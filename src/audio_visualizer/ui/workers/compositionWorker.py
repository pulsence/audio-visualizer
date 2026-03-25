"""Composition render worker — FFmpeg subprocess runner.

Builds the FFmpeg command from a :class:`CompositionModel`, executes it
in a subprocess, parses progress output, and reports lifecycle state
through the shared :class:`WorkerSignals` contract.
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

from PySide6.QtCore import QRunnable

from audio_visualizer.hwaccel import is_hardware_encoder
from audio_visualizer.ui.tabs.renderComposition.evaluation import (
    compute_composition_duration_ms,
)
from audio_visualizer.ui.tabs.renderComposition.filterGraph import (
    build_ffmpeg_command,
)
from audio_visualizer.ui.tabs.renderComposition.model import CompositionModel
from audio_visualizer.ui.workers.workerBridge import WorkerSignals

logger = logging.getLogger(__name__)

# Regex to extract time= from FFmpeg stderr progress
_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+)\.(\d+)")
_SOFTWARE_FALLBACK_ENCODER = "libx264"


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
        self.signals = WorkerSignals()

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
        self.signals.started.emit(
            "composition",
            "render_composition",
            f"Rendering composition to {Path(self._output_path).name}",
        )
        self.signals.stage.emit(
            "Preparing FFmpeg command",
            0,
            2,
            {"output_path": self._output_path},
        )
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
        selected_encoder = self._extract_video_encoder(cmd)
        logger.info("FFmpeg command: %s", " ".join(cmd))
        self.signals.log.emit(
            "INFO",
            "Prepared FFmpeg composition command.",
            self._command_log_data(cmd, selected_encoder),
        )
        self.signals.stage.emit(
            "Running FFmpeg",
            1,
            2,
            self._stage_data(selected_encoder),
        )

        duration_s = compute_composition_duration_ms(self._model) / 1000.0
        if duration_s <= 0:
            duration_s = 10.0

        result = self._run_ffmpeg_command(cmd, duration_s, selected_encoder)
        if result is None:
            return

        returncode, stderr_lines = result
        actual_encoder = selected_encoder

        if (
            returncode != 0
            and selected_encoder
            and is_hardware_encoder(selected_encoder)
            and not self._cancel_flag.is_set()
        ):
            self.signals.log.emit(
                "WARNING",
                "Hardware encoder failed; retrying with software encoder.",
                {
                    "failed_encoder": selected_encoder,
                    "fallback_encoder": _SOFTWARE_FALLBACK_ENCODER,
                    "output_path": self._output_path,
                },
            )
            fallback_cmd = build_ffmpeg_command(
                self._model,
                self._output_path,
                encoder_override=_SOFTWARE_FALLBACK_ENCODER,
            )
            actual_encoder = _SOFTWARE_FALLBACK_ENCODER
            self.signals.log.emit(
                "INFO",
                "Prepared fallback FFmpeg composition command.",
                self._command_log_data(fallback_cmd, actual_encoder),
            )
            self.signals.stage.emit(
                "Retrying FFmpeg with software encoder",
                1,
                2,
                self._stage_data(actual_encoder),
            )
            result = self._run_ffmpeg_command(fallback_cmd, duration_s, actual_encoder, retry=True)
            if result is None:
                return
            returncode, stderr_lines = result

        if returncode != 0:
            stderr_text = "".join(stderr_lines[-20:])
            self.signals.failed.emit(
                f"FFmpeg exited with code {returncode}:\n{stderr_text}",
                self._stage_data(actual_encoder),
            )
            return

        self.signals.progress.emit(
            100.0,
            f"Render complete ({actual_encoder or 'unknown encoder'}).",
            self._stage_data(actual_encoder),
        )
        self.signals.completed.emit({
            "output_path": self._output_path,
            "video_encoder": actual_encoder,
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

    def _run_ffmpeg_command(
        self,
        cmd: list[str],
        duration_s: float,
        video_encoder: str | None,
        *,
        retry: bool = False,
    ) -> tuple[int, list[str]] | None:
        """Run one FFmpeg invocation and collect stderr for progress/failure."""
        status_message = (
            f"Retrying with {video_encoder}..."
            if retry and video_encoder
            else f"Starting FFmpeg ({video_encoder})..."
            if video_encoder
            else "Starting FFmpeg..."
        )
        self.signals.progress.emit(0.0, status_message, self._stage_data(video_encoder))

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as exc:
            self.signals.failed.emit(
                f"Failed to start FFmpeg: {exc}",
                self._stage_data(video_encoder),
            )
            return None

        if self._cancel_flag.is_set():
            self._cleanup()
            self.signals.canceled.emit("Render canceled before start.")
            return None

        stderr_lines: list[str] = []
        try:
            if self._process.stderr is None:
                raise RuntimeError("FFmpeg process stderr is unavailable")
            for line in self._process.stderr:
                if self._cancel_flag.is_set():
                    self._cleanup()
                    self.signals.canceled.emit("Render canceled.")
                    return None

                stderr_lines.append(line)
                progress = self._parse_progress(line, duration_s)
                if progress is not None:
                    self.signals.progress.emit(
                        progress,
                        f"Rendering... {progress:.0f}%",
                        self._stage_data(video_encoder),
                    )
        except Exception as exc:
            logger.warning("Error reading FFmpeg output: %s", exc)

        returncode = self._process.wait()
        self._process = None

        if self._cancel_flag.is_set():
            self.signals.canceled.emit("Render canceled.")
            return None

        return returncode, stderr_lines

    def _extract_video_encoder(self, cmd: list[str]) -> str | None:
        """Return the ``-c:v`` encoder from an FFmpeg command, if present."""
        try:
            idx = cmd.index("-c:v")
        except ValueError:
            return None
        if idx + 1 >= len(cmd):
            return None
        return cmd[idx + 1]

    def _stage_data(self, video_encoder: str | None) -> dict[str, Any]:
        """Build signal payloads while keeping existing fields stable."""
        data: dict[str, Any] = {"output_path": self._output_path}
        if video_encoder:
            data["video_encoder"] = video_encoder
        return data

    def _command_log_data(self, cmd: list[str], video_encoder: str | None) -> dict[str, Any]:
        """Build log payloads for prepared commands."""
        data = self._stage_data(video_encoder)
        data["command"] = cmd
        return data
