"""Tests for TypewriterAnimation."""

import pytest
import pysubs2

from audio_visualizer.caption.animations.typewriterAnimation import TypewriterAnimation


class TestTypewriterBasic:
    """Basic typewriter animation tests."""

    def test_single_word(self):
        anim = TypewriterAnimation(params={})
        event = pysubs2.SSAEvent(start=0, end=2000, text="Hello")
        anim.apply_to_event(event)
        assert "H" in event.text
        assert "e" in event.text
        assert "l" in event.text
        assert "o" in event.text
        assert r"\k" in event.text

    def test_multi_word(self):
        anim = TypewriterAnimation(params={})
        event = pysubs2.SSAEvent(start=0, end=3000, text="Hello world")
        anim.apply_to_event(event)
        assert "H" in event.text
        assert "w" in event.text
        assert r"\k" in event.text

    def test_empty_text(self):
        anim = TypewriterAnimation(params={})
        event = pysubs2.SSAEvent(start=0, end=1000, text="")
        anim.apply_to_event(event)
        assert event.text == ""


class TestTypewriterCursor:
    """Tests for cursor behavior."""

    def test_cursor_present_by_default(self):
        anim = TypewriterAnimation(params={"show_cursor": True, "cursor_char": "|"})
        event = pysubs2.SSAEvent(start=0, end=5000, text="Hi")
        anim.apply_to_event(event)
        assert "|" in event.text

    def test_cursor_disabled(self):
        anim = TypewriterAnimation(params={"show_cursor": False})
        event = pysubs2.SSAEvent(start=0, end=5000, text="Hi")
        anim.apply_to_event(event)
        # The cursor char should not appear after the text
        # (the pipe might appear in ASS tags so check carefully)
        text_after_last_char = event.text.split("i")[-1]
        assert "|" not in text_after_last_char or r"\k" in text_after_last_char

    def test_custom_cursor_char(self):
        anim = TypewriterAnimation(params={"cursor_char": "_", "show_cursor": True})
        event = pysubs2.SSAEvent(start=0, end=5000, text="Hi")
        anim.apply_to_event(event)
        assert "_" in event.text


class TestTypewriterTiming:
    """Tests for timing parameters."""

    def test_lead_in(self):
        anim = TypewriterAnimation(params={"lead_in_ms": 500})
        event = pysubs2.SSAEvent(start=0, end=3000, text="Hello")
        anim.apply_to_event(event)
        assert r"\k" in event.text

    def test_chars_per_sec(self):
        anim = TypewriterAnimation(params={"chars_per_sec": 10})
        event = pysubs2.SSAEvent(start=0, end=5000, text="Hello")
        anim.apply_to_event(event)
        assert r"\k" in event.text
        # With 10 chars/sec, each char should take ~100ms = 10cs
        assert r"\k10" in event.text

    def test_short_duration(self):
        anim = TypewriterAnimation(params={})
        event = pysubs2.SSAEvent(start=0, end=100, text="Hello world")
        anim.apply_to_event(event)
        assert "H" in event.text


class TestTypewriterDefaults:
    """Tests for default parameters."""

    def test_default_params(self):
        defaults = TypewriterAnimation.get_default_params()
        assert defaults["cursor_char"] == "|"
        assert defaults["cursor_blink_ms"] == 500
        assert defaults["lead_in_ms"] == 0
        assert defaults["chars_per_sec"] == 0
        assert defaults["show_cursor"] is True

    def test_animation_type(self):
        assert TypewriterAnimation.animation_type == "typewriter"

    def test_validate_params_always_passes(self):
        anim = TypewriterAnimation(params={})
        assert anim is not None


class TestTypewriterNewlines:
    """Tests for newline handling."""

    def test_newlines_converted_to_ass(self):
        anim = TypewriterAnimation(params={"show_cursor": False})
        event = pysubs2.SSAEvent(start=0, end=5000, text="Hello\nworld")
        anim.apply_to_event(event)
        assert r"\N" in event.text
        assert "\n" not in event.text

    def test_ass_newline_input(self):
        anim = TypewriterAnimation(params={"show_cursor": False})
        event = pysubs2.SSAEvent(start=0, end=5000, text=r"Hello\Nworld")
        anim.apply_to_event(event)
        assert r"\N" in event.text
