"""Tests for WordHighlightAnimation."""

import pytest
import pysubs2

from audio_visualizer.caption.animations.wordHighlightAnimation import (
    WordHighlightAnimation,
)


class TestWordHighlightBasic:
    """Basic word highlight animation tests."""

    def test_single_word(self):
        anim = WordHighlightAnimation(params={"mode": "even"})
        event = pysubs2.SSAEvent(start=0, end=2000, text="Hello")
        anim.apply_to_event(event)
        assert "Hello" in event.text
        assert r"\kf" in event.text

    def test_multiple_words(self):
        anim = WordHighlightAnimation(params={"mode": "even"})
        event = pysubs2.SSAEvent(start=0, end=3000, text="Hello world today")
        anim.apply_to_event(event)
        assert "Hello" in event.text
        assert "world" in event.text
        assert "today" in event.text
        assert r"\kf" in event.text

    def test_empty_text(self):
        anim = WordHighlightAnimation(params={"mode": "even"})
        event = pysubs2.SSAEvent(start=0, end=1000, text="")
        anim.apply_to_event(event)
        assert event.text == ""

    def test_highlight_color_in_output(self):
        anim = WordHighlightAnimation(
            params={"mode": "even", "highlight_color": "#FFFF00"}
        )
        event = pysubs2.SSAEvent(start=0, end=2000, text="Hello world")
        anim.apply_to_event(event)
        # #FFFF00 -> ASS &H00FFFF
        assert r"\1c&H00FFFF" in event.text


class TestWordHighlightTimingModes:
    """Tests for timing mode behavior."""

    def test_even_mode(self):
        anim = WordHighlightAnimation(params={"mode": "even"})
        event = pysubs2.SSAEvent(start=0, end=2000, text="short longword")
        anim.apply_to_event(event)
        assert r"\kf" in event.text

    def test_weighted_mode(self):
        anim = WordHighlightAnimation(params={"mode": "weighted"})
        event = pysubs2.SSAEvent(start=0, end=3000, text="Hi supercalifragilistic")
        anim.apply_to_event(event)
        assert r"\kf" in event.text
        assert "Hi" in event.text
        assert "supercalifragilistic" in event.text

    def test_word_level_mode_with_timing(self):
        word_timing = [
            {"start": 0.0, "end": 0.5, "text": "Hello"},
            {"start": 0.5, "end": 1.0, "text": "world"},
        ]
        anim = WordHighlightAnimation(params={"mode": "word_level"})
        event = pysubs2.SSAEvent(start=0, end=1000, text="Hello world")
        anim.apply_to_event(event, word_timing=word_timing)
        assert "Hello" in event.text
        assert "world" in event.text

    def test_word_level_falls_back_to_even(self):
        anim = WordHighlightAnimation(params={"mode": "word_level"})
        event = pysubs2.SSAEvent(start=0, end=2000, text="Hello world")
        # No word_timing provided — should fall back to even
        anim.apply_to_event(event)
        assert r"\kf" in event.text


class TestWordHighlightEmphasis:
    """Tests for ==highlight== marker emphasis."""

    def test_emphasis_word_gets_emphasis_color(self):
        anim = WordHighlightAnimation(
            params={"mode": "even", "emphasis_color": "#FF8800"}
        )
        event = pysubs2.SSAEvent(start=0, end=2000, text="Hello ==world==")
        anim.apply_to_event(event)
        # #FF8800 -> ASS &H0088FF
        assert r"\1c&H0088FF" in event.text

    def test_emphasis_word_gets_emphasis_scale(self):
        anim = WordHighlightAnimation(
            params={"mode": "even", "emphasis_scale": 120}
        )
        event = pysubs2.SSAEvent(start=0, end=2000, text="Hello ==world==")
        anim.apply_to_event(event)
        assert r"\fscx120" in event.text


class TestWordHighlightDefaults:
    """Tests for default parameters."""

    def test_default_params(self):
        defaults = WordHighlightAnimation.get_default_params()
        assert defaults["mode"] == "even"
        assert defaults["highlight_color"] == "#FFFF00"
        assert defaults["emphasis_color"] == "#FF8800"
        assert defaults["highlight_scale"] == 110
        assert defaults["emphasis_scale"] == 120

    def test_animation_type(self):
        assert WordHighlightAnimation.animation_type == "word_highlight"

    def test_validate_params_always_passes(self):
        # Should not raise
        anim = WordHighlightAnimation(params={})
        assert anim is not None


class TestWordHighlightNewlines:
    """Tests for newline handling."""

    def test_multiline_text(self):
        anim = WordHighlightAnimation(params={"mode": "even"})
        event = pysubs2.SSAEvent(start=0, end=3000, text="First line\nSecond line")
        anim.apply_to_event(event)
        assert r"\N" in event.text
        assert "\n" not in event.text

    def test_ass_newline_escape(self):
        anim = WordHighlightAnimation(params={"mode": "even"})
        event = pysubs2.SSAEvent(start=0, end=3000, text=r"First\NSecond")
        anim.apply_to_event(event)
        assert r"\N" in event.text
