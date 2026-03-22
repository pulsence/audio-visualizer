"""Runtime capability detection with cached lazy checks.

Provides cached probes for optional runtime capabilities so the app
can degrade gracefully instead of crashing when OpenGL, audio playback,
or the training stack are unavailable.
"""
from __future__ import annotations

import functools
import logging

logger = logging.getLogger(__name__)


@functools.cache
def has_opengl() -> bool:
    """Return True if PyOpenGL can create a basic context."""
    try:
        import OpenGL.GL  # noqa: F401
        logger.debug("OpenGL capability: available")
        return True
    except Exception:
        logger.info("OpenGL capability: unavailable")
        return False


@functools.cache
def has_sounddevice() -> bool:
    """Return True if sounddevice can query an output device."""
    try:
        import sounddevice as sd
        sd.query_devices(kind="output")
        logger.debug("sounddevice capability: available")
        return True
    except Exception:
        logger.info("sounddevice capability: unavailable (no output device or library missing)")
        return False


@functools.cache
def has_training_stack() -> bool:
    """Return True if torch, transformers, peft, and ctranslate2 are importable."""
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        import peft  # noqa: F401
        import ctranslate2  # noqa: F401
        logger.debug("Training stack capability: available")
        return True
    except Exception:
        logger.info("Training stack capability: unavailable")
        return False


@functools.cache
def has_cuda() -> bool:
    """Return True if CUDA is available for training."""
    try:
        import torch
        available = torch.cuda.is_available()
        logger.debug("CUDA capability: %s", "available" if available else "unavailable")
        return available
    except Exception:
        logger.info("CUDA capability: unavailable (torch not importable)")
        return False


@functools.cache
def has_opengl_widget() -> bool:
    """Return True if ``QOpenGLWidget`` can be imported from PySide6.

    This is a lighter check than :func:`has_opengl` — it only verifies
    that the Qt OpenGL integration module is available, not that a full
    desktop OpenGL context can be created.
    """
    try:
        from PySide6.QtOpenGLWidgets import QOpenGLWidget  # noqa: F401
        logger.debug("QOpenGLWidget capability: available")
        return True
    except Exception:
        logger.info("QOpenGLWidget capability: unavailable")
        return False


@functools.cache
def has_pyav() -> bool:
    """Return True if PyAV (``av``) is importable."""
    try:
        import av  # noqa: F401
        logger.debug("PyAV capability: available")
        return True
    except Exception:
        logger.info("PyAV capability: unavailable")
        return False


def capability_summary() -> dict[str, bool]:
    """Return a dict of all capability check results."""
    return {
        "opengl": has_opengl(),
        "opengl_widget": has_opengl_widget(),
        "sounddevice": has_sounddevice(),
        "pyav": has_pyav(),
        "training_stack": has_training_stack(),
        "cuda": has_cuda(),
    }
