#!/usr/bin/env python3
"""Alignment utilities for corrected SRT workflows."""
from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import List, Tuple

from audio_visualizer.srt.models import WordItem
from audio_visualizer.srt.core.textProcessing import normalize_spaces


def _normalize_word(word: str) -> str:
    return re.sub(r"[^\w]", "", word.lower())


def _normalize_sentence(text: str) -> str:
    text = normalize_spaces(text).lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return normalize_spaces(text)


def parse_srt_to_words(srt_path: Path) -> List[Tuple[str, str]]:
    """Parse SRT text into a list of (normalized, original) word pairs."""
    text = srt_path.read_text(encoding="utf-8")
    words: List[Tuple[str, str]] = []
    for line in text.splitlines():
        raw = line.strip()
        if not raw:
            continue
        if "-->" in raw:
            continue
        if raw.isdigit():
            continue
        for token in raw.split():
            norm = _normalize_word(token)
            if not norm:
                continue
            words.append((norm, token))
    return words


def _distribute_insert_times(
    count: int,
    start: float,
    end: float,
) -> List[Tuple[float, float]]:
    if count <= 0:
        return []
    if end <= start:
        step = 0.01
        return [(start + i * step, start + (i + 1) * step) for i in range(count)]
    dur = (end - start) / count
    return [(start + i * dur, start + (i + 1) * dur) for i in range(count)]


def align_corrected_srt(corrected_srt: Path, words: List[WordItem]) -> List[WordItem]:
    """Align corrected SRT words to whisper word timings."""
    corrected_pairs = parse_srt_to_words(corrected_srt)
    corrected_norm = [n for n, _ in corrected_pairs]
    corrected_orig = [o for _, o in corrected_pairs]

    whisper_norm = [_normalize_word(w.text) for w in words]

    matcher = difflib.SequenceMatcher(None, whisper_norm, corrected_norm)
    out: List[WordItem] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for wi, cj in zip(range(i1, i2), range(j1, j2)):
                out.append(WordItem(words[wi].start, words[wi].end, corrected_orig[cj]))
        elif tag == "replace":
            count_whisper = i2 - i1
            count_corr = j2 - j1
            common = min(count_whisper, count_corr)
            for k in range(common):
                wi = i1 + k
                cj = j1 + k
                out.append(WordItem(words[wi].start, words[wi].end, corrected_orig[cj]))

            if count_corr > common:
                insert_count = count_corr - common
                insert_words = corrected_orig[j1 + common : j2]
                prev_end = words[i1 + common - 1].end if (i1 + common - 1) >= 0 else 0.0
                next_start = words[i2].start if i2 < len(words) else prev_end
                for (s, e), token in zip(
                    _distribute_insert_times(insert_count, prev_end, next_start),
                    insert_words,
                ):
                    out.append(WordItem(s, e, token))
        elif tag == "insert":
            insert_words = corrected_orig[j1:j2]
            prev_end = words[i1 - 1].end if i1 > 0 else (words[0].start if words else 0.0)
            next_start = words[i1].start if i1 < len(words) else (words[-1].end if words else prev_end)
            for (s, e), token in zip(
                _distribute_insert_times(len(insert_words), prev_end, next_start),
                insert_words,
            ):
                out.append(WordItem(s, e, token))
        elif tag == "delete":
            continue

    return out


def _replace_segment_text(segment: object, new_text: str):
    if hasattr(segment, "_replace"):
        return segment._replace(text=new_text)
    try:
        setattr(segment, "text", new_text)
    except Exception:
        pass
    return segment


def align_script_to_segments(script_sentences: List[str], segments: List[object]) -> List[object]:
    """Replace segment text with script sentences where possible."""
    script_units: List[str] = []
    for sent in script_sentences:
        cleaned = normalize_spaces(sent)
        if cleaned:
            script_units.append(cleaned)

    if not script_units:
        return segments

    segment_texts = [normalize_spaces(getattr(seg, "text", "")) for seg in segments]
    segment_norm = [_normalize_sentence(t) for t in segment_texts]
    script_norm = [_normalize_sentence(t) for t in script_units]

    matcher = difflib.SequenceMatcher(None, segment_norm, script_norm)
    updated = list(segments)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag not in {"equal", "replace"}:
            continue
        count_seg = i2 - i1
        count_script = j2 - j1
        common = min(count_seg, count_script)
        for k in range(common):
            seg_idx = i1 + k
            script_idx = j1 + k
            updated[seg_idx] = _replace_segment_text(segments[seg_idx], script_units[script_idx])

    return updated
