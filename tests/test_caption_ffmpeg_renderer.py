"""Tests for FFmpegRenderer progress parsing."""

from audio_visualizer.caption.rendering.ffmpegRenderer import FFmpegRenderer


class TestFFmpegRenderer:
    def test_parse_out_time_seconds(self):
        assert FFmpegRenderer._parse_out_time_seconds("00:00:03.500000") == 3.5
        assert FFmpegRenderer._parse_out_time_seconds("01:02:03.250000") == 3723.25
        assert FFmpegRenderer._parse_out_time_seconds(None) is None
