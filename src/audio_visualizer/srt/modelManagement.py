#!/usr/bin/env python3
"""Model management utilities for Local SRT.

This module provides functionality for:
- Listing downloaded Whisper models
- Downloading new models
- Deleting cached models
- System diagnostics
- Model info for the settings UI
"""
from __future__ import annotations

import os
import platform
import shutil
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from audio_visualizer import __version__
from audio_visualizer.srt.io.systemHelpers import ffmpeg_version, ffprobe_version, which_or_none


# Approximate model sizes for display purposes (parameters / disk)
_MODEL_SIZES: Dict[str, str] = {
    "tiny": "39M params (~150 MB)",
    "tiny.en": "39M params (~150 MB)",
    "base": "74M params (~290 MB)",
    "base.en": "74M params (~290 MB)",
    "small": "244M params (~970 MB)",
    "small.en": "244M params (~970 MB)",
    "medium": "769M params (~3.1 GB)",
    "medium.en": "769M params (~3.1 GB)",
    "large-v1": "1550M params (~6.2 GB)",
    "large-v2": "1550M params (~6.2 GB)",
    "large-v3": "1550M params (~6.2 GB)",
    "large": "1550M params (~6.2 GB)",
    "turbo": "809M params (~3.2 GB)",
    "distil-large-v2": "756M params (~3.0 GB)",
    "distil-large-v3": "756M params (~3.0 GB)",
    "distil-small.en": "166M params (~660 MB)",
    "distil-medium.en": "394M params (~1.6 GB)",
}


# ============================================================
# System Diagnostics
# ============================================================

@dataclass
class DiagnoseResult:
    tool_version: str
    python_version: str
    platform: str
    ffmpeg_version: Optional[str]
    ffprobe_version: Optional[str]
    faster_whisper_version: Optional[str]
    ffmpeg_path: Optional[str]
    ffprobe_path: Optional[str]


def diagnose() -> DiagnoseResult:
    """Return system diagnostic information."""
    fw_version: Optional[str]
    try:
        import faster_whisper  # type: ignore

        fw_version = getattr(faster_whisper, "__version__", "unknown")
    except Exception:
        fw_version = None

    return DiagnoseResult(
        tool_version=__version__,
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        ffmpeg_version=ffmpeg_version(),
        ffprobe_version=ffprobe_version(),
        faster_whisper_version=fw_version,
        ffmpeg_path=which_or_none("ffmpeg"),
        ffprobe_path=which_or_none("ffprobe"),
    )


# ============================================================
# Model Listing
# ============================================================

def list_downloaded_models() -> List[Tuple[str, str]]:
    """Get a list of already-downloaded Whisper models.

    Returns:
        List of (model_name, path) tuples for downloaded models
    """
    from faster_whisper import utils as fw_utils

    downloaded: List[Tuple[str, str]] = []
    for name in fw_utils.available_models():
        try:
            path = fw_utils.download_model(name, local_files_only=True)
        except Exception:
            continue
        if path and os.path.exists(path):
            downloaded.append((name, path))
    return downloaded


def list_available_models() -> List[str]:
    """Get a list of all available Whisper model names.

    Returns:
        List of model names (e.g., ["tiny", "base", "small", ...])
    """
    from faster_whisper import utils as fw_utils

    return list(fw_utils.available_models())


# ============================================================
# Model Download/Delete
# ============================================================

def download_model(model_name: str) -> str:
    """Download a Whisper model from the internet.

    Args:
        model_name: Name of the model to download (e.g., "small")

    Returns:
        Path to the downloaded model
    """
    from faster_whisper import utils as fw_utils

    try:
        path = fw_utils.download_model(model_name, local_files_only=False)
    except Exception as e:
        raise RuntimeError(f"Failed to download model '{model_name}': {e}") from e
    return path


def delete_model(model_name: str) -> str:
    """Delete a cached Whisper model from disk.

    Args:
        model_name: Name of the model to delete (e.g., "small")

    Returns:
        Path of the deleted model
    """
    from faster_whisper import utils as fw_utils

    try:
        path = fw_utils.download_model(model_name, local_files_only=True)
    except Exception:
        raise FileNotFoundError(f"Model '{model_name}' is not downloaded.")
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"Model '{model_name}' is not downloaded.")
    try:
        shutil.rmtree(path)
    except Exception as e:
        raise RuntimeError(f"Failed to delete model '{model_name}': {e}") from e
    return path


def get_model_size_label(model_name: str) -> str:
    """Return a human-readable size label for a model name.

    Args:
        model_name: Name of the model (e.g., "small", "large-v3")

    Returns:
        Size string (e.g., "244M params (~970 MB)") or "unknown" if not in table.
    """
    return _MODEL_SIZES.get(model_name, "unknown")


@dataclass
class ModelInfo:
    """Structured info about a single Whisper model for UI display."""

    name: str
    size_label: str
    is_downloaded: bool


def list_models_with_status() -> List[ModelInfo]:
    """Return all available Whisper models with download status.

    Returns:
        List of ModelInfo objects sorted by name, each indicating
        whether the model is currently downloaded.
    """
    available = list_available_models()
    downloaded_names = {name for name, _ in list_downloaded_models()}

    return [
        ModelInfo(
            name=name,
            size_label=get_model_size_label(name),
            is_downloaded=(name in downloaded_names),
        )
        for name in available
    ]
