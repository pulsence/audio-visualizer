"""QUndoCommand subclasses for SRT Edit undo/redo support.

Each command encapsulates a reversible edit operation on a
SubtitleDocument, storing enough state to undo and redo the change.
"""
from __future__ import annotations

import copy
import logging
from typing import Any

from PySide6.QtGui import QUndoCommand

from audio_visualizer.ui.tabs.srtEdit.document import SubtitleDocument, SubtitleEntry

logger = logging.getLogger(__name__)


class EditTextCommand(QUndoCommand):
    """Change the text of a subtitle entry."""

    def __init__(
        self,
        document: SubtitleDocument,
        index: int,
        new_text: str,
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._index = index
        self._old_text = document.entries[index].text
        self._new_text = new_text
        self.setText(f"Edit text at #{index + 1}")

    def redo(self) -> None:
        self._document.update_entry(self._index, text=self._new_text)

    def undo(self) -> None:
        self._document.update_entry(self._index, text=self._old_text)


class EditTimestampCommand(QUndoCommand):
    """Change start and/or end time of a subtitle entry."""

    def __init__(
        self,
        document: SubtitleDocument,
        index: int,
        new_start_ms: int | None = None,
        new_end_ms: int | None = None,
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._index = index
        entry = document.entries[index]
        self._old_start_ms = entry.start_ms
        self._old_end_ms = entry.end_ms
        self._new_start_ms = new_start_ms if new_start_ms is not None else entry.start_ms
        self._new_end_ms = new_end_ms if new_end_ms is not None else entry.end_ms
        self.setText(f"Edit timestamp at #{index + 1}")

    def redo(self) -> None:
        self._document.update_entry(
            self._index,
            start_ms=self._new_start_ms,
            end_ms=self._new_end_ms,
        )

    def undo(self) -> None:
        self._document.update_entry(
            self._index,
            start_ms=self._old_start_ms,
            end_ms=self._old_end_ms,
        )


class AddEntryCommand(QUndoCommand):
    """Add a new subtitle entry to the document."""

    def __init__(
        self,
        document: SubtitleDocument,
        entry: SubtitleEntry,
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._entry = copy.deepcopy(entry)
        self._inserted_index: int | None = None
        self.setText("Add subtitle entry")

    def redo(self) -> None:
        self._document.add_entry(copy.deepcopy(self._entry))
        self._inserted_index = len(self._document.entries) - 1

    def undo(self) -> None:
        if self._inserted_index is not None:
            self._document.remove_entry(self._inserted_index)


class RemoveEntryCommand(QUndoCommand):
    """Remove a subtitle entry from the document."""

    def __init__(
        self,
        document: SubtitleDocument,
        index: int,
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._index = index
        self._removed_entry = copy.deepcopy(document.entries[index])
        self.setText(f"Remove entry #{index + 1}")

    def redo(self) -> None:
        self._document.remove_entry(self._index)

    def undo(self) -> None:
        self._document.entries.insert(self._index, copy.deepcopy(self._removed_entry))
        self._document._reindex()
        self._document._dirty = True


class SplitEntryCommand(QUndoCommand):
    """Split a subtitle entry at a given time point."""

    def __init__(
        self,
        document: SubtitleDocument,
        index: int,
        split_ms: int,
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._index = index
        self._split_ms = split_ms
        self._original_entry = copy.deepcopy(document.entries[index])
        self.setText(f"Split entry #{index + 1}")

    def redo(self) -> None:
        self._document.split_entry(self._index, self._split_ms)

    def undo(self) -> None:
        # Remove the two split entries and restore the original
        if self._index + 1 < len(self._document.entries):
            self._document.entries.pop(self._index + 1)
        self._document.entries[self._index] = copy.deepcopy(self._original_entry)
        self._document._reindex()
        self._document._dirty = True


class MergeEntriesCommand(QUndoCommand):
    """Merge two adjacent subtitle entries."""

    def __init__(
        self,
        document: SubtitleDocument,
        index1: int,
        index2: int,
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._index1 = min(index1, index2)
        self._index2 = max(index1, index2)
        self._entry1 = copy.deepcopy(document.entries[self._index1])
        self._entry2 = copy.deepcopy(document.entries[self._index2])
        self.setText(f"Merge entries #{self._index1 + 1} and #{self._index2 + 1}")

    def redo(self) -> None:
        self._document.merge_entries(self._index1, self._index2)

    def undo(self) -> None:
        # Remove the merged entry and restore originals
        self._document.entries[self._index1] = copy.deepcopy(self._entry1)
        self._document.entries.insert(self._index2, copy.deepcopy(self._entry2))
        self._document._reindex()
        self._document._dirty = True


class MoveRegionCommand(QUndoCommand):
    """Move (drag) a subtitle's timing region."""

    def __init__(
        self,
        document: SubtitleDocument,
        index: int,
        new_start_ms: int,
        new_end_ms: int,
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._index = index
        entry = document.entries[index]
        self._old_start_ms = entry.start_ms
        self._old_end_ms = entry.end_ms
        self._new_start_ms = new_start_ms
        self._new_end_ms = new_end_ms
        self.setText(f"Move region #{index + 1}")

    def redo(self) -> None:
        self._document.update_entry(
            self._index,
            start_ms=self._new_start_ms,
            end_ms=self._new_end_ms,
        )

    def undo(self) -> None:
        self._document.update_entry(
            self._index,
            start_ms=self._old_start_ms,
            end_ms=self._old_end_ms,
        )


class BatchResyncCommand(QUndoCommand):
    """Apply bulk timing changes from a resync operation.

    Expects a list of (index, old_start, old_end, new_start, new_end) tuples.
    """

    def __init__(
        self,
        document: SubtitleDocument,
        changes: list[tuple[int, int, int, int, int]],
        description: str = "Batch resync",
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._changes = changes
        self.setText(description)

    def redo(self) -> None:
        for idx, _old_s, _old_e, new_s, new_e in self._changes:
            if 0 <= idx < len(self._document.entries):
                self._document.update_entry(idx, start_ms=new_s, end_ms=new_e)

    def undo(self) -> None:
        for idx, old_s, old_e, _new_s, _new_e in self._changes:
            if 0 <= idx < len(self._document.entries):
                self._document.update_entry(idx, start_ms=old_s, end_ms=old_e)
