"""Bundle reader for JSON subtitle bundles.

Reads bundle files and normalizes them into one in-memory contract that
downstream code can trust.  This is the only entry point for reading
bundle files — consumers should never parse raw bundle dicts directly.
"""
from __future__ import annotations

import json
import logging
import uuid as _uuid
from pathlib import Path
from typing import Any

from audio_visualizer.srt.models import WordItem

logger = logging.getLogger(__name__)

# Normalized bundle structure returned by read_json_bundle():
#
# {
#     "tool_version": str,
#     "input_file": str,
#     "device_used": str,
#     "compute_type_used": str,
#     "model_name": str,
#     "config": dict | None,
#     "subtitles": [
#         {
#             "id": str,
#             "start": float,
#             "end": float,
#             "text": str,
#             "original_text": str,
#             "words": [WordItem, ...],
#             "speaker_label": str | None,
#             "source_media_path": str,
#             "model_name": str,
#             "device": str,
#             "compute_type": str,
#             "alignment_status": str | None,
#             "alignment_confidence": float | None,
#         },
#         ...
#     ],
#     "words": [WordItem, ...],   # flat convenience list
# }


def read_json_bundle(path: str | Path) -> dict[str, Any]:
    """Read and normalize a JSON bundle file.

    Args:
        path: Filesystem path to the JSON bundle file.

    Returns:
        Normalized bundle dict.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is not a valid JSON bundle.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Bundle file not found: {path}")

    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in bundle file: {path}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Bundle file does not contain a JSON object: {path}")

    return normalize_bundle(data)


def normalize_bundle(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw bundle dict into the canonical contract.

    Accepts bundles with or without explicit subtitle-level word lists
    and ensures all fields are present with consistent types.

    Args:
        data: A raw bundle dict as loaded from JSON.

    Returns:
        Normalized bundle dict.
    """
    subtitles: list[dict[str, Any]] = []
    flat_words: list[WordItem] = []

    for sub_raw in data.get("subtitles", []):
        sub_id = sub_raw.get("id", str(_uuid.uuid4()))
        words: list[WordItem] = []
        for w_raw in sub_raw.get("words", []):
            wi = WordItem(
                start=float(w_raw.get("start", 0)),
                end=float(w_raw.get("end", 0)),
                text=w_raw.get("text", w_raw.get("word", "")),
                id=w_raw.get("id", str(_uuid.uuid4())),
                subtitle_id=w_raw.get("subtitle_id", sub_id),
                confidence=w_raw.get("confidence"),
                speaker_label=w_raw.get("speaker_label"),
            )
            words.append(wi)
            flat_words.append(wi)

        subtitles.append({
            "id": sub_id,
            "start": float(sub_raw.get("start", 0)),
            "end": float(sub_raw.get("end", 0)),
            "text": sub_raw.get("text", ""),
            "original_text": sub_raw.get("original_text", sub_raw.get("text", "")),
            "words": words,
            "speaker_label": sub_raw.get("speaker_label"),
            "source_media_path": sub_raw.get("source_media_path", ""),
            "model_name": sub_raw.get("model_name", data.get("model_name", "")),
            "device": sub_raw.get("device", data.get("device_used", "")),
            "compute_type": sub_raw.get("compute_type", data.get("compute_type_used", "")),
            "alignment_status": sub_raw.get("alignment_status"),
            "alignment_confidence": sub_raw.get("alignment_confidence"),
        })

    return {
        "tool_version": data.get("tool_version", ""),
        "input_file": data.get("input_file", ""),
        "device_used": data.get("device_used", ""),
        "compute_type_used": data.get("compute_type_used", ""),
        "model_name": data.get("model_name", ""),
        "config": data.get("config"),
        "subtitles": subtitles,
        "words": flat_words,
    }
