"""Local SRT - Local subtitle generator using faster-whisper + ffmpeg.

This package provides tools for generating subtitles from audio/video files
using the Whisper speech recognition model.
"""
from __future__ import annotations

from importlib import import_module
from typing import Dict, Tuple

__version__ = "0.3.0"

_EXPORTS: Dict[str, Tuple[str, str]] = {
    "transcribe_file": (".api", "transcribe_file"),
    "transcribe_batch": (".api", "transcribe_batch"),
    "load_model": (".api", "load_model"),
    "TranscriptionResult": (".api", "TranscriptionResult"),
    "BatchResult": (".api", "BatchResult"),
    "FormattingConfig": (".models", "FormattingConfig"),
    "TranscriptionConfig": (".models", "TranscriptionConfig"),
    "SilenceConfig": (".models", "SilenceConfig"),
    "ResolvedConfig": (".models", "ResolvedConfig"),
    "PipelineMode": (".models", "PipelineMode"),
    "SubtitleBlock": (".models", "SubtitleBlock"),
    "WordItem": (".models", "WordItem"),
    "EventEmitter": (".events", "EventEmitter"),
    "BaseEvent": (".events", "BaseEvent"),
    "LogEvent": (".events", "LogEvent"),
    "WarnEvent": (".events", "WarnEvent"),
    "ErrorEvent": (".events", "ErrorEvent"),
    "ProgressEvent": (".events", "ProgressEvent"),
    "StageEvent": (".events", "StageEvent"),
    "FileStartEvent": (".events", "FileStartEvent"),
    "FileCompleteEvent": (".events", "FileCompleteEvent"),
    "ModelLoadEvent": (".events", "ModelLoadEvent"),
    "EventLevel": (".events", "EventLevel"),
    "PRESETS": (".config", "PRESETS"),
    "load_config_file": (".config", "load_config_file"),
    "apply_overrides": (".config", "apply_overrides"),
}

__all__ = ["__version__", *_EXPORTS.keys()]


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
