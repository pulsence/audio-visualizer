#!/usr/bin/env python3
"""Configuration management for audio_visualizer.srt.

This module handles configuration loading, preset management, and
configuration merging/overrides. Config files are resolved from the
app data directory at ``get_data_dir() / "srt" / "configs"``.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any, Dict, Optional

from audio_visualizer.app_paths import get_data_dir
from audio_visualizer.srt.models import PipelineMode, ResolvedConfig


# ============================================================
# Presets
# ============================================================

PRESETS: Dict[str, Dict[str, Any]] = {
    "shorts": {
        "formatting": {
            "max_chars": 18,
            "max_lines": 1,
            "target_cps": 18.0,
            "min_dur": 0.7,
            "max_dur": 3.0,
            "prefer_punct_splits": False,
            "allow_commas": True,
            "allow_medium": True,
            "min_gap": 0.08,
            "pad": 0.00,
        },
        "transcription": {},
        "silence": {},
    },
    "yt": {
        "formatting": {
            "max_chars": 42,
            "max_lines": 2,
            "target_cps": 17.0,
            "min_dur": 1.0,
            "max_dur": 6.0,
            "prefer_punct_splits": False,
            "allow_commas": True,
            "allow_medium": True,
            "min_gap": 0.08,
            "pad": 0.00,
        },
        "transcription": {},
        "silence": {},
    },
    "podcast": {
        "formatting": {
            "max_chars": 40,
            "max_lines": 2,
            "target_cps": 16.0,
            "min_dur": 0.9,
            "max_dur": 5.0,
            "prefer_punct_splits": True,
            "allow_commas": True,
            "allow_medium": True,
            "min_gap": 0.08,
            "pad": 0.05,
        },
        "transcription": {},
        "silence": {},
    },
    "transcript": {
        "formatting": {
            "max_chars": 80,
            "max_lines": 4,
            "target_cps": 17.0,
            "min_dur": 2.0,
            "max_dur": 30.0,
            "prefer_punct_splits": True,
            "allow_commas": True,
            "allow_medium": True,
            "min_gap": 0.08,
            "pad": 0.00,
        },
        "transcription": {},
        "silence": {},
    },
}

MODE_PIPELINE_DEFAULTS: Dict[PipelineMode, Dict[str, Any]] = {
    PipelineMode.GENERAL: {"formatting": {}, "transcription": {}, "silence": {}},
    PipelineMode.SHORTS: {"formatting": {}, "transcription": {}, "silence": {}},
    PipelineMode.TRANSCRIPT: PRESETS["transcript"],
}


# ============================================================
# Configuration Loading
# ============================================================

def get_srt_config_dir() -> Path:
    """Return the SRT config directory inside the app data dir.

    The directory is created on first call if it does not exist.

    Returns:
        ``get_data_dir() / "srt" / "configs"``
    """
    d = get_data_dir() / "srt" / "configs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _resolve_config_path(path: str) -> Path:
    """Resolve a config path, checking the app data directory as a fallback.

    Resolution order:
    1. Treat *path* as an absolute or cwd-relative path – use it if it exists.
    2. Look for the filename in ``get_srt_config_dir()``.
    3. Raise ``FileNotFoundError``.
    """
    p = Path(path)
    if p.exists():
        return p
    data_candidate = get_srt_config_dir() / p.name
    if data_candidate.exists():
        return data_candidate
    raise FileNotFoundError(
        f"Config file not found: {p} (also checked {data_candidate})"
    )


def load_config_file(path: Optional[str]) -> Dict[str, Any]:
    """Load configuration from a JSON file.

    The path is resolved through :func:`_resolve_config_path`, which
    checks the literal path first, then falls back to the app data
    directory (``get_data_dir() / "srt" / "configs"``).

    Args:
        path: Path to JSON config file, or None to skip loading

    Returns:
        Dictionary of configuration values, or empty dict if path is None

    Raises:
        FileNotFoundError: If the config file doesn't exist
        ValueError: If the config file isn't a valid JSON object
    """
    if not path:
        return {}
    p = _resolve_config_path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Config must be a JSON object at top-level.")
    return data


def _apply_section_overrides(instance: Any, overrides: Dict[str, Any]) -> Any:
    fields = {f.name for f in dataclasses.fields(instance)}
    updates = {k: v for k, v in overrides.items() if k in fields}
    if not updates:
        return instance
    return dataclasses.replace(instance, **updates)


def apply_overrides(base: ResolvedConfig, overrides: Dict[str, Any]) -> ResolvedConfig:
    """Apply configuration overrides to a base configuration.

    Args:
        base: Base ResolvedConfig instance
        overrides: Dictionary of configuration values to override

    Returns:
        New ResolvedConfig instance with overrides applied
    """
    cfg = ResolvedConfig(
        formatting=dataclasses.replace(base.formatting),
        transcription=dataclasses.replace(base.transcription),
        silence=dataclasses.replace(base.silence),
    )
    for k, v in overrides.items():
        if not isinstance(v, dict):
            continue
        if k == "formatting":
            cfg = dataclasses.replace(cfg, formatting=_apply_section_overrides(cfg.formatting, v))
        elif k == "transcription":
            cfg = dataclasses.replace(cfg, transcription=_apply_section_overrides(cfg.transcription, v))
        elif k == "silence":
            cfg = dataclasses.replace(cfg, silence=_apply_section_overrides(cfg.silence, v))
    return cfg
