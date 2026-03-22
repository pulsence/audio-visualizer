"""Tests for audio_visualizer.capabilities module."""
import importlib

from audio_visualizer.capabilities import (
    has_opengl,
    has_sounddevice,
    has_training_stack,
    has_cuda,
    capability_summary,
)


class TestCapabilities:
    def test_has_opengl_returns_bool(self):
        result = has_opengl()
        assert isinstance(result, bool)

    def test_has_sounddevice_returns_bool(self):
        result = has_sounddevice()
        assert isinstance(result, bool)

    def test_has_training_stack_returns_bool(self):
        result = has_training_stack()
        assert isinstance(result, bool)

    def test_has_cuda_returns_bool(self):
        result = has_cuda()
        assert isinstance(result, bool)

    def test_capability_summary_returns_dict(self):
        summary = capability_summary()
        assert isinstance(summary, dict)
        assert "opengl" in summary
        assert "sounddevice" in summary
        assert "training_stack" in summary
        assert "cuda" in summary
        for v in summary.values():
            assert isinstance(v, bool)

    def test_cached_results_are_stable(self):
        """Calling twice returns the same result (cache)."""
        r1 = has_opengl()
        r2 = has_opengl()
        assert r1 == r2
