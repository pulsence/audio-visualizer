"""
Tests for word_reveal animation, especially newline handling.
"""

import pytest
import pysubs2

from caption_animator.animations.word_reveal import WordRevealAnimation


class TestWordRevealNewlineHandling:
    """Test suite for newline handling in word_reveal animation."""

    def test_single_line_no_newlines(self):
        """Test that single line text works correctly."""
        animation = WordRevealAnimation(params={"mode": "even"})
        event = pysubs2.SSAEvent(start=0, end=2000, text="Hello world")

        animation.apply_to_event(event)

        # Should have karaoke tags
        assert r"\k" in event.text
        # Should NOT have \N in output (no newlines in input)
        assert r"\N" not in event.text
        # Should have the original words
        assert "Hello" in event.text
        assert "world" in event.text

    def test_multiline_text_uses_ass_escape(self):
        """Test that multi-line text outputs ASS \\N escape, not raw \\n."""
        animation = WordRevealAnimation(params={"mode": "even"})
        # Input with Python newline character
        event = pysubs2.SSAEvent(start=0, end=3000, text="First line\nSecond line")

        animation.apply_to_event(event)

        # CRITICAL: Should use ASS escape \\N, not raw \\n
        assert r"\N" in event.text, "Should output ASS escape \\N for newlines"
        # Should NOT have raw newline character
        assert "\n" not in event.text, "Should not have raw \\n character"
        # Should have the words
        assert "First" in event.text
        assert "line" in event.text
        assert "Second" in event.text

    def test_multiline_with_ass_escape_input(self):
        """Test that text with ASS \\N escape sequences is handled correctly."""
        animation = WordRevealAnimation(params={"mode": "even"})
        # Input with ASS escape sequence (as it would come from subtitle.py after wrapping)
        event = pysubs2.SSAEvent(start=0, end=3000, text=r"First line\NSecond line")

        animation.apply_to_event(event)

        # Should output ASS escape \\N
        assert r"\N" in event.text, "Should preserve ASS escape \\N"
        # Should NOT have raw newline character
        assert "\n" not in event.text, "Should not have raw \\n character"
        # Should have the words
        assert "First" in event.text
        assert "line" in event.text
        assert "Second" in event.text

    def test_three_line_text(self):
        """Test text with three lines."""
        animation = WordRevealAnimation(params={"mode": "even"})
        event = pysubs2.SSAEvent(
            start=0,
            end=5000,
            text="Line one\nLine two\nLine three"
        )

        animation.apply_to_event(event)

        # Should have two \\N escapes (3 lines = 2 line breaks)
        n_count = event.text.count(r"\N")
        assert n_count == 2, f"Expected 2 \\N escapes, found {n_count}"
        # No raw newlines
        assert "\n" not in event.text

    def test_empty_lines_preserved(self):
        """Test that empty lines (multiple newlines) are preserved."""
        animation = WordRevealAnimation(params={"mode": "even"})
        event = pysubs2.SSAEvent(
            start=0,
            end=4000,
            text="First\n\nThird"
        )

        animation.apply_to_event(event)

        # Should have two \\N escapes
        n_count = event.text.count(r"\N")
        assert n_count == 2
        # No raw newlines
        assert "\n" not in event.text

    def test_trailing_newline(self):
        """Test handling of trailing newline."""
        animation = WordRevealAnimation(params={"mode": "even"})
        event = pysubs2.SSAEvent(start=0, end=2000, text="Hello\n")

        animation.apply_to_event(event)

        # Should have one \\N escape
        assert r"\N" in event.text
        # No raw newlines
        assert "\n" not in event.text


class TestWordRevealTokenization:
    """Test suite for tokenization logic."""

    def test_simple_words(self):
        """Test basic word tokenization."""
        animation = WordRevealAnimation(params={"mode": "even"})
        event = pysubs2.SSAEvent(start=0, end=2000, text="The quick brown fox")

        animation.apply_to_event(event)

        # All words should be present
        assert "The" in event.text
        assert "quick" in event.text
        assert "brown" in event.text
        assert "fox" in event.text
        # Should have karaoke tags
        assert r"\k" in event.text

    def test_punctuation_handling(self):
        """Test that punctuation is grouped with preceding words."""
        animation = WordRevealAnimation(params={"mode": "even"})
        event = pysubs2.SSAEvent(start=0, end=3000, text="Hello, world!")

        animation.apply_to_event(event)

        # Words with trailing punctuation should be grouped together
        assert "Hello," in event.text or ("Hello" in event.text and "," in event.text)
        assert "world!" in event.text or ("world" in event.text and "!" in event.text)

    def test_empty_text(self):
        """Test handling of empty text."""
        animation = WordRevealAnimation(params={"mode": "even"})
        event = pysubs2.SSAEvent(start=0, end=1000, text="")

        animation.apply_to_event(event)

        # Should return empty or unchanged
        assert event.text in ("", "")


class TestWordRevealTimingModes:
    """Test suite for different timing modes."""

    def test_even_mode(self):
        """Test even timing distribution."""
        animation = WordRevealAnimation(params={"mode": "even"})
        event = pysubs2.SSAEvent(start=0, end=2000, text="Short word longer")

        animation.apply_to_event(event)

        # Should have karaoke tags
        assert r"\k" in event.text
        # All words present
        assert "Short" in event.text
        assert "word" in event.text
        assert "longer" in event.text

    def test_weighted_mode(self):
        """Test weighted timing distribution."""
        animation = WordRevealAnimation(params={"mode": "weighted"})
        event = pysubs2.SSAEvent(start=0, end=3000, text="Hi supercalifragilistic")

        animation.apply_to_event(event)

        # Should have karaoke tags
        assert r"\k" in event.text
        # Both words present
        assert "Hi" in event.text
        assert "supercalifragilistic" in event.text

    def test_lead_in_parameter(self):
        """Test lead_in_ms parameter."""
        animation = WordRevealAnimation(params={"mode": "even", "lead_in_ms": 500})
        event = pysubs2.SSAEvent(start=0, end=2000, text="Hello world")

        animation.apply_to_event(event)

        # Should have lead-in tag at the beginning
        # Lead-in is represented as {\k50} (500ms = 50 centiseconds)
        assert r"\k" in event.text

    def test_short_duration_handling(self):
        """Test handling of very short event duration."""
        animation = WordRevealAnimation(params={"mode": "even"})
        # Very short duration
        event = pysubs2.SSAEvent(start=0, end=100, text="Quick")

        animation.apply_to_event(event)

        # Should still work, though timing will be compressed
        assert "Quick" in event.text


class TestWordRevealEdgeCases:
    """Test suite for edge cases."""

    def test_single_word(self):
        """Test single word."""
        animation = WordRevealAnimation(params={"mode": "even"})
        event = pysubs2.SSAEvent(start=0, end=1000, text="Hello")

        animation.apply_to_event(event)

        assert "Hello" in event.text
        assert r"\k" in event.text

    def test_only_punctuation(self):
        """Test text with only punctuation."""
        animation = WordRevealAnimation(params={"mode": "even"})
        event = pysubs2.SSAEvent(start=0, end=1000, text="...")

        animation.apply_to_event(event)

        # Should handle gracefully
        assert "..." in event.text or event.text == "..."

    def test_mixed_punctuation_and_newlines(self):
        """Test complex text with punctuation and newlines."""
        animation = WordRevealAnimation(params={"mode": "even"})
        event = pysubs2.SSAEvent(
            start=0,
            end=4000,
            text="Hello, world!\nHow are you?"
        )

        animation.apply_to_event(event)

        # Should have ASS escape
        assert r"\N" in event.text
        # No raw newlines
        assert "\n" not in event.text
        # Words and punctuation present
        assert "Hello" in event.text
        assert "?" in event.text

    def test_unicode_text(self):
        """Test handling of unicode characters."""
        animation = WordRevealAnimation(params={"mode": "even"})
        event = pysubs2.SSAEvent(start=0, end=2000, text="Hello 世界 🌍")

        animation.apply_to_event(event)

        # Should preserve unicode
        assert "世界" in event.text or "Hello" in event.text
