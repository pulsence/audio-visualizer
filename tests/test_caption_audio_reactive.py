"""Tests for audio-reactive caption analysis and animations."""

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock

from audio_visualizer.caption.core.audioReactive import (
    AudioReactiveAnalysis,
    analyze_audio,
    make_cache_key,
)


# ------------------------------------------------------------------
# AudioReactiveAnalysis dataclass
# ------------------------------------------------------------------


class TestAudioReactiveAnalysis:
    def test_default_construction(self):
        analysis = AudioReactiveAnalysis()
        assert analysis.smoothed_amplitude == []
        assert analysis.peak_markers == []
        assert analysis.emphasis_markers == []
        assert analysis.bpm_estimate == 0.0
        assert analysis.frame_count == 0
        assert analysis.fps == 30.0
        assert analysis.duration_ms == 0

    def test_construction_with_values(self):
        analysis = AudioReactiveAnalysis(
            smoothed_amplitude=[0.1, 0.5, 0.9],
            peak_markers=[2],
            emphasis_markers=[1, 2],
            bpm_estimate=120.0,
            frame_count=3,
            fps=24.0,
            duration_ms=1000,
        )
        assert len(analysis.smoothed_amplitude) == 3
        assert analysis.peak_markers == [2]
        assert analysis.bpm_estimate == 120.0
        assert analysis.frame_count == 3
        assert analysis.fps == 24.0
        assert analysis.duration_ms == 1000


# ------------------------------------------------------------------
# Cache key generation
# ------------------------------------------------------------------


class TestMakeCacheKey:
    def test_cache_key_structure(self):
        key = make_cache_key(Path("/tmp/audio.mp3"), 30.0, 5000)
        assert isinstance(key, tuple)
        assert len(key) == 3
        assert Path(key[0]) == Path("/tmp/audio.mp3")
        assert key[1] == "audio_reactive"
        assert key[2] == "30.0_5000"

    def test_cache_key_uniqueness(self):
        key1 = make_cache_key(Path("/tmp/a.mp3"), 30.0, 5000)
        key2 = make_cache_key(Path("/tmp/b.mp3"), 30.0, 5000)
        key3 = make_cache_key(Path("/tmp/a.mp3"), 60.0, 5000)
        assert key1 != key2
        assert key1 != key3


# ------------------------------------------------------------------
# analyze_audio function (mocked librosa)
# ------------------------------------------------------------------


class TestAnalyzeAudioWithMock:
    def test_analyze_with_mocked_librosa(self):
        """Test that analyze_audio produces reasonable results with mock audio data."""
        import librosa as _librosa

        sr = 22050
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        y = np.sin(2 * np.pi * 440 * t).astype(np.float32)

        mock_rms = np.array([[0.1, 0.3, 0.8, 0.5, 0.2, 0.9, 0.4, 0.1, 0.3, 0.7]])

        with (
            patch.object(_librosa, "load", return_value=(y, sr)),
            patch.object(_librosa.feature, "rms", return_value=mock_rms),
            patch.object(_librosa.beat, "beat_track", return_value=(np.array([120.0]), np.array([]))),
        ):
            result = analyze_audio(Path("/tmp/test.mp3"), fps=30.0, duration_ms=1000)

        assert isinstance(result, AudioReactiveAnalysis)
        assert result.fps == 30.0
        assert result.duration_ms == 1000
        assert len(result.smoothed_amplitude) > 0
        assert result.bpm_estimate == 120.0

    def test_analyze_empty_audio(self):
        """Test with empty audio returns empty analysis."""
        import librosa as _librosa

        y = np.array([], dtype=np.float32)

        with patch.object(_librosa, "load", return_value=(y, 22050)):
            result = analyze_audio(Path("/tmp/empty.mp3"), fps=30.0)

        assert isinstance(result, AudioReactiveAnalysis)
        assert result.frame_count == 0

    def test_analyze_returns_analysis_type(self):
        """Test that analyze_audio always returns AudioReactiveAnalysis."""
        import librosa as _librosa

        sr = 22050
        y = np.zeros(sr, dtype=np.float32)  # 1 second of silence
        rms_data = np.array([[0.1, 0.2, 0.3]])

        with (
            patch.object(_librosa, "load", return_value=(y, sr)),
            patch.object(_librosa.feature, "rms", return_value=rms_data),
            patch.object(_librosa.beat, "beat_track", return_value=(np.array([0.0]), np.array([]))),
        ):
            result = analyze_audio(Path("/tmp/test.mp3"), fps=30.0, duration_ms=1000)

        assert isinstance(result, AudioReactiveAnalysis)
        assert result.fps == 30.0

    def test_peak_detection(self):
        """Test that peaks are detected in amplitude data."""
        import librosa as _librosa

        sr = 22050
        y = np.zeros(sr, dtype=np.float32)
        rms_data = np.array([[0.1, 0.1, 0.1, 0.9, 0.1, 0.1, 0.1, 0.1, 0.9, 0.1]])

        with (
            patch.object(_librosa, "load", return_value=(y, sr)),
            patch.object(_librosa.feature, "rms", return_value=rms_data),
            patch.object(_librosa.beat, "beat_track", return_value=(np.array([120.0]), np.array([]))),
        ):
            result = analyze_audio(Path("/tmp/test.mp3"), fps=10.0, duration_ms=1000)

        assert isinstance(result, AudioReactiveAnalysis)
        assert result.frame_count == 10


# ------------------------------------------------------------------
# Audio-reactive animation tests
# ------------------------------------------------------------------


class TestPulseAnimation:
    def test_pulse_registration(self):
        from audio_visualizer.caption.animations import AnimationRegistry
        assert "pulse" in AnimationRegistry.list_types()

    def test_pulse_default_params(self):
        from audio_visualizer.caption.animations import AnimationRegistry
        defaults = AnimationRegistry.get_defaults("pulse")
        assert "in_ms" in defaults
        assert "out_ms" in defaults
        assert "min_scale" in defaults
        assert "max_scale" in defaults

    def test_pulse_create(self):
        from audio_visualizer.caption.animations import AnimationRegistry
        anim = AnimationRegistry.create("pulse", {"in_ms": 150, "out_ms": 120})
        assert anim.animation_type == "pulse"

    def test_pulse_with_amplitude(self):
        from audio_visualizer.caption.animations import AnimationRegistry
        anim = AnimationRegistry.create(
            "pulse",
            {"in_ms": 150, "out_ms": 120, "min_scale": 100, "max_scale": 115},
        )
        override = anim.generate_ass_override({"amplitude": 1.0})
        assert "\\fscx" in override
        assert "\\fscy" in override

    def test_pulse_without_context(self):
        from audio_visualizer.caption.animations import AnimationRegistry
        anim = AnimationRegistry.create("pulse", {"in_ms": 150, "out_ms": 120})
        override = anim.generate_ass_override()
        assert "\\fscx" in override


class TestBeatPopAnimation:
    def test_beat_pop_registration(self):
        from audio_visualizer.caption.animations import AnimationRegistry
        assert "beat_pop" in AnimationRegistry.list_types()

    def test_beat_pop_default_params(self):
        from audio_visualizer.caption.animations import AnimationRegistry
        defaults = AnimationRegistry.get_defaults("beat_pop")
        assert "in_ms" in defaults
        assert "out_ms" in defaults
        assert "pop_scale" in defaults

    def test_beat_pop_create(self):
        from audio_visualizer.caption.animations import AnimationRegistry
        anim = AnimationRegistry.create("beat_pop", {"in_ms": 100, "out_ms": 120})
        assert anim.animation_type == "beat_pop"

    def test_beat_pop_with_amplitude(self):
        from audio_visualizer.caption.animations import AnimationRegistry
        anim = AnimationRegistry.create(
            "beat_pop",
            {"in_ms": 100, "out_ms": 120, "pop_scale": 125, "settle_scale": 100},
        )
        override_low = anim.generate_ass_override({"amplitude": 0.0})
        override_high = anim.generate_ass_override({"amplitude": 1.0})
        # Both should have scale tags
        assert "\\fscx" in override_low
        assert "\\fscx" in override_high


class TestEmphasisGlowAnimation:
    def test_emphasis_glow_registration(self):
        from audio_visualizer.caption.animations import AnimationRegistry
        assert "emphasis_glow" in AnimationRegistry.list_types()

    def test_emphasis_glow_default_params(self):
        from audio_visualizer.caption.animations import AnimationRegistry
        defaults = AnimationRegistry.get_defaults("emphasis_glow")
        assert "in_ms" in defaults
        assert "out_ms" in defaults
        assert "min_blur" in defaults
        assert "max_blur" in defaults

    def test_emphasis_glow_create(self):
        from audio_visualizer.caption.animations import AnimationRegistry
        anim = AnimationRegistry.create("emphasis_glow", {"in_ms": 200, "out_ms": 120})
        assert anim.animation_type == "emphasis_glow"

    def test_emphasis_glow_with_amplitude(self):
        from audio_visualizer.caption.animations import AnimationRegistry
        anim = AnimationRegistry.create(
            "emphasis_glow",
            {"in_ms": 200, "out_ms": 120, "min_blur": 0, "max_blur": 6},
        )
        override = anim.generate_ass_override({"amplitude": 0.8})
        assert "\\blur" in override

    def test_emphasis_glow_without_context(self):
        from audio_visualizer.caption.animations import AnimationRegistry
        anim = AnimationRegistry.create("emphasis_glow", {"in_ms": 200, "out_ms": 120})
        override = anim.generate_ass_override()
        assert "\\blur" in override


# ------------------------------------------------------------------
# Session context cache integration
# ------------------------------------------------------------------


class TestAudioReactiveCacheIntegration:
    def test_store_and_retrieve_analysis(self):
        from audio_visualizer.ui.workspaceContext import WorkspaceContext

        ctx = WorkspaceContext()
        analysis = AudioReactiveAnalysis(
            smoothed_amplitude=[0.5, 0.8, 0.3],
            peak_markers=[1],
            bpm_estimate=120.0,
            frame_count=3,
            fps=30.0,
            duration_ms=100,
        )

        key = make_cache_key(Path("/tmp/audio.mp3"), 30.0, 100)
        ctx.store_analysis(key, analysis)

        cached = ctx.get_analysis(key)
        assert cached is analysis
        assert cached.smoothed_amplitude == [0.5, 0.8, 0.3]
        assert cached.bpm_estimate == 120.0

    def test_cache_miss_returns_none(self):
        from audio_visualizer.ui.workspaceContext import WorkspaceContext

        ctx = WorkspaceContext()
        key = make_cache_key(Path("/tmp/nonexistent.mp3"), 30.0, 0)
        assert ctx.get_analysis(key) is None
