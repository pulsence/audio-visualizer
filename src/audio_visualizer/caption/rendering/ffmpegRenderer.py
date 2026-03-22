"""
FFmpeg-based video rendering.

This module provides a renderer that uses FFmpeg with libass to render
subtitle overlays as transparent ProRes 4444 videos.
"""

import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from audio_visualizer.events import AppEvent, AppEventEmitter, EventLevel, EventType
from ..core.sizing import OverlaySize

logger = logging.getLogger(__name__)


class FFmpegRenderer:
    """
    Renders subtitle overlays using FFmpeg.

    This renderer creates transparent video files (ProRes 4444 with alpha channel)
    by rendering ASS subtitles onto a transparent canvas using FFmpeg's libass filter.

    Example:
        from audio_visualizer.events import AppEventEmitter

        emitter = AppEventEmitter()
        emitter.subscribe(lambda e: print(e.message))

        renderer = FFmpegRenderer(emitter, loglevel="error", show_progress=True)
        renderer.render(
            ass_path=Path("subtitles.ass"),
            output_path=Path("overlay.mov"),
            size=OverlaySize(1920, 1080),
            fps="30",
            duration_sec=120.5
        )
    """

    def __init__(
        self,
        emitter: AppEventEmitter,
        loglevel: str = "error",
        show_progress: bool = True,
        ffmpeg_path: Optional[str] = None,
        quality: str = "small",
    ) -> None:
        """
        Initialize FFmpeg renderer.

        Args:
            emitter: AppEventEmitter for progress and debug events
            loglevel: FFmpeg log level (quiet, error, warning, info, debug)
            show_progress: Whether to emit render progress events
            ffmpeg_path: Path to ffmpeg binary (if None, searches PATH)
            quality: Output quality preset (small/medium/large)
        """
        self.emitter = emitter
        self.loglevel = loglevel
        self.show_progress = show_progress
        self.ffmpeg_path = ffmpeg_path or self._find_ffmpeg()
        self.quality = quality

    def _find_ffmpeg(self) -> str:
        """
        Find FFmpeg executable on the system.

        Returns:
            Path to ffmpeg binary

        Raises:
            RuntimeError: If ffmpeg is not found
        """
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError(
                "FFmpeg not found on PATH. Please install FFmpeg and ensure "
                "it is available in your system PATH."
            )
        return ffmpeg

    def _build_h264_args(self, encoder_override: str | None = None) -> tuple[list[str], str]:
        """
        Build H.264 codec arguments with hardware acceleration when available.

        Returns:
            Tuple of FFmpeg arguments and the selected encoder name.
        """
        from audio_visualizer.hwaccel import select_encoder

        encoder = encoder_override or select_encoder("h264")
        logger.info("Caption render using encoder: %s", encoder)

        return [
            "-c:v",
            encoder,
            "-crf",
            "18",  # Visually lossless quality
            "-preset",
            "slow",  # Better compression
            "-pix_fmt",
            "yuva420p",  # Alpha support
        ], encoder

    def _build_prores_422hq_args(self) -> list:
        """
        Build ProRes 422 HQ codec arguments.

        Returns:
            List of FFmpeg arguments for ProRes 422 HQ encoding
        """
        return [
            "-c:v",
            "prores_ks",
            "-profile:v",
            "3",  # ProRes 422 HQ
            "-pix_fmt",
            "yuv422p10le",
        ]

    def _build_prores_4444_args(self) -> list:
        """
        Build ProRes 4444 codec arguments (with alpha).

        Returns:
            List of FFmpeg arguments for ProRes 4444 encoding
        """
        return [
            "-c:v",
            "prores_ks",
            "-profile:v",
            "4",  # ProRes 4444
            "-pix_fmt",
            "yuva444p10le",
        ]

    def render(
        self,
        ass_path: Path,
        output_path: Path,
        size: OverlaySize,
        fps: str,
        duration_sec: float,
    ) -> None:
        """
        Render ASS subtitles to transparent video.

        Args:
            ass_path: Path to ASS subtitle file
            output_path: Path for output video file (.mov)
            size: Overlay dimensions
            fps: Frame rate (e.g., "30", "60", "30000/1001")
            duration_sec: Video duration in seconds

        Raises:
            RuntimeError: If rendering fails
        """
        w, h = size.width, size.height

        # Escape path for FFmpeg filter syntax
        ass_escaped = self._escape_filter_path(ass_path)

        actual_encoder: str | None = None

        def _build_command(
            *,
            encoder_override: str | None = None,
        ) -> tuple[list[str], str | None]:
            if self.quality == "small":
                # H.264 with transparency support (using overlay)
                video_filter = (
                    f"format=rgba,"
                    f"subtitles=filename='{ass_escaped}':alpha=1:original_size={w}x{h},"
                    f"format=yuva420p"
                )
                codec_args, selected_encoder = self._build_h264_args(encoder_override)
            elif self.quality == "medium":
                # ProRes 422 HQ (no alpha)
                video_filter = (
                    f"format=rgba,"
                    f"subtitles=filename='{ass_escaped}':alpha=1:original_size={w}x{h},"
                    f"format=yuv422p10le"
                )
                codec_args = self._build_prores_422hq_args()
                selected_encoder = None
            else:  # large
                # ProRes 4444 (with alpha)
                video_filter = (
                    f"format=rgba,"
                    f"subtitles=filename='{ass_escaped}':alpha=1:original_size={w}x{h},"
                    f"format=yuva444p10le"
                )
                codec_args = self._build_prores_4444_args()
                selected_encoder = None

            cmd = [
                self.ffmpeg_path,
                "-y",  # Overwrite output
                "-hide_banner",
                "-loglevel",
                self.loglevel,
                "-f",
                "lavfi",
                "-t",
                f"{duration_sec:.3f}",
                "-i",
                f"color=c=black@0.0:s={w}x{h}:r={fps}",
                "-vf",
                video_filter,
            ]
            cmd.extend(codec_args)
            cmd.extend(
                [
                    "-r",
                    fps,
                    "-an",  # No audio
                    str(output_path),
                ]
            )

            if self.show_progress:
                cmd.insert(1, "-progress")
                cmd.insert(2, "pipe:2")
                cmd.insert(3, "-nostats")
            return cmd, selected_encoder

        cmd, selected_encoder = _build_command()
        actual_encoder = selected_encoder
        self._emit_command_log(cmd, selected_encoder)

        # Emit render start event
        self.emitter.emit(
            AppEvent(
                event_type=EventType.RENDER_START,
                message="Starting FFmpeg render",
            )
        )

        try:
            self._run_render_command(cmd, output_path, duration_sec)
        except RuntimeError:
            from audio_visualizer.hwaccel import is_hardware_encoder

            if (
                self.quality != "small"
                or not selected_encoder
                or not is_hardware_encoder(selected_encoder)
            ):
                raise

            actual_encoder = "libx264"
            self.emitter.emit(
                AppEvent(
                    event_type=EventType.LOG,
                    message=(
                        "Hardware encoder failed; retrying FFmpeg render "
                        "with software encoder libx264."
                    ),
                    level=EventLevel.WARNING,
                    data={
                        "failed_encoder": selected_encoder,
                        "fallback_encoder": actual_encoder,
                    },
                )
            )
            cmd, _ = _build_command(encoder_override=actual_encoder)
            self._emit_command_log(cmd, actual_encoder)
            self._run_render_command(cmd, output_path, duration_sec)

        # Emit render complete event
        self.emitter.emit(
            AppEvent(
                event_type=EventType.RENDER_COMPLETE,
                message="FFmpeg render complete",
                data=({"video_encoder": actual_encoder} if actual_encoder else None),
            )
        )

    def _emit_command_log(self, cmd: list[str], video_encoder: str | None) -> None:
        """Emit diagnostic events describing the FFmpeg command and encoder."""
        if video_encoder:
            self.emitter.emit(
                AppEvent(
                    event_type=EventType.LOG,
                    message=f"Using video encoder: {video_encoder}",
                    level=EventLevel.INFO,
                    data={"video_encoder": video_encoder},
                )
            )

        self.emitter.emit(
            AppEvent(
                event_type=EventType.LOG,
                message="FFmpeg command:\n  " + " ".join(cmd),
                level=EventLevel.DEBUG,
                data=({"video_encoder": video_encoder} if video_encoder else None),
            )
        )

    def _run_render_command(
        self,
        cmd: list,
        output_path: Path,
        duration_sec: float,
    ) -> None:
        """Dispatch to the configured FFmpeg execution mode."""
        if not self.show_progress:
            self._render_simple(cmd, output_path)
        else:
            self._render_with_progress(cmd, output_path, duration_sec)

    def _render_simple(self, cmd: list, output_path: Path) -> None:
        """Run FFmpeg without progress tracking."""
        result = subprocess.run(cmd)
        if result.returncode != 0:
            raise RuntimeError("FFmpeg render failed. Check output above for details.")

        self._verify_output(output_path)

    def _render_with_progress(
        self,
        cmd: list,
        output_path: Path,
        duration_sec: float,
    ) -> None:
        """Run FFmpeg with progress tracking."""
        proc = subprocess.Popen(
            cmd,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        last_emit = time.time()
        frame = None
        out_time = None
        speed = None

        assert proc.stderr is not None
        for line in proc.stderr:
            line = line.strip()
            if not line or "=" not in line:
                continue

            key, value = line.split("=", 1)

            if key == "frame":
                frame = value
            elif key == "out_time":
                out_time = value
            elif key == "speed":
                speed = value
            elif key == "progress" and value == "end":
                break

            # Emit progress at most twice per second
            now = time.time()
            if now - last_emit >= 0.5 and (frame or out_time):
                percent = None
                current_seconds = self._parse_out_time_seconds(out_time)
                if current_seconds is not None and duration_sec > 0:
                    percent = min(100.0, (current_seconds / duration_sec) * 100.0)
                self.emitter.emit(
                    AppEvent(
                        event_type=EventType.RENDER_PROGRESS,
                        message="FFmpeg rendering",
                        data={
                            "percent": percent,
                            "frame": int(frame) if frame else None,
                            "time": out_time,
                            "speed": speed,
                        },
                    )
                )
                last_emit = now

        returncode = proc.wait()
        if returncode != 0:
            raise RuntimeError("FFmpeg render failed. Check output above for details.")

        self._verify_output(output_path)

    @staticmethod
    def _parse_out_time_seconds(value: str | None) -> float | None:
        """Parse FFmpeg ``out_time`` strings into seconds."""
        if not value:
            return None

        try:
            hours, minutes, seconds = value.split(":")
            return (
                int(hours) * 3600
                + int(minutes) * 60
                + float(seconds)
            )
        except (TypeError, ValueError):
            return None

    def _verify_output(self, output_path: Path) -> None:
        """Verify that output file was created successfully."""
        if not output_path.exists():
            raise RuntimeError(f"Output file was not created: {output_path}")

        if output_path.stat().st_size < 1024:
            raise RuntimeError(
                f"Output file is too small ({output_path.stat().st_size} bytes), "
                "render likely failed"
            )

    @staticmethod
    def _escape_filter_path(path: Path) -> str:
        """
        Escape file path for FFmpeg filter syntax.

        FFmpeg filters use ':' as separators and need special escaping for:
        - Backslashes (Windows paths)
        - Colons (Windows drive letters)
        - Single quotes (used as delimiters)

        Args:
            path: Path to escape

        Returns:
            Escaped path string safe for FFmpeg filter
        """
        # Use forward slashes (works on all platforms)
        s = str(path.resolve()).replace("\\", "/")

        # Escape colons (for drive letters like C:)
        s = s.replace(":", r"\:")

        # Escape single quotes
        s = s.replace("'", r"\'")

        return s
