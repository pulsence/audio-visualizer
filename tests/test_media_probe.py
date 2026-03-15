"""Tests for media probing helpers."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from audio_visualizer.ui.mediaProbe import (
    check_composition_compatibility,
    classify_caption_output,
    probe_media,
)


# ------------------------------------------------------------------
# probe_media tests
# ------------------------------------------------------------------


class TestProbeMedia:
    """Tests for the probe_media function."""

    def test_returns_none_when_ffprobe_missing(self):
        with patch("audio_visualizer.ui.mediaProbe._find_ffprobe", return_value=None):
            result = probe_media("/some/file.mp4")
        assert result is None

    def test_returns_none_for_nonexistent_file(self):
        with patch("audio_visualizer.ui.mediaProbe._find_ffprobe", return_value="/usr/bin/ffprobe"):
            result = probe_media("/nonexistent/file.mp4")
        assert result is None

    def test_parses_video_metadata(self, tmp_path):
        probe_output = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "30000/1001",
                    "avg_frame_rate": "30000/1001",
                    "pix_fmt": "yuv420p",
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                },
            ],
            "format": {
                "duration": "120.5",
            },
        }

        dummy_file = tmp_path / "test.mp4"
        dummy_file.touch()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(probe_output)

        with (
            patch("audio_visualizer.ui.mediaProbe._find_ffprobe", return_value="/usr/bin/ffprobe"),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = probe_media(str(dummy_file))

        assert result is not None
        assert result["width"] == 1920
        assert result["height"] == 1080
        assert abs(result["fps"] - 29.97) < 0.1
        assert result["duration_ms"] == 120500
        assert result["has_audio"] is True
        assert result["has_alpha"] is False
        assert result["codec_name"] == "h264"
        assert result["pix_fmt"] == "yuv420p"

    def test_detects_alpha_channel(self, tmp_path):
        probe_output = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "vp9",
                    "width": 1280,
                    "height": 720,
                    "r_frame_rate": "30/1",
                    "avg_frame_rate": "30/1",
                    "pix_fmt": "yuva420p",
                },
            ],
            "format": {
                "duration": "10.0",
            },
        }

        dummy_file = tmp_path / "alpha.webm"
        dummy_file.touch()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(probe_output)

        with (
            patch("audio_visualizer.ui.mediaProbe._find_ffprobe", return_value="/usr/bin/ffprobe"),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = probe_media(str(dummy_file))

        assert result is not None
        assert result["has_alpha"] is True
        assert result["has_audio"] is False

    def test_handles_ffprobe_error(self, tmp_path):
        dummy_file = tmp_path / "bad.mp4"
        dummy_file.touch()

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error"
        mock_result.stdout = ""

        with (
            patch("audio_visualizer.ui.mediaProbe._find_ffprobe", return_value="/usr/bin/ffprobe"),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = probe_media(str(dummy_file))

        assert result is None

    def test_handles_invalid_json(self, tmp_path):
        dummy_file = tmp_path / "bad.mp4"
        dummy_file.touch()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not json"

        with (
            patch("audio_visualizer.ui.mediaProbe._find_ffprobe", return_value="/usr/bin/ffprobe"),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = probe_media(str(dummy_file))

        assert result is None

    def test_handles_timeout(self, tmp_path):
        dummy_file = tmp_path / "slow.mp4"
        dummy_file.touch()

        with (
            patch("audio_visualizer.ui.mediaProbe._find_ffprobe", return_value="/usr/bin/ffprobe"),
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ffprobe", 30)),
        ):
            result = probe_media(str(dummy_file))

        assert result is None

    def test_audio_only_file(self, tmp_path):
        probe_output = {
            "streams": [
                {
                    "codec_type": "audio",
                    "codec_name": "mp3",
                    "duration": "180.0",
                },
            ],
            "format": {
                "duration": "180.0",
            },
        }

        dummy_file = tmp_path / "audio.mp3"
        dummy_file.touch()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(probe_output)

        with (
            patch("audio_visualizer.ui.mediaProbe._find_ffprobe", return_value="/usr/bin/ffprobe"),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = probe_media(str(dummy_file))

        assert result is not None
        assert result["width"] is None
        assert result["height"] is None
        assert result["has_audio"] is True
        assert result["duration_ms"] == 180000

    def test_frame_rate_integer(self, tmp_path):
        probe_output = {
            "streams": [
                {
                    "codec_type": "video",
                    "width": 640,
                    "height": 480,
                    "r_frame_rate": "25/1",
                    "pix_fmt": "yuv420p",
                },
            ],
            "format": {"duration": "5.0"},
        }

        dummy_file = tmp_path / "test.mp4"
        dummy_file.touch()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(probe_output)

        with (
            patch("audio_visualizer.ui.mediaProbe._find_ffprobe", return_value="/usr/bin/ffprobe"),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = probe_media(str(dummy_file))

        assert result is not None
        assert result["fps"] == 25.0


# ------------------------------------------------------------------
# classify_caption_output tests
# ------------------------------------------------------------------


class TestClassifyCaptionOutput:
    """Tests for caption output classification."""

    def test_none_asset_returns_opaque(self):
        assert classify_caption_output(None) == "opaque"

    def test_alpha_and_overlay_ready(self):
        asset = SimpleNamespace(
            has_alpha=True,
            is_overlay_ready=True,
            preferred_for_overlay=False,
            metadata={},
        )
        assert classify_caption_output(asset) == "alpha_ready"

    def test_preferred_with_alpha(self):
        asset = SimpleNamespace(
            has_alpha=True,
            is_overlay_ready=False,
            preferred_for_overlay=True,
            metadata={},
        )
        assert classify_caption_output(asset) == "alpha_ready"

    def test_alpha_only_needs_normalization(self):
        asset = SimpleNamespace(
            has_alpha=True,
            is_overlay_ready=False,
            preferred_for_overlay=False,
            metadata={},
        )
        assert classify_caption_output(asset) == "needs_normalization"

    def test_no_alpha_opaque(self):
        asset = SimpleNamespace(
            has_alpha=False,
            is_overlay_ready=False,
            preferred_for_overlay=False,
            metadata={},
        )
        assert classify_caption_output(asset) == "opaque"

    def test_large_quality_tier(self):
        asset = SimpleNamespace(
            has_alpha=None,
            is_overlay_ready=False,
            preferred_for_overlay=False,
            metadata={"quality_tier": "large"},
        )
        assert classify_caption_output(asset) == "alpha_ready"

    def test_small_quality_tier(self):
        asset = SimpleNamespace(
            has_alpha=None,
            is_overlay_ready=False,
            preferred_for_overlay=False,
            metadata={"quality_tier": "small"},
        )
        assert classify_caption_output(asset) == "needs_normalization"

    def test_medium_quality_tier(self):
        asset = SimpleNamespace(
            has_alpha=None,
            is_overlay_ready=False,
            preferred_for_overlay=False,
            metadata={"quality_tier": "medium"},
        )
        assert classify_caption_output(asset) == "opaque"


# ------------------------------------------------------------------
# check_composition_compatibility tests
# ------------------------------------------------------------------


class TestCompositionCompatibility:
    """Tests for composition compatibility checks."""

    def test_empty_list(self):
        assert check_composition_compatibility([]) == []

    def test_compatible_assets(self):
        a1 = SimpleNamespace(
            display_name="vid1", width=1920, height=1080,
            fps=30.0, duration_ms=10000,
            has_audio=False, source_tab="tab1", role=None,
        )
        a2 = SimpleNamespace(
            display_name="vid2", width=1920, height=1080,
            fps=30.0, duration_ms=10000,
            has_audio=False, source_tab="tab1", role=None,
        )
        warnings = check_composition_compatibility([a1, a2])
        assert warnings == []

    def test_resolution_mismatch(self):
        a1 = SimpleNamespace(
            display_name="hd", width=1920, height=1080,
            fps=30.0, duration_ms=10000,
            has_audio=False, source_tab="tab1", role=None,
        )
        a2 = SimpleNamespace(
            display_name="sd", width=1280, height=720,
            fps=30.0, duration_ms=10000,
            has_audio=False, source_tab="tab1", role=None,
        )
        warnings = check_composition_compatibility([a1, a2])
        assert any("Resolution mismatch" in w for w in warnings)

    def test_fps_mismatch(self):
        a1 = SimpleNamespace(
            display_name="30fps", width=1920, height=1080,
            fps=30.0, duration_ms=10000,
            has_audio=False, source_tab="tab1", role=None,
        )
        a2 = SimpleNamespace(
            display_name="60fps", width=1920, height=1080,
            fps=60.0, duration_ms=10000,
            has_audio=False, source_tab="tab1", role=None,
        )
        warnings = check_composition_compatibility([a1, a2])
        assert any("FPS mismatch" in w for w in warnings)

    def test_audio_visualizer_embedded_audio_warning(self):
        a = SimpleNamespace(
            display_name="viz_out", width=1920, height=1080,
            fps=30.0, duration_ms=10000,
            has_audio=True, source_tab="audio_visualizer", role=None,
        )
        warnings = check_composition_compatibility([a])
        assert any("embedded audio" in w for w in warnings)

    def test_duration_spread_warning(self):
        a1 = SimpleNamespace(
            display_name="short", width=1920, height=1080,
            fps=30.0, duration_ms=5000,
            has_audio=False, source_tab="tab1", role=None,
        )
        a2 = SimpleNamespace(
            display_name="long", width=1920, height=1080,
            fps=30.0, duration_ms=60000,
            has_audio=False, source_tab="tab1", role=None,
        )
        warnings = check_composition_compatibility([a1, a2])
        assert any("duration" in w.lower() for w in warnings)
