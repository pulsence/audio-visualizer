"""Hardware-accelerated encoder detection and selection.

Provides a shared encoder-detection and selection layer for all render
paths (Audio Visualizer PyAV, Render Composition FFmpeg subprocess,
Caption Animator FFmpeg subprocess).

Encoder priority: h264_nvenc -> h264_qsv -> h264_amf -> h264_mf -> libx264
"""
from __future__ import annotations

import functools
import logging
import shutil
import subprocess
from typing import Any

logger = logging.getLogger(__name__)

# Encoder priority order (highest priority first)
_H264_ENCODER_PRIORITY: list[str] = [
    "h264_nvenc",
    "h264_qsv",
    "h264_amf",
    "h264_mf",
    "libx264",
]

_SOFTWARE_FALLBACK = "libx264"


@functools.cache
def detect_subprocess_encoders() -> list[str]:
    """Probe FFmpeg for available H.264 encoders (subprocess path).

    Returns a list of available encoder names from the priority list.
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        logger.warning("ffmpeg not found on PATH; falling back to libx264")
        return [_SOFTWARE_FALLBACK]

    try:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=10,
        )
        output = result.stdout
    except Exception:
        logger.exception("Failed to probe ffmpeg encoders")
        return [_SOFTWARE_FALLBACK]

    available: list[str] = []
    for encoder in _H264_ENCODER_PRIORITY:
        if encoder in output:
            available.append(encoder)

    if not available:
        available.append(_SOFTWARE_FALLBACK)

    logger.info("Detected subprocess H.264 encoders: %s", available)
    return available


@functools.cache
def detect_pyav_encoders() -> list[str]:
    """Probe PyAV for available H.264 encoders.

    Returns a list of available encoder names from the priority list.
    """
    try:
        import av
    except ImportError:
        logger.warning("PyAV not available; falling back to libx264")
        return [_SOFTWARE_FALLBACK]

    available: list[str] = []
    for encoder in _H264_ENCODER_PRIORITY:
        try:
            av.codec.Codec(encoder, "w")
            available.append(encoder)
        except Exception:
            pass

    if not available:
        available.append(_SOFTWARE_FALLBACK)

    logger.info("Detected PyAV H.264 encoders: %s", available)
    return available


def select_encoder(codec: str = "h264", *, use_pyav: bool = False) -> str:
    """Select the highest-priority available encoder.

    Args:
        codec: Target codec (only "h264" supported currently).
        use_pyav: If True, probe PyAV instead of FFmpeg subprocess.

    Returns:
        The encoder name string to use.
    """
    if codec != "h264":
        return codec

    encoders = detect_pyav_encoders() if use_pyav else detect_subprocess_encoders()
    selected = encoders[0]
    logger.info("Selected encoder: %s (pyav=%s)", selected, use_pyav)
    return selected


def get_decode_flags() -> list[str]:
    """Return FFmpeg decode acceleration flags for subprocess renders.

    Returns ``["-hwaccel", "auto"]`` to let FFmpeg pick the best
    available hardware decoder.
    """
    return ["-hwaccel", "auto"]


def is_hardware_encoder(encoder: str) -> bool:
    """Return True if *encoder* is a hardware encoder (not software)."""
    return encoder != _SOFTWARE_FALLBACK
