"""Tests for the canonical timeline evaluation contract (evaluation.py)."""

import pytest

from audio_visualizer.ui.tabs.renderComposition.evaluation import (
    AudioLayerEval,
    VisualLayerEval,
    audio_needs_input_loop,
    compute_composition_duration_ms,
    evaluate_audio_layer,
    evaluate_visual_layer,
    visual_needs_input_loop,
)
from audio_visualizer.ui.tabs.renderComposition.model import (
    CompositionAudioLayer,
    CompositionLayer,
    CompositionModel,
)


# ------------------------------------------------------------------
# evaluate_visual_layer
# ------------------------------------------------------------------


class TestEvaluateVisualLayer:
    def test_before_start_is_inactive(self):
        layer = CompositionLayer(start_ms=1000, end_ms=5000, source_duration_ms=4000)
        result = evaluate_visual_layer(layer, 500)
        assert result.is_active is False
        assert result.source_time_ms is None

    def test_after_end_is_inactive(self):
        layer = CompositionLayer(start_ms=1000, end_ms=5000, source_duration_ms=4000)
        result = evaluate_visual_layer(layer, 5000)
        assert result.is_active is False
        assert result.source_time_ms is None

    def test_within_window_returns_offset(self):
        layer = CompositionLayer(start_ms=1000, end_ms=5000, source_duration_ms=4000)
        result = evaluate_visual_layer(layer, 3000)
        assert result.is_active is True
        assert result.source_time_ms == 2000  # 3000 - 1000
        assert result.is_looping is False

    def test_at_start_boundary(self):
        layer = CompositionLayer(start_ms=1000, end_ms=5000, source_duration_ms=4000)
        result = evaluate_visual_layer(layer, 1000)
        assert result.is_active is True
        assert result.source_time_ms == 0

    def test_zero_start(self):
        layer = CompositionLayer(start_ms=0, end_ms=5000, source_duration_ms=5000)
        result = evaluate_visual_layer(layer, 2500)
        assert result.is_active is True
        assert result.source_time_ms == 2500

    def test_loop_behavior(self):
        layer = CompositionLayer(
            start_ms=0, end_ms=9000,
            source_duration_ms=3000,
            behavior_after_end="loop",
        )
        result = evaluate_visual_layer(layer, 7000)
        assert result.is_active is True
        assert result.source_time_ms == 7000 % 3000  # 1000
        assert result.is_looping is True
        assert result.loop_iteration == 2

    def test_loop_iteration_zero_for_first_pass(self):
        layer = CompositionLayer(
            start_ms=0, end_ms=9000,
            source_duration_ms=3000,
            behavior_after_end="loop",
        )
        result = evaluate_visual_layer(layer, 2000)
        assert result.is_active is True
        assert result.source_time_ms == 2000
        assert result.is_looping is False
        assert result.loop_iteration == 0

    def test_freeze_last_frame_behavior(self):
        layer = CompositionLayer(
            start_ms=0, end_ms=8000,
            source_duration_ms=3000,
            behavior_after_end="freeze_last_frame",
        )
        result = evaluate_visual_layer(layer, 5000)
        assert result.is_active is True
        assert result.source_time_ms == 2999  # source_duration - 1
        assert result.is_looping is False

    def test_hide_behavior(self):
        layer = CompositionLayer(
            start_ms=0, end_ms=8000,
            source_duration_ms=3000,
            behavior_after_end="hide",
        )
        result = evaluate_visual_layer(layer, 5000)
        assert result.is_active is False
        assert result.source_time_ms is None

    def test_no_source_duration_always_active(self):
        layer = CompositionLayer(start_ms=0, end_ms=5000, source_duration_ms=0)
        result = evaluate_visual_layer(layer, 3000)
        assert result.is_active is True
        assert result.source_time_ms == 3000

    def test_no_end_ms_layer(self):
        """Layer with end_ms=0 (unbounded) is active past start."""
        layer = CompositionLayer(start_ms=1000, end_ms=0, source_duration_ms=0)
        result = evaluate_visual_layer(layer, 50000)
        assert result.is_active is True

    def test_start_offset_applied(self):
        layer = CompositionLayer(start_ms=2000, end_ms=6000, source_duration_ms=4000)
        result = evaluate_visual_layer(layer, 4000)
        assert result.source_time_ms == 2000


# ------------------------------------------------------------------
# evaluate_audio_layer
# ------------------------------------------------------------------


class TestEvaluateAudioLayer:
    def test_before_start_inactive(self):
        al = CompositionAudioLayer(start_ms=1000, source_duration_ms=5000)
        result = evaluate_audio_layer(al, 500)
        assert result.is_active is False
        assert result.source_time_ms is None

    def test_within_window_active(self):
        al = CompositionAudioLayer(start_ms=1000, source_duration_ms=5000)
        result = evaluate_audio_layer(al, 3000)
        assert result.is_active is True
        assert result.source_time_ms == 2000

    def test_after_duration_inactive(self):
        al = CompositionAudioLayer(
            start_ms=1000, duration_ms=3000,
            use_full_length=False, source_duration_ms=10000,
        )
        result = evaluate_audio_layer(al, 5000)
        assert result.is_active is False

    def test_effective_duration_reported(self):
        al = CompositionAudioLayer(
            start_ms=0, duration_ms=3000,
            use_full_length=False, source_duration_ms=10000,
        )
        result = evaluate_audio_layer(al, 1000)
        assert result.effective_duration_ms == 3000

    def test_full_length_uses_source_duration(self):
        al = CompositionAudioLayer(
            start_ms=0, source_duration_ms=7000,
            use_full_length=True,
        )
        result = evaluate_audio_layer(al, 1000)
        assert result.effective_duration_ms == 7000
        assert result.is_active is True


# ------------------------------------------------------------------
# compute_composition_duration_ms
# ------------------------------------------------------------------


class TestComputeCompositionDurationMs:
    def test_empty_model(self):
        model = CompositionModel()
        assert compute_composition_duration_ms(model) == 0

    def test_single_visual_layer(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(
            start_ms=1000, end_ms=6000, enabled=True,
        ))
        assert compute_composition_duration_ms(model) == 6000

    def test_disabled_layer_excluded(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(
            start_ms=0, end_ms=10000, enabled=False,
        ))
        assert compute_composition_duration_ms(model) == 0

    def test_audio_layer_extends_duration(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(
            start_ms=0, end_ms=5000, enabled=True,
        ))
        model.audio_layers.append(CompositionAudioLayer(
            start_ms=0, source_duration_ms=8000, enabled=True,
        ))
        assert compute_composition_duration_ms(model) == 8000

    def test_multiple_layers_takes_max(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(start_ms=0, end_ms=3000, enabled=True))
        model.add_layer(CompositionLayer(start_ms=2000, end_ms=7000, enabled=True))
        assert compute_composition_duration_ms(model) == 7000


# ------------------------------------------------------------------
# visual_needs_input_loop / audio_needs_input_loop
# ------------------------------------------------------------------


class TestInputLoopDetection:
    def test_video_needs_loop(self):
        layer = CompositionLayer(
            source_kind="video",
            source_duration_ms=3000,
            start_ms=0, end_ms=9000,
        )
        assert visual_needs_input_loop(layer) is True

    def test_video_no_loop_when_shorter(self):
        layer = CompositionLayer(
            source_kind="video",
            source_duration_ms=10000,
            start_ms=0, end_ms=5000,
        )
        assert visual_needs_input_loop(layer) is False

    def test_image_never_needs_loop(self):
        layer = CompositionLayer(
            source_kind="image",
            source_duration_ms=0,
            start_ms=0, end_ms=5000,
        )
        assert visual_needs_input_loop(layer) is False

    def test_video_no_source_duration(self):
        layer = CompositionLayer(
            source_kind="video",
            source_duration_ms=0,
            start_ms=0, end_ms=5000,
        )
        assert visual_needs_input_loop(layer) is False

    def test_audio_needs_loop(self):
        al = CompositionAudioLayer(
            source_duration_ms=3000,
            duration_ms=9000,
            use_full_length=False,
        )
        assert audio_needs_input_loop(al) is True

    def test_audio_no_loop(self):
        al = CompositionAudioLayer(
            source_duration_ms=10000,
            duration_ms=5000,
            use_full_length=False,
        )
        assert audio_needs_input_loop(al) is False

    def test_audio_no_source_duration(self):
        al = CompositionAudioLayer(
            source_duration_ms=0,
            duration_ms=5000,
            use_full_length=False,
        )
        assert audio_needs_input_loop(al) is False
