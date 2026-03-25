#!/usr/bin/env python3
"""Output writers for various subtitle formats.

This module handles writing subtitles to different formats:
- SRT (SubRip)
- VTT (WebVTT)
- ASS (Advanced SubStation Alpha)
- TXT (plain transcript)
- JSON (complete bundle with metadata)
- JSON bundle-from-SRT (with alignment quality metadata)
"""
from __future__ import annotations

import dataclasses
import json
import os
import uuid as _uuid_mod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from audio_visualizer.srt.models import ResolvedConfig, SubtitleBlock, WordItem
from audio_visualizer.srt.io.systemHelpers import ensure_parent_dir
from audio_visualizer.srt.core.textProcessing import normalize_spaces, wrap_text_lines

if TYPE_CHECKING:
    from audio_visualizer.srt.core.alignment import AlignedCue


# ============================================================
# Time Formatters
# ============================================================

def format_srt_time(seconds: float) -> str:
    """Format time for SRT format (HH:MM:SS,mmm).

    Args:
        seconds: Time in seconds

    Returns:
        Formatted time string (e.g., "00:01:23,456")
    """
    ms = int(round(seconds * 1000))
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def format_vtt_time(seconds: float) -> str:
    """Format time for WebVTT format (HH:MM:SS.mmm).

    Args:
        seconds: Time in seconds

    Returns:
        Formatted time string (e.g., "00:01:23.456")
    """
    ms = int(round(seconds * 1000))
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def format_ass_time(seconds: float) -> str:
    """Format time for ASS format (H:MM:SS.cc, where cc is centiseconds).

    Args:
        seconds: Time in seconds

    Returns:
        Formatted time string (e.g., "0:01:23.45")
    """
    cs = int(round(seconds * 100))
    h = cs // 360_000
    cs %= 360_000
    m = cs // 6_000
    cs %= 6_000
    s = cs // 100
    cs %= 100
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


# ============================================================
# Atomic File Writing
# ============================================================

def atomic_write_text(path: Path, content: str) -> None:
    """Write text to a file atomically using a temporary file.

    Args:
        path: Destination file path
        content: Text content to write
    """
    ensure_parent_dir(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


# ============================================================
# Format Writers
# ============================================================

def _subtitle_text(sb: SubtitleBlock) -> str:
    text = normalize_spaces(" ".join(sb.lines))
    if sb.speaker:
        return f"{sb.speaker}: {text}".strip()
    return text


def write_srt(subs: List[SubtitleBlock], out_path: Path, *, max_chars: int, max_lines: int) -> None:
    """Write subtitles in SRT (SubRip) format.

    Args:
        subs: List of SubtitleBlock objects
        out_path: Output file path
        max_chars: Maximum characters per line
        max_lines: Maximum lines per subtitle
    """
    chunks: List[str] = []
    for i, sb in enumerate(subs, start=1):
        text = _subtitle_text(sb)
        lines = wrap_text_lines(text, max_chars)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
        chunks.append(
            f"{i}\n"
            f"{format_srt_time(sb.start)} --> {format_srt_time(sb.end)}\n"
            f"{'\n'.join(lines).strip()}\n"
        )
    atomic_write_text(out_path, "\n".join(chunks).strip() + "\n")


def write_vtt(subs: List[SubtitleBlock], out_path: Path, *, max_chars: int, max_lines: int) -> None:
    """Write subtitles in WebVTT format.

    Args:
        subs: List of SubtitleBlock objects
        out_path: Output file path
        max_chars: Maximum characters per line
        max_lines: Maximum lines per subtitle
    """
    chunks: List[str] = ["WEBVTT\n"]
    for sb in subs:
        text = _subtitle_text(sb)
        lines = wrap_text_lines(text, max_chars)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
        chunks.append(
            f"{format_vtt_time(sb.start)} --> {format_vtt_time(sb.end)}\n"
            f"{'\n'.join(lines).strip()}\n"
        )
    atomic_write_text(out_path, "\n".join(chunks).rstrip() + "\n")


def write_ass(subs: List[SubtitleBlock], out_path: Path, *, max_chars: int, max_lines: int) -> None:
    """Write subtitles in ASS (Advanced SubStation Alpha) format.

    Args:
        subs: List of SubtitleBlock objects
        out_path: Output file path
        max_chars: Maximum characters per line
        max_lines: Maximum lines per subtitle
    """
    header = "\n".join(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            "PlayResX: 1920",
            "PlayResY: 1080",
            "WrapStyle: 0",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
            "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,"
            "1,2,0,2,80,80,60,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )
    events: List[str] = [header]
    for sb in subs:
        text = _subtitle_text(sb)
        lines = wrap_text_lines(text, max_chars)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
        ass_text = "\\N".join(lines).strip()
        events.append(
            f"Dialogue: 0,{format_ass_time(sb.start)},{format_ass_time(sb.end)},Default,,0,0,0,,{ass_text}"
        )
    atomic_write_text(out_path, "\n".join(events).rstrip() + "\n")


def write_txt(subs: List[SubtitleBlock], out_path: Path) -> None:
    """Write plain text transcript from subtitle blocks.

    Args:
        subs: List of SubtitleBlock objects
        out_path: Output file path
    """
    lines: List[str] = []
    for sb in subs:
        lines.append(normalize_spaces(" ".join(sb.lines)))
    atomic_write_text(out_path, "\n".join(lines).strip() + "\n")


# ============================================================
# JSON Utilities
# ============================================================

def segments_to_jsonable(segments: List[Any], *, include_words: bool) -> List[Dict[str, Any]]:
    """Convert transcription segments to JSON-serializable format.

    Args:
        segments: List of transcription segment objects
        include_words: If True, include word-level timing data

    Returns:
        List of dictionaries representing segments
    """
    out: List[Dict[str, Any]] = []
    for s in segments:
        d: Dict[str, Any] = {
            "start": float(s.start),
            "end": float(s.end),
            "text": getattr(s, "text", ""),
        }
        if include_words and getattr(s, "words", None):
            d["words"] = [
                {"start": float(w.start), "end": float(w.end), "word": w.word}
                for w in s.words
            ]
        out.append(d)
    return out


def _build_subtitles(
    subs: List[SubtitleBlock],
    segments: List[Any],
    *,
    model_name: str,
    device_used: str,
    compute_type_used: str,
    source_media_path: str,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Build subtitle entries and a flat words list.

    Returns (subtitles_list, flat_words_list).
    """
    import uuid as _uuid

    subtitles: List[Dict[str, Any]] = []
    flat_words: List[Dict[str, Any]] = []

    # Build a segment index keyed on approximate start time for word lookup
    seg_words_map: Dict[int, List[Any]] = {}
    for seg in segments:
        raw_words = getattr(seg, "words", None) or []
        if raw_words:
            key = int(round(float(seg.start) * 1000))
            seg_words_map[key] = raw_words

    for idx, sb in enumerate(subs):
        sub_id = str(_uuid.uuid4())
        text = normalize_spaces(" ".join(sb.lines))

        # Try to find matching segment words for this subtitle
        sub_key = int(round(sb.start * 1000))
        matched_raw_words: List[Any] = []
        # Find closest segment
        for seg_key, seg_words in seg_words_map.items():
            if abs(seg_key - sub_key) < 500:  # within 500ms
                matched_raw_words = seg_words
                break

        words: List[Dict[str, Any]] = []
        for w in matched_raw_words:
            w_id = str(_uuid.uuid4())
            w_text = getattr(w, "word", getattr(w, "text", ""))
            w_entry: Dict[str, Any] = {
                "id": w_id,
                "subtitle_id": sub_id,
                "text": w_text.strip(),
                "start": float(w.start),
                "end": float(w.end),
            }
            confidence = getattr(w, "probability", None)
            if confidence is not None:
                w_entry["confidence"] = float(confidence)
            words.append(w_entry)
            flat_words.append(w_entry)

        sub_entry: Dict[str, Any] = {
            "id": sub_id,
            "start": sb.start,
            "end": sb.end,
            "text": text,
            "words": words,
            "original_text": text,
            "source_media_path": source_media_path,
            "model_name": model_name,
            "device": device_used,
            "compute_type": compute_type_used,
        }
        if sb.speaker:
            sub_entry["speaker_label"] = sb.speaker

        subtitles.append(sub_entry)

    return subtitles, flat_words


def write_json_bundle(
    out_path: Path,
    *,
    input_file: str,
    device_used: str,
    compute_type_used: str,
    cfg: ResolvedConfig,
    segments: List[Any],
    subs: List[SubtitleBlock],
    tool_version: str,
    model_name: str = "",
) -> None:
    """Write a complete JSON bundle with metadata, segments, and subtitles.

    Emits a bundle with stable IDs, normalized field names, provenance
    fields, and a flat convenience ``words`` list.

    Args:
        out_path: Output file path
        input_file: Input file name
        device_used: Device used for transcription (cpu/cuda)
        compute_type_used: Compute type used (int8/float16)
        cfg: Configuration used
        segments: List of transcription segments
        subs: List of SubtitleBlock objects
        tool_version: Tool version string
        model_name: Whisper model name used for transcription
    """
    subtitles_list, flat_words = _build_subtitles(
        subs,
        segments,
        model_name=model_name,
        device_used=device_used,
        compute_type_used=compute_type_used,
        source_media_path=input_file,
    )

    payload: Dict[str, Any] = {
        "tool_version": tool_version,
        "input_file": input_file,
        "device_used": device_used,
        "compute_type_used": compute_type_used,
        "model_name": model_name,
        "config": dataclasses.asdict(cfg),
        "subtitles": subtitles_list,
        "words": flat_words,
    }
    ensure_parent_dir(out_path)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, out_path)


def write_bundle_from_srt(
    out_path: Path,
    *,
    aligned_cues: List[AlignedCue],
    input_file: str,
    device_used: str,
    compute_type_used: str,
    model_name: str,
    tool_version: str,
    cfg: Optional[ResolvedConfig] = None,
) -> None:
    """Write a JSON bundle from aligned cue data (bundle-from-SRT).

    Preserves the original subtitle text exactly while attaching
    Whisper-aligned word timing and alignment quality metadata.

    Args:
        out_path: Output file path.
        aligned_cues: List of AlignedCue objects from cue-to-word alignment.
        input_file: Path to the source media file.
        device_used: Device used for Whisper transcription.
        compute_type_used: Compute type used.
        model_name: Whisper model name.
        tool_version: Tool version string.
        cfg: Optional configuration used (for metadata only).
    """
    subtitles: List[Dict[str, Any]] = []
    flat_words: List[Dict[str, Any]] = []

    for cue in aligned_cues:
        sub_id = str(_uuid_mod.uuid4())

        words: List[Dict[str, Any]] = []
        for w in cue.words:
            w_id = str(_uuid_mod.uuid4())
            w_entry: Dict[str, Any] = {
                "id": w_id,
                "subtitle_id": sub_id,
                "text": w.text.strip(),
                "start": w.start,
                "end": w.end,
            }
            if w.confidence is not None:
                w_entry["confidence"] = w.confidence
            words.append(w_entry)
            flat_words.append(w_entry)

        sub_entry: Dict[str, Any] = {
            "id": sub_id,
            "start": cue.start,
            "end": cue.end,
            "text": cue.cue_text,
            "original_text": cue.cue_text,
            "words": words,
            "source_media_path": input_file,
            "model_name": model_name,
            "device": device_used,
            "compute_type": compute_type_used,
            "alignment_status": cue.alignment_status,
            "alignment_confidence": cue.alignment_confidence,
        }
        subtitles.append(sub_entry)

    payload: Dict[str, Any] = {
        "tool_version": tool_version,
        "input_file": input_file,
        "device_used": device_used,
        "compute_type_used": compute_type_used,
        "model_name": model_name,
        "config": dataclasses.asdict(cfg) if cfg else None,
        "subtitles": subtitles,
        "words": flat_words,
    }
    ensure_parent_dir(out_path)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, out_path)
