#!/usr/bin/env python3
"""Whisper model initialization wrapper for Local SRT.

This module handles initialization of the faster-whisper model with
appropriate device and compute type selection.
"""
from __future__ import annotations

from typing import Tuple, Any, Optional

from .events import EventHandler, LogEvent


# ============================================================
# Device Initialization
# ============================================================

def _emit(handler: Optional[EventHandler], event: object) -> None:
    if handler is None:
        return
    emit = getattr(handler, "emit", None)
    if callable(emit):
        emit(event)
    else:
        handler(event)


def init_whisper_model_internal(
    model_name: str,
    device: str,               # auto|cpu|cuda
    strict_cuda: bool,
    event_handler: Optional[EventHandler],
) -> Tuple[Any, str, str]:
    """Initialize a Whisper model with appropriate device and compute type.

    Args:
        model_name: Name of the Whisper model (e.g., "small", "medium")
        device: Device selection: "auto", "cpu", or "cuda"
        strict_cuda: If True, fail if CUDA requested but unavailable
        event_handler: Optional event handler for log events

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
            _emit(event_handler, LogEvent(message="Using device=cuda compute_type=float16"))
            return m, "cuda", compute_type
        except Exception as e:
            if strict_cuda:
                raise RuntimeError(f"CUDA requested but init failed: {e}") from e
            _emit(event_handler, LogEvent(message=f"CUDA init failed; falling back to CPU. Reason: {e}"))
            compute_type = "int8"
            return WhisperModel(model_name, device="cpu", compute_type=compute_type), "cpu", compute_type

    # auto
    try:
        compute_type = "float16"
        m = WhisperModel(model_name, device="cuda", compute_type=compute_type)
        _emit(event_handler, LogEvent(message="CUDA available: using device=cuda compute_type=float16"))
        return m, "cuda", compute_type
    except Exception as e:
        _emit(event_handler, LogEvent(message=f"CUDA not available; using CPU. Reason: {e}"))
        compute_type = "int8"
        return WhisperModel(model_name, device="cpu", compute_type=compute_type), "cpu", compute_type
