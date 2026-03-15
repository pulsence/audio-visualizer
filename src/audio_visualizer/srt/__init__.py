"""audio_visualizer.srt - Subtitle generation from media using faster-whisper.

This package provides tools for generating subtitles from audio/video files
using the Whisper speech recognition model. Heavy imports (faster-whisper, etc.)
are deferred until first access via lazy loading.

Example:
    from audio_visualizer.srt import transcribe_file, load_model, ResolvedConfig
"""
from __future__ import annotations

from importlib import import_module
from typing import Dict, Tuple

_EXPORTS: Dict[str, Tuple[str, str]] = {
    # Public API
    "transcribe_file": (".srtApi", "transcribe_file"),
    "load_model": (".srtApi", "load_model"),
    "TranscriptionResult": (".srtApi", "TranscriptionResult"),
    # Model manager
    "ModelManager": (".modelManager", "ModelManager"),
    "ModelInfo": (".modelManager", "ModelInfo"),
    # Data models
    "FormattingConfig": (".models", "FormattingConfig"),
    "TranscriptionConfig": (".models", "TranscriptionConfig"),
    "SilenceConfig": (".models", "SilenceConfig"),
    "ResolvedConfig": (".models", "ResolvedConfig"),
    "PipelineMode": (".models", "PipelineMode"),
    "SubtitleBlock": (".models", "SubtitleBlock"),
    "WordItem": (".models", "WordItem"),
    # Config
    "PRESETS": (".config", "PRESETS"),
    "load_config_file": (".config", "load_config_file"),
    "apply_overrides": (".config", "apply_overrides"),
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
