"""
Tests for text wrapping functionality.
"""

import pytest
from PIL import ImageFont

from caption_animator.text.wrapper import wrap_text_to_width


class TestWrapTextToWidth:
    """Test suite for wrap_text_to_width function."""

    def test_no_wrapping_when_max_width_zero(self, mock_font):
        """Test that no wrapping occurs when max_width is 0."""
        text = "This is a very long line that should not be wrapped"
        result = wrap_text_to_width(text, mock_font, 0)
        assert result == text

    def test_no_wrapping_when_max_width_negative(self, mock_font):
        """Test that no wrapping occurs when max_width is negative."""
        text = "This is a very long line that should not be wrapped"
        result = wrap_text_to_width(text, mock_font, -1)
        assert result == text

    def test_single_word_always_fits(self, mock_font):
        """Test that a single word is always returned, even if it exceeds max_width."""
        text = "Supercalifragilisticexpialidocious"
        result = wrap_text_to_width(text, mock_font, 10)
        assert result == text

    def test_wrapping_simple_text(self, mock_font):
        """Test basic wrapping of text that exceeds width."""
        text = "The quick brown fox jumps over the lazy dog"
        # Use a small width to force wrapping
        result = wrap_text_to_width(text, mock_font, 200)

        # Should have multiple lines
        lines = result.split("\n")
        assert len(lines) > 1

        # Each line should not be empty
        for line in lines:
            assert line.strip()

    def test_preserves_existing_line_breaks(self, mock_font):
        """Test that existing line breaks are preserved."""
        text = "Line one\nLine two\nLine three"
        # Use large width so no additional wrapping occurs
        result = wrap_text_to_width(text, mock_font, 1000)

        assert result == text
        lines = result.split("\n")
        assert len(lines) == 3

    def test_empty_string(self, mock_font):
        """Test handling of empty string."""
        result = wrap_text_to_width("", mock_font, 500)
        assert result == ""

    def test_whitespace_normalization(self, mock_font):
        """Test that extra whitespace is normalized."""
        text = "This  has   extra    spaces"
        result = wrap_text_to_width(text, mock_font, 1000)
        # Should normalize to single spaces
        assert "  " not in result

    def test_preserves_empty_lines(self, mock_font):
        """Test that empty lines in input are preserved."""
        text = "Line one\n\nLine three"
        result = wrap_text_to_width(text, mock_font, 1000)

        lines = result.split("\n")
        assert len(lines) == 3
        assert lines[0] == "Line one"
        assert lines[1] == ""
        assert lines[2] == "Line three"

    def test_wrapping_with_existing_breaks(self, mock_font):
        """Test wrapping when input already has line breaks."""
        text = "This is a very long line that needs wrapping\nAnd this is another long line"
        result = wrap_text_to_width(text, mock_font, 200)

        # Should have more than 2 lines (original 2 plus wrapped lines)
        lines = result.split("\n")
        assert len(lines) >= 2

    def test_each_line_fits_width(self, mock_font):
        """Test that each output line fits within max_width."""
        text = "The quick brown fox jumps over the lazy dog"
        max_width = 250
        result = wrap_text_to_width(text, mock_font, max_width)

        # Each line should fit within max_width
        for line in result.split("\n"):
            if line.strip():  # Skip empty lines
                line_width = mock_font.getlength(line)
                assert line_width <= max_width, f"Line '{line}' exceeds max_width"

    def test_multiple_paragraphs(self, mock_font):
        """Test wrapping text with multiple paragraphs."""
        text = "First paragraph text\n\nSecond paragraph text\n\nThird paragraph"
        result = wrap_text_to_width(text, mock_font, 1000)

        lines = result.split("\n")
        # Should preserve the empty lines between paragraphs
        assert "" in lines

    def test_strips_leading_trailing_whitespace_per_line(self, mock_font):
        """Test that leading/trailing whitespace is stripped from each line."""
        text = "  Line with spaces  \n  Another line  "
        result = wrap_text_to_width(text, mock_font, 1000)

        for line in result.split("\n"):
            if line:  # Skip empty lines
                assert line == line.strip()
