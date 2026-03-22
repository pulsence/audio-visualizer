"""Tests for FFmpegRenderer progress parsing."""

from pathlib import Path

from audio_visualizer.caption.core.sizing import OverlaySize
from audio_visualizer.caption.rendering.ffmpegRenderer import FFmpegRenderer
from audio_visualizer.events import AppEventEmitter, EventLevel, EventType


class TestFFmpegRenderer:
    def test_parse_out_time_seconds(self):
        assert FFmpegRenderer._parse_out_time_seconds("00:00:03.500000") == 3.5
        assert FFmpegRenderer._parse_out_time_seconds("01:02:03.250000") == 3723.25
        assert FFmpegRenderer._parse_out_time_seconds(None) is None

    def test_render_retries_with_software_encoder_after_hardware_failure(self, monkeypatch, tmp_path):
        events = []
        emitter = AppEventEmitter()
        emitter.subscribe(events.append)
        renderer = FFmpegRenderer(
            emitter,
            ffmpeg_path="ffmpeg",
            quality="small",
            show_progress=False,
        )

        monkeypatch.setattr(
            "audio_visualizer.hwaccel.select_encoder",
            lambda codec: "h264_nvenc",
        )

        attempted_encoders: list[str] = []

        def _fake_run(cmd, output_path, duration_sec):
            encoder = cmd[cmd.index("-c:v") + 1]
            attempted_encoders.append(encoder)
            if encoder == "h264_nvenc":
                raise RuntimeError("hardware encoder failed")

        monkeypatch.setattr(renderer, "_run_render_command", _fake_run)

        renderer.render(
            ass_path=tmp_path / "captions.ass",
            output_path=tmp_path / "captions.mp4",
            size=OverlaySize(1920, 1080),
            fps="30",
            duration_sec=5.0,
        )

        assert attempted_encoders == ["h264_nvenc", "libx264"]
        assert any(
            event.event_type == EventType.LOG
            and event.level == EventLevel.WARNING
            and "retrying ffmpeg render with software encoder libx264" in event.message.lower()
            for event in events
        )
        assert any(
            event.event_type == EventType.RENDER_COMPLETE
            and event.data == {"video_encoder": "libx264"}
            for event in events
        )
