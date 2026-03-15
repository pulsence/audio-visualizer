#!/usr/bin/env python3
"""Whisper model initialization wrapper.

This module handles initialization of the faster-whisper model with
appropriate device and compute type selection.
"""
from __future__ import annotations

from typing import Tuple, Any, Optional

from audio_visualizer.events import AppEvent, AppEventEmitter, EventType


# ============================================================
# Device Initialization
# ============================================================

def _emit(emitter: Optional[AppEventEmitter], event: AppEvent) -> None:
    if emitter is not None:
        emitter.emit(event)


def init_whisper_model_internal(
    model_name: str,
    device: str,               # auto|cpu|cuda
    strict_cuda: bool,
    emitter: Optional[AppEventEmitter] = None,
) -> Tuple[Any, str, str]:
    """Initialize a Whisper model with appropriate device and compute type.

    Args:
        model_name: Name of the Whisper model (e.g., "small", "medium")
        device: Device selection: "auto", "cpu", or "cuda"
        strict_cuda: If True, fail if CUDA requested but unavailable
        emitter: Optional event emitter for log events

    Returns:
        Tuple of (model, device_used, compute_type_used)

    Raises:
        RuntimeError: If strict_cuda=True and CUDA initialization fails
    """
    from faster_whisper import WhisperModel

    if device == "cpu":
        compute_type = "int8"
        return WhisperModel(model_name, device="cpu", compute_type=compute_type), "cpu", compute_type

    if device == "cuda":
        try:
            compute_type = "float16"
            m = WhisperModel(model_name, device="cuda", compute_type=compute_type)
            _emit(emitter, AppEvent(event_type=EventType.LOG, message="Using device=cuda compute_type=float16"))
            return m, "cuda", compute_type
        except Exception as e:
            if strict_cuda:
                raise RuntimeError(f"CUDA requested but init failed: {e}") from e
            _emit(emitter, AppEvent(event_type=EventType.LOG, message=f"CUDA init failed; falling back to CPU. Reason: {e}"))
            compute_type = "int8"
            return WhisperModel(model_name, device="cpu", compute_type=compute_type), "cpu", compute_type

    # auto
    try:
        compute_type = "float16"
        m = WhisperModel(model_name, device="cuda", compute_type=compute_type)
        _emit(emitter, AppEvent(event_type=EventType.LOG, message="CUDA available: using device=cuda compute_type=float16"))
        return m, "cuda", compute_type
    except Exception as e:
        _emit(emitter, AppEvent(event_type=EventType.LOG, message=f"CUDA not available; using CPU. Reason: {e}"))
        compute_type = "int8"
        return WhisperModel(model_name, device="cpu", compute_type=compute_type), "cpu", compute_type
