"""
Tests for text measurement functionality.
"""

import pytest
from PIL import ImageFont

from caption_animator.text.measurement import measure_multiline, measure_single_line


class TestMeasureSingleLine:
    """Test suite for measure_single_line function."""

    def test_empty_string(self, mock_font):
        """Test measurement of empty string."""
        width = measure_single_line("", mock_font)
        assert width == 0

    def test_single_word(self, mock_font):
        """Test measurement of single word."""
        width = measure_single_line("Hello", mock_font)
        assert width > 0
        assert isinstance(width, int)

    def test_multiple_words(self, mock_font):
        """Test measurement of multiple words."""
        width = measure_single_line("Hello World", mock_font)
        # Should be wider than just "Hello"
        hello_width = measure_single_line("Hello", mock_font)
        assert width > hello_width

    def test_longer_text_wider(self, mock_font):
        """Test that longer text produces wider measurements."""
        short = measure_single_line("Hi", mock_font)
        long = measure_single_line("This is a longer sentence", mock_font)
        assert long > short

    def test_spaces_contribute_to_width(self, mock_font):
        """Test that spaces contribute to width."""
        no_space = measure_single_line("HelloWorld", mock_font)
        with_space = measure_single_line("Hello World", mock_font)
        assert with_space >= no_space


class TestMeasureMultiline:
    """Test suite for measure_multiline function."""

    def test_empty_string(self, mock_font):
        """Test measurement of empty string."""
        width, height, line_count = measure_multiline("", mock_font, 0)
        assert width == 0
        assert height > 0  # Height is based on font metrics
        assert line_count == 1  # Empty string counts as 1 line

    def test_single_line(self, mock_font):
        """Test measurement of single line."""
        width, height, line_count = measure_multiline("Hello", mock_font, 0)
        assert width > 0
        assert height > 0
        assert line_count == 1
        assert isinstance(width, int)
        assert isinstance(height, int)

    def test_two_lines(self, mock_font):
        """Test measurement of two lines."""
        width, height, line_count = measure_multiline("Hello\nWorld", mock_font, 0)
        assert width > 0
        assert height > 0
        assert line_count == 2

    def test_three_lines(self, mock_font):
        """Test measurement of three lines."""
        text = "Line one\nLine two\nLine three"
        width, height, line_count = measure_multiline(text, mock_font, 0)
        assert line_count == 3

    def test_max_width_used(self, mock_font):
        """Test that width is the maximum of all lines."""
        # Second line is intentionally longer
        text = "Short\nThis is a much longer line\nShort again"
        width, height, line_count = measure_multiline(text, mock_font, 0)

        # Measure individual lines
        short_width = measure_single_line("Short", mock_font)
        long_width = measure_single_line("This is a much longer line", mock_font)

        # Width should be the longest line
        assert width == long_width
        assert width > short_width

    def test_line_spacing_affects_height(self, mock_font):
        """Test that line spacing increases total height."""
        text = "Line one\nLine two"
        width1, height1, _ = measure_multiline(text, mock_font, 0)
        width2, height2, _ = measure_multiline(text, mock_font, 10)

        # Width should be the same
        assert width1 == width2
        # Height with spacing should be larger
        assert height2 > height1
        assert height2 == height1 + 10

    def test_more_lines_more_spacing(self, mock_font):
        """Test that more lines means more spacing is added."""
        two_lines = "Line one\nLine two"
        three_lines = "Line one\nLine two\nLine three"

        _, height2, _ = measure_multiline(two_lines, mock_font, 10)
        _, height3, _ = measure_multiline(three_lines, mock_font, 10)

        # Three lines should have 20px more spacing than two lines (2 gaps vs 1 gap)
        ascent, descent = mock_font.getmetrics()
        line_height = ascent + descent

        # Difference should be one line height plus one spacing
        expected_diff = line_height + 10
        assert abs(height3 - height2 - expected_diff) < 2  # Allow small rounding error

    def test_empty_line_in_middle(self, mock_font):
        """Test handling of empty line in the middle."""
        text = "Line one\n\nLine three"
        width, height, line_count = measure_multiline(text, mock_font, 0)

        assert line_count == 3
        # Width should be max of non-empty lines
        assert width > 0

    def test_trailing_newline(self, mock_font):
        """Test handling of trailing newline."""
        text = "Line one\n"
        width, height, line_count = measure_multiline(text, mock_font, 0)

        # Should count as 2 lines (one with text, one empty)
        assert line_count == 2

    def test_multiple_trailing_newlines(self, mock_font):
        """Test handling of multiple trailing newlines."""
        text = "Line one\n\n"
        width, height, line_count = measure_multiline(text, mock_font, 0)

        # Should count as 3 lines
        assert line_count == 3

    def test_height_scales_with_line_count(self, mock_font):
        """Test that height increases with line count."""
        one_line = "Line"
        two_lines = "Line\nLine"
        three_lines = "Line\nLine\nLine"

        _, h1, _ = measure_multiline(one_line, mock_font, 0)
        _, h2, _ = measure_multiline(two_lines, mock_font, 0)
        _, h3, _ = measure_multiline(three_lines, mock_font, 0)

        assert h2 > h1
        assert h3 > h2

    def test_negative_line_spacing_handled(self, mock_font):
        """Test that negative line spacing is handled gracefully."""
        text = "Line one\nLine two"
        # Negative spacing should make height smaller
        _, height_zero, _ = measure_multiline(text, mock_font, 0)
        _, height_neg, _ = measure_multiline(text, mock_font, -5)

        assert height_neg < height_zero
