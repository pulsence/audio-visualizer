"""audio_visualizer.caption - Subtitle overlay rendering with animated effects.

This package provides tools for rendering stylized subtitle overlays as
transparent video files. Heavy imports (pysubs2, Pillow, etc.) are deferred
until first access via lazy loading.

Example:
    from audio_visualizer.caption import render_subtitle, RenderConfig

    result = render_subtitle("input.srt", "output.mov")
"""
from __future__ import annotations

from importlib import import_module
from typing import Dict, Tuple

_EXPORTS: Dict[str, Tuple[str, str]] = {
    # Public API
    "render_subtitle": (".captionApi", "render_subtitle"),
    "RenderConfig": (".captionApi", "RenderConfig"),
    "RenderResult": (".captionApi", "RenderResult"),
    "list_presets": (".captionApi", "list_presets"),
    "list_animations": (".captionApi", "list_animations"),
    # Core
    "PresetConfig": (".core.config", "PresetConfig"),
    "AnimationConfig": (".core.config", "AnimationConfig"),
    "SubtitleFile": (".core.subtitle", "SubtitleFile"),
    "SizeCalculator": (".core.sizing", "SizeCalculator"),
    "StyleBuilder": (".core.style", "StyleBuilder"),
    # Rendering
    "FFmpegRenderer": (".rendering.ffmpegRenderer", "FFmpegRenderer"),
    # Presets
    "PresetLoader": (".presets.loader", "PresetLoader"),
    # Animations
    "AnimationRegistry": (".animations.registry", "AnimationRegistry"),
    "BaseAnimation": (".animations.baseAnimation", "BaseAnimation"),
}

__all__ = list(_EXPORTS.keys())


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if not target:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = target
    module = import_module(module_name, __name__)
    value = getattr(module, attr)
    globals()[name] = value
    return value


def __dir__():
    return sorted(list(globals().keys()) + list(_EXPORTS.keys()))
