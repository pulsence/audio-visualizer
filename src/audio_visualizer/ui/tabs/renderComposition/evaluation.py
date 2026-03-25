"""Canonical timeline evaluation contract for Render Composition.

Provides pure functions that accept :class:`CompositionLayer`,
:class:`CompositionAudioLayer`, and :class:`CompositionModel` instances
and return computed timing results.  Both the live preview
(:mod:`playbackEngine`) and FFmpeg export (:mod:`filterGraph`) import
from this module instead of carrying parallel timing logic.
"""
from __future__ import annotations

from dataclasses import dataclass

from audio_visualizer.ui.tabs.renderComposition.model import (
    CompositionAudioLayer,
    CompositionLayer,
    CompositionModel,
)


# ------------------------------------------------------------------
# Result types
# ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class VisualLayerEval:
    """Evaluation result for a visual layer at a given composition time."""

    is_active: bool
    source_time_ms: int | None
    is_looping: bool
    loop_iteration: int


@dataclass(frozen=True, slots=True)
class AudioLayerEval:
    """Evaluation result for an audio layer at a given composition time."""

    is_active: bool
    source_time_ms: int | None
    effective_duration_ms: int


# ------------------------------------------------------------------
# Core evaluation functions
# ------------------------------------------------------------------


def evaluate_visual_layer(
    layer: CompositionLayer,
    composition_ms: int,
) -> VisualLayerEval:
    """Evaluate a visual layer's state at *composition_ms*.

    Returns a :class:`VisualLayerEval` with activity, source-time
    mapping, and loop status.
    """
    start_ms = layer.start_ms
    end_ms = layer.end_ms

    # Before timeline window
    if composition_ms < start_ms:
        return VisualLayerEval(
            is_active=False, source_time_ms=None,
            is_looping=False, loop_iteration=0,
        )

    # After timeline window
    if end_ms > start_ms and composition_ms >= end_ms:
        return VisualLayerEval(
            is_active=False, source_time_ms=None,
            is_looping=False, loop_iteration=0,
        )

    source_ms = max(0, composition_ms - start_ms)
    source_duration_ms = layer.source_duration_ms
    behavior = layer.behavior_after_end

    # Source not exhausted — straightforward
    if source_duration_ms <= 0 or source_ms < source_duration_ms:
        return VisualLayerEval(
            is_active=True, source_time_ms=source_ms,
            is_looping=False, loop_iteration=0,
        )

    # Source exhausted — apply behavior_after_end
    if behavior == "loop":
        iteration = source_ms // source_duration_ms
        return VisualLayerEval(
            is_active=True,
            source_time_ms=source_ms % source_duration_ms,
            is_looping=True,
            loop_iteration=iteration,
        )
    if behavior == "freeze_last_frame":
        return VisualLayerEval(
            is_active=True,
            source_time_ms=max(0, source_duration_ms - 1),
            is_looping=False,
            loop_iteration=0,
        )
    # "hide" (or unknown) — inactive after source exhaustion
    return VisualLayerEval(
        is_active=False, source_time_ms=None,
        is_looping=False, loop_iteration=0,
    )


def evaluate_audio_layer(
    audio_layer: CompositionAudioLayer,
    composition_ms: int,
) -> AudioLayerEval:
    """Evaluate an audio layer's state at *composition_ms*.

    Returns an :class:`AudioLayerEval` with activity, source-time
    mapping, and effective duration.
    """
    eff_dur = audio_layer.effective_duration_ms()
    start_ms = audio_layer.start_ms

    # Before layer start
    if composition_ms < start_ms:
        return AudioLayerEval(
            is_active=False, source_time_ms=None,
            effective_duration_ms=eff_dur,
        )

    offset_ms = composition_ms - start_ms

    # After effective duration
    if eff_dur > 0 and offset_ms >= eff_dur:
        return AudioLayerEval(
            is_active=False, source_time_ms=None,
            effective_duration_ms=eff_dur,
        )

    return AudioLayerEval(
        is_active=True, source_time_ms=offset_ms,
        effective_duration_ms=eff_dur,
    )


def compute_composition_duration_ms(model: CompositionModel) -> int:
    """Return the canonical composition duration from all enabled layers.

    This is the single source of truth for composition length, replacing
    direct ``model.get_duration_ms()`` calls.
    """
    max_ms = 0
    for layer in model.layers:
        if layer.enabled:
            max_ms = max(max_ms, layer.start_ms + layer.effective_duration_ms())
    for al in model.audio_layers:
        if al.enabled:
            max_ms = max(max_ms, al.effective_end_ms())
    return max_ms


def visual_needs_input_loop(layer: CompositionLayer) -> bool:
    """Return whether the layer requires ``-stream_loop -1`` at input.

    True when the layer is a video whose effective duration exceeds
    its source duration.
    """
    if layer.source_kind != "video":
        return False
    if layer.source_duration_ms <= 0:
        return False
    return layer.effective_duration_ms() > layer.source_duration_ms


def audio_needs_input_loop(audio_layer: CompositionAudioLayer) -> bool:
    """Return whether the audio layer requires ``-stream_loop -1`` at input.

    True when effective duration exceeds source duration.
    """
    if audio_layer.source_duration_ms <= 0:
        return False
    return audio_layer.effective_duration_ms() > audio_layer.source_duration_ms
