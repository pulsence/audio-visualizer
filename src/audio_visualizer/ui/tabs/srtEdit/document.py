"""Subtitle document model for the SRT Edit tab.

Provides SubtitleEntry (a single subtitle cue) and SubtitleDocument
(an ordered collection with mutation helpers, dirty tracking, and
file I/O via the parser module).
"""
from __future__ import annotations

import bisect
import copy
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SubtitleEntry:
    """A single subtitle cue with timing, text, and metadata.

    Attributes:
        index: 1-based display index.
        start_ms: Start time in milliseconds.
        end_ms: End time in milliseconds.
        text: Subtitle text (may contain newlines for multi-line cues).
        speaker: Optional speaker label.
        dirty: Whether this entry has been modified since last save.
        id: Stable identifier for bundle round-tripping.
        words: Word-level timing data from bundle loading.
        original_text: Original text before user edits (provenance).
        source_media_path: Source media path from transcription.
        model_name: Whisper model used for transcription.
        alignment_status: Bundle-from-SRT alignment quality marker.
        alignment_confidence: Bundle-from-SRT alignment confidence score.
    """

    index: int
    start_ms: int
    end_ms: int
    text: str
    speaker: Optional[str] = None
    dirty: bool = False
    id: Optional[str] = None
    words: list = field(default_factory=list)
    original_text: Optional[str] = None
    source_media_path: Optional[str] = None
    model_name: Optional[str] = None
    alignment_status: Optional[str] = None
    alignment_confidence: Optional[float] = None


class SubtitleDocument:
    """Ordered collection of subtitle entries with mutation helpers.

    Supports load/save via pysubs2, add/remove/update/split/merge
    operations, timestamp normalization, and dirty tracking.
    """

    def __init__(self) -> None:
        self._entries: list[SubtitleEntry] = []
        self._dirty: bool = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def entries(self) -> list[SubtitleEntry]:
        """Return the ordered list of subtitle entries."""
        return self._entries

    @property
    def is_dirty(self) -> bool:
        """Return True if any entry has been modified since last save."""
        if self._dirty:
            return True
        return any(e.dirty for e in self._entries)

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    def load_srt(self, path: str) -> None:
        """Parse an .srt file and populate entries.

        Args:
            path: Filesystem path to the .srt file.
        """
        from audio_visualizer.ui.tabs.srtEdit.parser import parse_srt_file

        self._entries = parse_srt_file(path)
        self._dirty = False
        logger.info("Loaded %d entries from %s", len(self._entries), path)

    def save_srt(self, path: str) -> None:
        """Write entries back to an .srt file.

        Args:
            path: Filesystem path for the output .srt file.
        """
        from audio_visualizer.ui.tabs.srtEdit.parser import write_srt_file

        write_srt_file(self._entries, path)
        self.mark_clean()
        logger.info("Saved %d entries to %s", len(self._entries), path)

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def add_entry(self, entry: SubtitleEntry) -> int:
        """Insert a new entry in sorted order by start time and re-index.

        Args:
            entry: The subtitle entry to add.

        Returns:
            The 0-based index where the entry was inserted.
        """
        entry.dirty = True
        # Find insertion point to keep entries sorted by start_ms
        starts = [e.start_ms for e in self._entries]
        pos = bisect.bisect_right(starts, entry.start_ms)
        self._entries.insert(pos, entry)
        self._reindex()
        self._dirty = True
        return pos

    def remove_entry(self, index: int) -> SubtitleEntry:
        """Remove the entry at the given list position and re-index.

        Args:
            index: 0-based list position.

        Returns:
            The removed SubtitleEntry.

        Raises:
            IndexError: If index is out of range.
        """
        if index < 0 or index >= len(self._entries):
            raise IndexError(f"Entry index {index} out of range.")
        removed = self._entries.pop(index)
        self._reindex()
        self._dirty = True
        return removed

    def update_entry(
        self,
        index: int,
        *,
        start_ms: int | None = None,
        end_ms: int | None = None,
        text: str | None = None,
        speaker: str | None = ...,  # type: ignore[assignment]
    ) -> None:
        """Update fields on the entry at the given list position.

        Args:
            index: 0-based list position.
            start_ms: New start time (ms), or None to keep current.
            end_ms: New end time (ms), or None to keep current.
            text: New text, or None to keep current.
            speaker: New speaker label, Ellipsis to keep current, None to clear.
        """
        if index < 0 or index >= len(self._entries):
            raise IndexError(f"Entry index {index} out of range.")
        entry = self._entries[index]
        timing_changed = False
        if start_ms is not None and start_ms != entry.start_ms:
            entry.start_ms = start_ms
            timing_changed = True
        if end_ms is not None and end_ms != entry.end_ms:
            entry.end_ms = end_ms
            timing_changed = True
        if text is not None:
            entry.text = text
        if speaker is not ...:
            entry.speaker = speaker  # type: ignore[assignment]
        entry.dirty = True
        self._dirty = True
        # Re-sort when start time changes break ordering
        if timing_changed:
            self._ensure_sorted()

    def split_entry(self, index: int, split_ms: int) -> None:
        """Split the entry at *index* into two entries at *split_ms*.

        The first entry keeps text up to the midpoint; the second entry
        gets the remainder.  If the text cannot be meaningfully split
        the full text is duplicated.

        Args:
            index: 0-based list position of the entry to split.
            split_ms: Time point (ms) at which to split.

        Raises:
            IndexError: If index is out of range.
            ValueError: If split_ms is outside the entry's time range.
        """
        if index < 0 or index >= len(self._entries):
            raise IndexError(f"Entry index {index} out of range.")
        entry = self._entries[index]
        if split_ms <= entry.start_ms or split_ms >= entry.end_ms:
            raise ValueError(
                f"split_ms={split_ms} must be between start_ms={entry.start_ms} "
                f"and end_ms={entry.end_ms}."
            )

        words = entry.text.split()
        mid = max(1, len(words) // 2)
        text_a = " ".join(words[:mid]) if len(words) > 1 else entry.text
        text_b = " ".join(words[mid:]) if len(words) > 1 else entry.text

        entry_a = SubtitleEntry(
            index=0,
            start_ms=entry.start_ms,
            end_ms=split_ms,
            text=text_a,
            speaker=entry.speaker,
            dirty=True,
        )
        entry_b = SubtitleEntry(
            index=0,
            start_ms=split_ms,
            end_ms=entry.end_ms,
            text=text_b,
            speaker=entry.speaker,
            dirty=True,
        )
        self._entries[index] = entry_a
        self._entries.insert(index + 1, entry_b)
        self._reindex()
        self._dirty = True

    def merge_entries(self, index1: int, index2: int) -> None:
        """Merge two adjacent entries into one.

        The merged entry spans from the earlier start to the later end
        and concatenates the text with a space.

        Args:
            index1: 0-based list position of the first entry.
            index2: 0-based list position of the second entry.

        Raises:
            IndexError: If either index is out of range.
            ValueError: If entries are not adjacent.
        """
        if index1 < 0 or index1 >= len(self._entries):
            raise IndexError(f"Entry index {index1} out of range.")
        if index2 < 0 or index2 >= len(self._entries):
            raise IndexError(f"Entry index {index2} out of range.")
        if abs(index1 - index2) != 1:
            raise ValueError("Can only merge adjacent entries.")

        lo, hi = min(index1, index2), max(index1, index2)
        e1 = self._entries[lo]
        e2 = self._entries[hi]

        merged = SubtitleEntry(
            index=0,
            start_ms=min(e1.start_ms, e2.start_ms),
            end_ms=max(e1.end_ms, e2.end_ms),
            text=f"{e1.text} {e2.text}".strip(),
            speaker=e1.speaker or e2.speaker,
            dirty=True,
        )
        self._entries[lo] = merged
        self._entries.pop(hi)
        self._reindex()
        self._dirty = True

    def normalize_timestamps(self) -> None:
        """Sort entries by start time and fix overlaps.

        Overlapping entries have their end times clamped so that each
        entry ends before the next one begins (with at least a 1 ms gap).
        """
        self._entries.sort(key=lambda e: e.start_ms)
        for i in range(len(self._entries) - 1):
            current = self._entries[i]
            nxt = self._entries[i + 1]
            if current.end_ms > nxt.start_ms:
                current.end_ms = max(current.start_ms + 1, nxt.start_ms - 1)
                current.dirty = True
        self._reindex()
        self._dirty = True

    # ------------------------------------------------------------------
    # Dirty tracking
    # ------------------------------------------------------------------

    def mark_clean(self) -> None:
        """Reset the dirty flag on the document and all entries."""
        self._dirty = False
        for entry in self._entries:
            entry.dirty = False

    # ------------------------------------------------------------------
    # Word-level helpers
    # ------------------------------------------------------------------

    def update_word(
        self,
        entry_index: int,
        word_index: int,
        *,
        text: str | None = None,
        start: float | None = None,
        end: float | None = None,
    ) -> None:
        """Update a word within a subtitle entry.

        Args:
            entry_index: 0-based subtitle index.
            word_index: 0-based word index within the entry's words list.
            text: New word text, or None to keep current.
            start: New start time in seconds, or None to keep current.
            end: New end time in seconds, or None to keep current.
        """
        if entry_index < 0 or entry_index >= len(self._entries):
            raise IndexError(f"Entry index {entry_index} out of range.")
        entry = self._entries[entry_index]
        if word_index < 0 or word_index >= len(entry.words):
            raise IndexError(f"Word index {word_index} out of range for entry {entry_index}.")
        word = entry.words[word_index]
        if text is not None:
            word.text = text
        if start is not None:
            word.start = start
        if end is not None:
            word.end = end
        entry.dirty = True
        self._dirty = True

    def clamp_segment_bounds(self, index: int, new_start_ms: int, new_end_ms: int) -> tuple[int, int]:
        """Clamp proposed segment bounds so they do not overlap neighbors.

        Args:
            index: 0-based entry index.
            new_start_ms: Proposed start time in milliseconds.
            new_end_ms: Proposed end time in milliseconds.

        Returns:
            (clamped_start_ms, clamped_end_ms) that respect neighbor bounds.
        """
        # Clamp against previous entry's end
        if index > 0:
            prev_end = self._entries[index - 1].end_ms
            if new_start_ms < prev_end:
                new_start_ms = prev_end
        # Clamp against next entry's start
        if index < len(self._entries) - 1:
            next_start = self._entries[index + 1].start_ms
            if new_end_ms > next_start:
                new_end_ms = next_start
        # Ensure min duration
        if new_end_ms <= new_start_ms:
            new_end_ms = new_start_ms + 1
        return new_start_ms, new_end_ms

    def clamp_word_bounds(
        self,
        entry_index: int,
        word_index: int,
        new_start: float,
        new_end: float,
    ) -> tuple[float, float]:
        """Clamp proposed word bounds within its parent segment and neighbors.

        Args:
            entry_index: 0-based subtitle index.
            word_index: 0-based word index.
            new_start: Proposed start time in seconds.
            new_end: Proposed end time in seconds.

        Returns:
            (clamped_start, clamped_end).
        """
        entry = self._entries[entry_index]
        seg_start = entry.start_ms / 1000.0
        seg_end = entry.end_ms / 1000.0
        words = entry.words
        # Clamp within parent segment
        new_start = max(new_start, seg_start)
        new_end = min(new_end, seg_end)
        # Clamp against previous word
        if word_index > 0:
            prev_end = words[word_index - 1].end
            new_start = max(new_start, prev_end)
        # Clamp against next word
        if word_index < len(words) - 1:
            next_start = words[word_index + 1].start
            new_end = min(new_end, next_start)
        # Ensure minimum duration
        if new_end <= new_start:
            new_end = new_start + 0.001
        return new_start, new_end

    # ------------------------------------------------------------------
    # Bundle I/O
    # ------------------------------------------------------------------

    def load_bundle(self, path: str) -> None:
        """Load a JSON bundle file and populate entries with word data.

        Uses the normalized bundle reader as the single entry point.

        Args:
            path: Filesystem path to the .json or .bundle.json file.
        """
        from audio_visualizer.srt.io import read_json_bundle

        bundle = read_json_bundle(path)
        entries: list[SubtitleEntry] = []
        for i, sub in enumerate(bundle.get("subtitles", []), start=1):
            entry = SubtitleEntry(
                index=i,
                start_ms=int(round(sub["start"] * 1000)),
                end_ms=int(round(sub["end"] * 1000)),
                text=sub.get("text", ""),
                speaker=sub.get("speaker_label"),
                dirty=False,
                id=sub.get("id"),
                words=list(sub.get("words", [])),
                original_text=sub.get("original_text"),
                source_media_path=sub.get("source_media_path"),
                model_name=sub.get("model_name"),
                alignment_status=sub.get("alignment_status"),
                alignment_confidence=sub.get("alignment_confidence"),
            )
            entries.append(entry)
        self._entries = entries
        self._dirty = False
        logger.info("Loaded bundle with %d entries from %s", len(self._entries), path)

    def save_bundle(self, path: str) -> None:
        """Save the current document as a JSON bundle v2.

        Preserves word timing data and provenance fields.

        Args:
            path: Filesystem path for the output .json file.
        """
        import json
        import os
        from pathlib import Path as _Path

        subtitles = []
        flat_words = []
        for entry in self._entries:
            words_data = []
            for w in entry.words:
                w_dict = {
                    "id": getattr(w, "id", None) or "",
                    "subtitle_id": getattr(w, "subtitle_id", None) or entry.id or "",
                    "text": getattr(w, "text", ""),
                    "start": float(getattr(w, "start", 0)),
                    "end": float(getattr(w, "end", 0)),
                }
                conf = getattr(w, "confidence", None)
                if conf is not None:
                    w_dict["confidence"] = float(conf)
                speaker = getattr(w, "speaker_label", None)
                if speaker is not None:
                    w_dict["speaker_label"] = speaker
                words_data.append(w_dict)
                flat_words.append(w_dict)

            sub_entry = {
                "id": entry.id or "",
                "start": entry.start_ms / 1000.0,
                "end": entry.end_ms / 1000.0,
                "text": entry.text,
                "original_text": entry.original_text or entry.text,
                "words": words_data,
                "source_media_path": entry.source_media_path or "",
                "model_name": entry.model_name or "",
            }
            if entry.speaker:
                sub_entry["speaker_label"] = entry.speaker
            if entry.alignment_status:
                sub_entry["alignment_status"] = entry.alignment_status
            if entry.alignment_confidence is not None:
                sub_entry["alignment_confidence"] = entry.alignment_confidence
            subtitles.append(sub_entry)

        payload = {
            "bundle_version": 2,
            "subtitles": subtitles,
            "words": flat_words,
        }

        out = _Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(out.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, out)
        self.mark_clean()
        logger.info("Saved bundle with %d entries to %s", len(self._entries), path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _reindex(self) -> None:
        """Re-number entries starting from 1."""
        for i, entry in enumerate(self._entries):
            entry.index = i + 1

    def _ensure_sorted(self) -> None:
        """Re-sort entries by start_ms if ordering has been violated."""
        for i in range(len(self._entries) - 1):
            if self._entries[i].start_ms > self._entries[i + 1].start_ms:
                self._entries.sort(key=lambda e: e.start_ms)
                self._reindex()
                return
