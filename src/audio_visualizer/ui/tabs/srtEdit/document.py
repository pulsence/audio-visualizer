"""Subtitle document model for the SRT Edit tab.

Provides SubtitleEntry (a single subtitle cue) and SubtitleDocument
(an ordered collection with mutation helpers, dirty tracking, and
file I/O via the parser module).
"""
from __future__ import annotations

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

    def add_entry(self, entry: SubtitleEntry) -> None:
        """Append a new entry and re-index.

        Args:
            entry: The subtitle entry to add.
        """
        entry.dirty = True
        self._entries.append(entry)
        self._reindex()
        self._dirty = True

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
        if start_ms is not None:
            entry.start_ms = start_ms
        if end_ms is not None:
            entry.end_ms = end_ms
        if text is not None:
            entry.text = text
        if speaker is not ...:
            entry.speaker = speaker  # type: ignore[assignment]
        entry.dirty = True
        self._dirty = True

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
    # Internal helpers
    # ------------------------------------------------------------------

    def _reindex(self) -> None:
        """Re-number entries starting from 1."""
        for i, entry in enumerate(self._entries):
            entry.index = i + 1
