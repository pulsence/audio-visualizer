#!/usr/bin/env python3
"""Alignment utilities for corrected SRT workflows and bundle-from-SRT."""
from __future__ import annotations

import difflib
import re
import uuid as _uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from audio_visualizer.srt.models import SubtitleBlock, WordItem
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


# ============================================================
# Bundle-from-SRT: Cue-to-Word Alignment
# ============================================================


@dataclass
class AlignedCue:
    """Result of aligning a single subtitle cue with Whisper word timing.

    Attributes:
        cue_text: The original cue text preserved exactly.
        start: Start time in seconds (from the original cue).
        end: End time in seconds (from the original cue).
        words: List of WordItem objects aligned to this cue.
        alignment_status: One of "matched", "partial", "estimated".
        alignment_confidence: Float 0.0-1.0 indicating match quality.
    """

    cue_text: str
    start: float
    end: float
    words: List[WordItem] = field(default_factory=list)
    alignment_status: str = "estimated"
    alignment_confidence: float = 0.0


def _tokenize_cue(text: str) -> List[str]:
    """Split cue text into word tokens, preserving original form."""
    return text.split()


def _match_ratio(cue_norm: List[str], whisper_norm: List[str]) -> float:
    """Compute sequence match ratio between two normalized word lists."""
    if not cue_norm and not whisper_norm:
        return 1.0
    if not cue_norm or not whisper_norm:
        return 0.0
    matcher = difflib.SequenceMatcher(None, cue_norm, whisper_norm)
    return matcher.ratio()


def align_cues_to_whisper_words(
    cues: List[SubtitleBlock],
    whisper_words: List[WordItem],
) -> List[AlignedCue]:
    """Align existing subtitle cues to Whisper-produced word-level timing.

    For each cue, finds the best-matching span of Whisper words based on
    normalized text comparison.  Preserves the original cue text exactly
    while attaching timing from the Whisper words.

    Handles punctuation and casing differences by normalizing before
    comparison but keeping original text in the output.

    Args:
        cues: Subtitle cues from the user's existing subtitle file.
        whisper_words: Word-level timing data from Whisper transcription.

    Returns:
        List of AlignedCue objects, one per input cue.
    """
    if not whisper_words:
        return [
            AlignedCue(
                cue_text=normalize_spaces(" ".join(cue.lines)),
                start=cue.start,
                end=cue.end,
                alignment_status="estimated",
                alignment_confidence=0.0,
            )
            for cue in cues
        ]

    # Pre-normalize all whisper words
    w_norm = [_normalize_word(w.text) for w in whisper_words]

    results: List[AlignedCue] = []
    cursor = 0  # sliding window start position in whisper_words

    for cue in cues:
        cue_text = normalize_spaces(" ".join(cue.lines))
        cue_tokens = _tokenize_cue(cue_text)
        cue_norm = [_normalize_word(t) for t in cue_tokens]
        # Filter empty normalizations
        cue_norm_filtered = [n for n in cue_norm if n]

        if not cue_norm_filtered:
            # Empty or all-punctuation cue: no alignment possible
            results.append(AlignedCue(
                cue_text=cue_text,
                start=cue.start,
                end=cue.end,
                alignment_status="estimated",
                alignment_confidence=0.0,
            ))
            continue

        # Find best matching span using time-bounded search
        best_score = 0.0
        best_start = cursor
        best_end = cursor
        span_len = len(cue_norm_filtered)

        # Search in a window around the cursor position
        search_start = max(0, cursor - span_len)
        search_end = min(len(whisper_words), cursor + span_len * 4 + 10)

        for i in range(search_start, search_end):
            # Try spans of varying length around the cue word count
            for extra in range(max(1, span_len - 1), span_len + 3):
                j = min(i + extra, len(whisper_words))
                if j <= i:
                    continue
                candidate_norm = [n for n in w_norm[i:j] if n]
                score = _match_ratio(cue_norm_filtered, candidate_norm)

                # Bonus for time overlap with the cue
                if j <= len(whisper_words) and i < len(whisper_words):
                    w_start = whisper_words[i].start
                    w_end = whisper_words[j - 1].end
                    overlap_start = max(cue.start, w_start)
                    overlap_end = min(cue.end, w_end)
                    cue_dur = max(0.001, cue.end - cue.start)
                    if overlap_end > overlap_start:
                        time_bonus = min(0.15, 0.15 * (overlap_end - overlap_start) / cue_dur)
                        score += time_bonus

                if score > best_score:
                    best_score = score
                    best_start = i
                    best_end = j

        # Build aligned words using the best span
        matched_whisper = whisper_words[best_start:best_end]
        aligned_words = _align_cue_words_to_whisper_span(
            cue_tokens, matched_whisper, cue.start, cue.end
        )

        # Determine alignment quality
        text_score = best_score - 0.15  # remove possible time bonus
        text_score = max(0.0, min(1.0, text_score))

        if text_score >= 0.85:
            status = "matched"
            confidence = min(1.0, text_score)
        elif text_score >= 0.5:
            status = "partial"
            confidence = text_score
        else:
            status = "estimated"
            confidence = text_score

        results.append(AlignedCue(
            cue_text=cue_text,
            start=cue.start,
            end=cue.end,
            words=aligned_words,
            alignment_status=status,
            alignment_confidence=round(confidence, 3),
        ))

        # Advance cursor past matched words
        if best_end > cursor:
            cursor = best_end

    return results


def _align_cue_words_to_whisper_span(
    cue_tokens: List[str],
    whisper_span: List[WordItem],
    cue_start: float,
    cue_end: float,
) -> List[WordItem]:
    """Map individual cue words to Whisper timing within a matched span.

    Uses SequenceMatcher to pair cue words with whisper words, preserving
    the cue's original text while using Whisper timing.  Words that have
    no direct match get estimated timing distributed evenly in gaps.

    Args:
        cue_tokens: Original word tokens from the cue.
        whisper_span: Whisper WordItem objects for the matched span.
        cue_start: Cue start time for fallback distribution.
        cue_end: Cue end time for fallback distribution.

    Returns:
        List of WordItem objects for each cue token.
    """
    if not cue_tokens:
        return []

    if not whisper_span:
        # No whisper words: distribute timing evenly
        times = _distribute_insert_times(len(cue_tokens), cue_start, cue_end)
        return [
            WordItem(start=s, end=e, text=token)
            for (s, e), token in zip(times, cue_tokens)
        ]

    cue_norm = [_normalize_word(t) for t in cue_tokens]
    whisper_norm = [_normalize_word(w.text) for w in whisper_span]

    matcher = difflib.SequenceMatcher(None, cue_norm, whisper_norm)
    result: List[Optional[WordItem]] = [None] * len(cue_tokens)

    # First pass: assign timing from matched whisper words
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for ci, wi in zip(range(i1, i2), range(j1, j2)):
                result[ci] = WordItem(
                    start=whisper_span[wi].start,
                    end=whisper_span[wi].end,
                    text=cue_tokens[ci],
                )
        elif tag == "replace":
            common = min(i2 - i1, j2 - j1)
            for k in range(common):
                ci = i1 + k
                wi = j1 + k
                result[ci] = WordItem(
                    start=whisper_span[wi].start,
                    end=whisper_span[wi].end,
                    text=cue_tokens[ci],
                )

    # Second pass: fill gaps with distributed timing
    for i in range(len(result)):
        if result[i] is not None:
            continue

        # Find surrounding known times
        prev_end = cue_start
        for j in range(i - 1, -1, -1):
            if result[j] is not None:
                prev_end = result[j].end
                break

        next_start = cue_end
        for j in range(i + 1, len(result)):
            if result[j] is not None:
                next_start = result[j].start
                break

        # Count consecutive unassigned words
        gap_count = 0
        for j in range(i, len(result)):
            if result[j] is not None:
                break
            gap_count += 1

        times = _distribute_insert_times(gap_count, prev_end, next_start)
        for k in range(gap_count):
            if i + k < len(result) and result[i + k] is None:
                s, e = times[k] if k < len(times) else (prev_end, next_start)
                result[i + k] = WordItem(
                    start=s,
                    end=e,
                    text=cue_tokens[i + k],
                )

    return [w for w in result if w is not None]


def parse_subtitle_file(path: Path) -> List[SubtitleBlock]:
    """Parse a subtitle file (.srt, .vtt, .ass) into SubtitleBlock objects.

    Uses pysubs2 for robust format detection and parsing.

    Args:
        path: Path to the subtitle file.

    Returns:
        List of SubtitleBlock objects.
    """
    import pysubs2

    subs = pysubs2.load(str(path), encoding="utf-8")
    blocks: List[SubtitleBlock] = []
    for event in subs:
        if event.is_comment:
            continue
        # pysubs2 uses milliseconds
        start = event.start / 1000.0
        end = event.end / 1000.0
        text = event.plaintext.strip()
        if not text:
            continue
        blocks.append(SubtitleBlock(
            start=start,
            end=end,
            lines=[text],
        ))
    return blocks
