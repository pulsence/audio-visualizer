"""Tests for animation registry — verify all animations registered (Phase 10)."""

from audio_visualizer.caption.animations import AnimationRegistry


class TestAnimationRegistryPhase10:
    """Verify new Phase 10 animations are registered alongside existing ones."""

    def test_existing_animations_still_registered(self):
        types = AnimationRegistry.list_types()
        assert "fade" in types
        assert "slide_up" in types
        assert "scale_settle" in types
        assert "blur_settle" in types
        assert "word_reveal" in types
        assert "pulse" in types
        assert "beat_pop" in types
        assert "emphasis_glow" in types

    def test_word_highlight_registered(self):
        types = AnimationRegistry.list_types()
        assert "word_highlight" in types

    def test_typewriter_registered(self):
        types = AnimationRegistry.list_types()
        assert "typewriter" in types

    def test_create_word_highlight(self):
        anim = AnimationRegistry.create("word_highlight", {"mode": "even"})
        assert anim.animation_type == "word_highlight"

    def test_create_typewriter(self):
        anim = AnimationRegistry.create("typewriter", {})
        assert anim.animation_type == "typewriter"

    def test_get_defaults_word_highlight(self):
        defaults = AnimationRegistry.get_defaults("word_highlight")
        assert "mode" in defaults
        assert "highlight_color" in defaults

    def test_get_defaults_typewriter(self):
        defaults = AnimationRegistry.get_defaults("typewriter")
        assert "cursor_char" in defaults
        assert "cursor_blink_ms" in defaults

    def test_total_animation_count(self):
        """Should have at least 10 animations registered."""
        types = AnimationRegistry.list_types()
        assert len(types) >= 10
