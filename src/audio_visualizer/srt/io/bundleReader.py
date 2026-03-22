"""Bundle reader and normalizer for JSON subtitle bundles.

Accepts both v1 (legacy) and v2 bundles and normalizes them into one
in-memory contract that downstream code can trust.  This is the only
entry point for reading bundle files — consumers should never parse
raw bundle dicts directly.
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
#     "bundle_version": 2,
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

    Accepts both v1 and v2 bundle formats and returns a normalized v2
    structure.

    Args:
        path: Filesystem path to the JSON bundle file.

    Returns:
        Normalized bundle dict with ``bundle_version == 2``.

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
    """Normalize a raw bundle dict into the canonical v2 contract.

    Works with both v1 (no ``bundle_version`` key, uses ``"word"`` field
    names and a ``segments`` + ``subtitles`` shape) and v2 (explicit
    ``bundle_version: 2``, uses ``"text"`` field names and subtitle-level
    ``words`` lists).

    Args:
        data: A raw bundle dict as loaded from JSON.

    Returns:
        Normalized v2 bundle dict.
    """
    version = data.get("bundle_version", 1)

    if version >= 2:
        return _normalize_v2(data)
    return _normalize_v1(data)


def _normalize_v2(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize a v2 bundle (already in the target format)."""
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
        "bundle_version": 2,
        "tool_version": data.get("tool_version", ""),
        "input_file": data.get("input_file", ""),
        "device_used": data.get("device_used", ""),
        "compute_type_used": data.get("compute_type_used", ""),
        "model_name": data.get("model_name", ""),
        "config": data.get("config"),
        "subtitles": subtitles,
        "words": flat_words,
    }


def _normalize_v1(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize a legacy v1 bundle into the v2 contract.

    V1 bundles have:
    - ``segments[].words[].word`` (not ``text``)
    - ``subtitles[]`` with just start/end/text (no IDs, no words)
    - No ``bundle_version`` key
    """
    raw_segments = data.get("segments", [])
    raw_subtitles = data.get("subtitles", [])
    input_file = data.get("input_file", "")
    device_used = data.get("device_used", "")
    compute_type_used = data.get("compute_type_used", "")

    # Build a word pool from segments
    all_seg_words: list[dict[str, Any]] = []
    for seg in raw_segments:
        for w in seg.get("words", []):
            all_seg_words.append(w)

    subtitles: list[dict[str, Any]] = []
    flat_words: list[WordItem] = []
    word_cursor = 0

    for sub_raw in raw_subtitles:
        sub_id = str(_uuid.uuid4())
        sub_text = sub_raw.get("text", "")
        sub_start = float(sub_raw.get("start", 0))
        sub_end = float(sub_raw.get("end", 0))

        # Match words from the segment pool to this subtitle
        words: list[WordItem] = []
        entry_word_texts = sub_text.split()
        matched = 0
        scan = word_cursor

        while scan < len(all_seg_words) and matched < len(entry_word_texts):
            raw_w = all_seg_words[scan]
            w_text = raw_w.get("word", raw_w.get("text", "")).strip()
            e_text = entry_word_texts[matched].strip()
            if (
                w_text.lower() == e_text.lower()
                or w_text.lower().rstrip(".,!?;:") == e_text.lower().rstrip(".,!?;:")
            ):
                if matched == 0:
                    word_cursor = scan
                w_id = str(_uuid.uuid4())
                wi = WordItem(
                    start=float(raw_w.get("start", 0)),
                    end=float(raw_w.get("end", 0)),
                    text=w_text,
                    id=w_id,
                    subtitle_id=sub_id,
                )
                words.append(wi)
                flat_words.append(wi)
                matched += 1
            elif matched > 0:
                matched = 0
                word_cursor = scan + 1
            scan += 1

        if matched > 0:
            word_cursor = word_cursor + matched

        subtitles.append({
            "id": sub_id,
            "start": sub_start,
            "end": sub_end,
            "text": sub_text,
            "original_text": sub_text,
            "words": words,
            "speaker_label": None,
            "source_media_path": input_file,
            "model_name": "",
            "device": device_used,
            "compute_type": compute_type_used,
            "alignment_status": None,
            "alignment_confidence": None,
        })

    return {
        "bundle_version": 2,
        "tool_version": data.get("tool_version", ""),
        "input_file": input_file,
        "device_used": device_used,
        "compute_type_used": compute_type_used,
        "model_name": "",
        "config": data.get("config"),
        "subtitles": subtitles,
        "words": flat_words,
    }
