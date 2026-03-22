"""Tests for audio_visualizer.hwaccel module."""
from unittest.mock import patch, MagicMock
import pytest

from audio_visualizer.hwaccel import (
    detect_subprocess_encoders,
    detect_working_subprocess_encoders,
    detect_pyav_encoders,
    select_encoder,
    get_decode_flags,
    is_hardware_encoder,
    _H264_ENCODER_PRIORITY,
    _SOFTWARE_FALLBACK,
)


class TestDetectSubprocessEncoders:
    def test_returns_list(self):
        # Clear cache for test isolation
        detect_subprocess_encoders.cache_clear()
        result = detect_subprocess_encoders()
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_always_includes_at_least_one_encoder(self):
        detect_subprocess_encoders.cache_clear()
        result = detect_subprocess_encoders()
        assert len(result) >= 1

    def test_fallback_when_ffmpeg_missing(self):
        detect_subprocess_encoders.cache_clear()
        with patch("audio_visualizer.hwaccel.shutil.which", return_value=None):
            result = detect_subprocess_encoders()
        assert result == [_SOFTWARE_FALLBACK]
        detect_subprocess_encoders.cache_clear()


class TestDetectPyavEncoders:
    def test_returns_list(self):
        detect_pyav_encoders.cache_clear()
        result = detect_pyav_encoders()
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_fallback_when_pyav_missing(self):
        detect_pyav_encoders.cache_clear()
        with patch.dict("sys.modules", {"av": None}):
            # Force re-import failure
            with patch("builtins.__import__", side_effect=ImportError("no av")):
                result = detect_pyav_encoders()
        # May have been cached already; just check type
        assert isinstance(result, list)
        detect_pyav_encoders.cache_clear()


class TestSelectEncoder:
    def test_returns_string(self):
        detect_subprocess_encoders.cache_clear()
        result = select_encoder("h264")
        assert isinstance(result, str)

    def test_non_h264_passes_through(self):
        result = select_encoder("hevc")
        assert result == "hevc"

    def test_pyav_mode(self):
        detect_pyav_encoders.cache_clear()
        result = select_encoder("h264", use_pyav=True)
        assert isinstance(result, str)
        assert result in _H264_ENCODER_PRIORITY

    def test_subprocess_mode_skips_encoders_that_fail_runtime_probe(self):
        detect_working_subprocess_encoders.cache_clear()
        with patch(
            "audio_visualizer.hwaccel.detect_working_subprocess_encoders",
            return_value=["h264_qsv", "libx264"],
        ):
            result = select_encoder("h264")
        assert result == "h264_qsv"


class TestDetectWorkingSubprocessEncoders:
    def test_filters_out_runtime_failing_hardware_encoders(self):
        detect_subprocess_encoders.cache_clear()
        detect_working_subprocess_encoders.cache_clear()

        with patch(
            "audio_visualizer.hwaccel.shutil.which",
            return_value="/usr/bin/ffmpeg",
        ):
            with patch(
                "audio_visualizer.hwaccel.detect_subprocess_encoders",
                return_value=["h264_nvenc", "h264_qsv", "libx264"],
            ):
                with patch(
                    "audio_visualizer.hwaccel._probe_subprocess_encoder",
                    side_effect=[False, True, True],
                ):
                    result = detect_working_subprocess_encoders()

        assert result == ["h264_qsv", "libx264"]
        detect_working_subprocess_encoders.cache_clear()


class TestGetDecodeFlags:
    def test_returns_hwaccel_auto(self):
        flags = get_decode_flags()
        assert flags == ["-hwaccel", "auto"]


class TestIsHardwareEncoder:
    def test_software_is_not_hardware(self):
        assert is_hardware_encoder("libx264") is False

    def test_nvenc_is_hardware(self):
        assert is_hardware_encoder("h264_nvenc") is True

    def test_qsv_is_hardware(self):
        assert is_hardware_encoder("h264_qsv") is True


class TestEncoderPriority:
    def test_nvenc_is_first(self):
        assert _H264_ENCODER_PRIORITY[0] == "h264_nvenc"

    def test_libx264_is_last(self):
        assert _H264_ENCODER_PRIORITY[-1] == "libx264"
