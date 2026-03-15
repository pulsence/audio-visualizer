"""Resync tools for bulk subtitle timing adjustments.

Each function takes a SubtitleDocument and returns a list of
(index, old_start_ms, old_end_ms, new_start_ms, new_end_ms) tuples
that describe the timing changes.  The caller can preview these
changes and then apply them via BatchResyncCommand for undo support.
"""
from __future__ import annotations

import logging
from typing import Optional

from audio_visualizer.ui.tabs.srtEdit.document import SubtitleDocument

logger = logging.getLogger(__name__)

# Type alias for a single timing change record
TimingChange = tuple[int, int, int, int, int]


def global_shift(document: SubtitleDocument, delta_ms: int) -> list[TimingChange]:
    """Shift all entries by a constant offset.

    Args:
        document: The subtitle document.
        delta_ms: Offset in milliseconds (positive = later, negative = earlier).

    Returns:
        List of timing change tuples.
    """
    changes: list[TimingChange] = []
    for i, entry in enumerate(document.entries):
        new_start = max(0, entry.start_ms + delta_ms)
        new_end = max(new_start + 1, entry.end_ms + delta_ms)
        changes.append((i, entry.start_ms, entry.end_ms, new_start, new_end))
    return changes


def shift_from_cursor(
    document: SubtitleDocument,
    from_index: int,
    delta_ms: int,
) -> list[TimingChange]:
    """Shift entries from *from_index* onwards by *delta_ms*.

    Entries before *from_index* are left unchanged.

    Args:
        document: The subtitle document.
        from_index: 0-based index of the first entry to shift.
        delta_ms: Offset in milliseconds.

    Returns:
        List of timing change tuples.
    """
    changes: list[TimingChange] = []
    for i, entry in enumerate(document.entries):
        if i < from_index:
            continue
        new_start = max(0, entry.start_ms + delta_ms)
        new_end = max(new_start + 1, entry.end_ms + delta_ms)
        changes.append((i, entry.start_ms, entry.end_ms, new_start, new_end))
    return changes


def two_point_stretch(
    document: SubtitleDocument,
    anchor1_idx: int,
    anchor1_ms: int,
    anchor2_idx: int,
    anchor2_ms: int,
) -> list[TimingChange]:
    """Linearly stretch/compress timing between two anchor points.

    Maps the time at anchor1 to anchor1_ms and anchor2 to anchor2_ms,
    then linearly interpolates all entries.

    Args:
        document: The subtitle document.
        anchor1_idx: 0-based index of the first anchor entry.
        anchor1_ms: Desired start time (ms) for anchor1.
        anchor2_idx: 0-based index of the second anchor entry.
        anchor2_ms: Desired start time (ms) for anchor2.

    Returns:
        List of timing change tuples.
    """
    entries = document.entries
    if not entries:
        return []

    if anchor1_idx < 0 or anchor1_idx >= len(entries):
        return []
    if anchor2_idx < 0 or anchor2_idx >= len(entries):
        return []

    old_t1 = entries[anchor1_idx].start_ms
    old_t2 = entries[anchor2_idx].start_ms

    if old_t2 == old_t1:
        # Degenerate case — fall back to global shift
        delta = anchor1_ms - old_t1
        return global_shift(document, delta)

    # Linear mapping: new_t = anchor1_ms + (t - old_t1) * scale
    scale = (anchor2_ms - anchor1_ms) / (old_t2 - old_t1)

    changes: list[TimingChange] = []
    for i, entry in enumerate(entries):
        new_start = int(round(anchor1_ms + (entry.start_ms - old_t1) * scale))
        new_end = int(round(anchor1_ms + (entry.end_ms - old_t1) * scale))
        new_start = max(0, new_start)
        new_end = max(new_start + 1, new_end)
        changes.append((i, entry.start_ms, entry.end_ms, new_start, new_end))
    return changes


def fps_drift_correction(
    document: SubtitleDocument,
    source_fps: float,
    target_fps: float,
) -> list[TimingChange]:
    """Correct timing drift caused by frame-rate mismatch.

    Scales all timestamps by target_fps / source_fps.

    Args:
        document: The subtitle document.
        source_fps: The frame rate the subtitles were authored for.
        target_fps: The actual frame rate of the video.

    Returns:
        List of timing change tuples.
    """
    if source_fps <= 0 or target_fps <= 0:
        return []

    factor = source_fps / target_fps
    changes: list[TimingChange] = []
    for i, entry in enumerate(document.entries):
        new_start = max(0, int(round(entry.start_ms * factor)))
        new_end = max(new_start + 1, int(round(entry.end_ms * factor)))
        changes.append((i, entry.start_ms, entry.end_ms, new_start, new_end))
    return changes


def silence_snap(
    document: SubtitleDocument,
    silence_intervals: list[tuple[float, float]],
    snap_threshold_ms: int = 200,
) -> list[TimingChange]:
    """Snap subtitle boundaries to nearby silence edges.

    For each entry boundary (start or end), if a silence edge is within
    *snap_threshold_ms*, move the boundary to that silence edge.

    Args:
        document: The subtitle document.
        silence_intervals: List of (start_s, end_s) silence intervals in seconds.
        snap_threshold_ms: Maximum distance (ms) for snapping.

    Returns:
        List of timing change tuples.
    """
    if not silence_intervals:
        return []

    # Convert silence intervals to ms
    silence_edges_ms: list[int] = []
    for s, e in silence_intervals:
        silence_edges_ms.append(int(round(s * 1000)))
        silence_edges_ms.append(int(round(e * 1000)))
    silence_edges_ms.sort()

    def _nearest_edge(time_ms: int) -> Optional[int]:
        """Find the nearest silence edge within threshold."""
        best: Optional[int] = None
        best_dist = snap_threshold_ms + 1
        for edge in silence_edges_ms:
            dist = abs(edge - time_ms)
            if dist < best_dist:
                best_dist = dist
                best = edge
        return best if best_dist <= snap_threshold_ms else None

    changes: list[TimingChange] = []
    for i, entry in enumerate(document.entries):
        new_start = entry.start_ms
        new_end = entry.end_ms

        snapped_start = _nearest_edge(entry.start_ms)
        if snapped_start is not None:
            new_start = snapped_start

        snapped_end = _nearest_edge(entry.end_ms)
        if snapped_end is not None:
            new_end = snapped_end

        # Ensure validity
        if new_end <= new_start:
            new_end = new_start + 1

        if new_start != entry.start_ms or new_end != entry.end_ms:
            changes.append((i, entry.start_ms, entry.end_ms, new_start, new_end))

    return changes


def reapply_word_timing(
    document: SubtitleDocument,
    json_bundle_data: dict,
) -> list[TimingChange]:
    """Re-derive entry timing from word-level timestamps in a JSON bundle.

    Expects json_bundle_data to contain a "words" key with a list of
    {"start": float, "end": float, "text": str} dicts.

    For each entry, we find the words that best match the entry text
    and use their timing.

    Args:
        document: The subtitle document.
        json_bundle_data: Dict with a "words" list of word-level timing data.

    Returns:
        List of timing change tuples.
    """
    words = json_bundle_data.get("words", [])
    if not words:
        return []

    changes: list[TimingChange] = []
    word_idx = 0

    for i, entry in enumerate(document.entries):
        entry_words = entry.text.split()
        if not entry_words:
            continue

        # Find the best word-index offset for this entry
        best_start_idx = word_idx
        matched_count = 0

        # Simple greedy forward match
        scan_idx = word_idx
        while scan_idx < len(words) and matched_count < len(entry_words):
            w_text = words[scan_idx].get("text", "").strip().lower()
            e_text = entry_words[matched_count].strip().lower()
            if w_text == e_text or w_text.rstrip(".,!?;:") == e_text.rstrip(".,!?;:"):
                if matched_count == 0:
                    best_start_idx = scan_idx
                matched_count += 1
            elif matched_count > 0:
                # Reset match
                matched_count = 0
                best_start_idx = scan_idx + 1
            scan_idx += 1

        if matched_count > 0:
            first_word = words[best_start_idx]
            last_word = words[best_start_idx + matched_count - 1]
            new_start = int(round(first_word["start"] * 1000))
            new_end = int(round(last_word["end"] * 1000))
            new_start = max(0, new_start)
            new_end = max(new_start + 1, new_end)

            if new_start != entry.start_ms or new_end != entry.end_ms:
                changes.append((i, entry.start_ms, entry.end_ms, new_start, new_end))
            word_idx = best_start_idx + matched_count

    return changes
