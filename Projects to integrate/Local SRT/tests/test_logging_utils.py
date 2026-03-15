"""Tests for the logging_utils module."""
from local_srt.logging_utils import format_duration


class TestFormatDuration:
    """Tests for format_duration function."""

    def test_format_duration_seconds(self):
        assert format_duration(45) == "0:45"
        assert format_duration(5) == "0:05"

    def test_format_duration_minutes(self):
        assert format_duration(90) == "1:30"
        assert format_duration(600) == "10:00"

    def test_format_duration_hours(self):
        assert format_duration(3600) == "1:00:00"
        assert format_duration(3661) == "1:01:01"
        assert format_duration(7325) == "2:02:05"

    def test_format_duration_zero(self):
        assert format_duration(0) == "0:00"

    def test_format_duration_negative(self):
        assert format_duration(-10) == "0:00"

    def test_format_duration_float(self):
        assert format_duration(45.7) == "0:45"
        assert format_duration(90.9) == "1:30"

    def test_format_duration_large_hours(self):
        assert format_duration(36000) == "10:00:00"

    def test_format_duration_all_components(self):
        assert format_duration(8130) == "2:15:30"
