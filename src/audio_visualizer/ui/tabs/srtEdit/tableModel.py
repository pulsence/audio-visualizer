"""Qt table model backed by SubtitleDocument.

Provides SubtitleTableModel (QAbstractTableModel) that exposes subtitle
entries as an editable table with columns for index, start, end,
duration, text, and speaker.
"""
from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from audio_visualizer.ui.tabs.srtEdit.document import SubtitleDocument

logger = logging.getLogger(__name__)

# Column definitions
COL_INDEX = 0
COL_START = 1
COL_END = 2
COL_DURATION = 3
COL_TEXT = 4
COL_SPEAKER = 5
COLUMN_COUNT = 6

COLUMN_HEADERS = ("#", "Start", "End", "Duration", "Text", "Speaker")


def _ms_to_timestamp(ms: int) -> str:
    """Convert milliseconds to HH:MM:SS.mmm display string."""
    if ms < 0:
        ms = 0
    total_seconds = ms // 1000
    millis = ms % 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def _timestamp_to_ms(text: str) -> int | None:
    """Parse a HH:MM:SS.mmm or HH:MM:SS,mmm timestamp to milliseconds.

    Returns None if parsing fails.
    """
    text = text.strip().replace(",", ".")
    parts = text.split(":")
    try:
        if len(parts) == 3:
            h, m = int(parts[0]), int(parts[1])
            sec_parts = parts[2].split(".")
            s = int(sec_parts[0])
            ms = int(sec_parts[1].ljust(3, "0")[:3]) if len(sec_parts) > 1 else 0
            return (h * 3600 + m * 60 + s) * 1000 + ms
        elif len(parts) == 2:
            m = int(parts[0])
            sec_parts = parts[1].split(".")
            s = int(sec_parts[0])
            ms = int(sec_parts[1].ljust(3, "0")[:3]) if len(sec_parts) > 1 else 0
            return (m * 60 + s) * 1000 + ms
    except (ValueError, IndexError):
        pass
    return None


class SubtitleTableModel(QAbstractTableModel):
    """Table model that exposes SubtitleDocument entries.

    Editable columns: Start, End, Text, Speaker.
    Read-only columns: #, Duration.
    """

    def __init__(self, document: SubtitleDocument, parent: Any = None) -> None:
        super().__init__(parent)
        self._document = document

    @property
    def document(self) -> SubtitleDocument:
        """Return the backing SubtitleDocument."""
        return self._document

    def set_document(self, document: SubtitleDocument) -> None:
        """Replace the backing document and refresh the view."""
        self.beginResetModel()
        self._document = document
        self.endResetModel()

    # ------------------------------------------------------------------
    # QAbstractTableModel interface
    # ------------------------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._document.entries)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return COLUMN_COUNT

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(COLUMN_HEADERS):
                return COLUMN_HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self._document.entries):
            return None

        entry = self._document.entries[row]

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            if col == COL_INDEX:
                return entry.index
            elif col == COL_START:
                return _ms_to_timestamp(entry.start_ms)
            elif col == COL_END:
                return _ms_to_timestamp(entry.end_ms)
            elif col == COL_DURATION:
                return _ms_to_timestamp(max(0, entry.end_ms - entry.start_ms))
            elif col == COL_TEXT:
                return entry.text
            elif col == COL_SPEAKER:
                return entry.speaker or ""

        if role == Qt.ItemDataRole.BackgroundRole:
            if entry.dirty:
                from PySide6.QtGui import QColor
                return QColor(255, 255, 200)

        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        base_flags = super().flags(index)
        if not index.isValid():
            return base_flags
        col = index.column()
        if col in (COL_START, COL_END, COL_TEXT, COL_SPEAKER):
            return base_flags | Qt.ItemFlag.ItemIsEditable
        return base_flags

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False
        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self._document.entries):
            return False

        entry = self._document.entries[row]

        if col == COL_START:
            ms = _timestamp_to_ms(str(value))
            if ms is None:
                return False
            self._document.update_entry(row, start_ms=ms)
        elif col == COL_END:
            ms = _timestamp_to_ms(str(value))
            if ms is None:
                return False
            self._document.update_entry(row, end_ms=ms)
        elif col == COL_TEXT:
            self._document.update_entry(row, text=str(value))
        elif col == COL_SPEAKER:
            val = str(value).strip()
            self._document.update_entry(row, speaker=val if val else None)
        else:
            return False

        self.dataChanged.emit(index, index, [role])
        return True

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    def get_entry(self, row: int):
        """Return the SubtitleEntry at *row*, or None."""
        if 0 <= row < len(self._document.entries):
            return self._document.entries[row]
        return None

    def refresh(self) -> None:
        """Emit a full model reset so the view redraws."""
        self.beginResetModel()
        self.endResetModel()

    def notify_rows_changed(self, first: int, last: int) -> None:
        """Emit dataChanged for a range of rows."""
        if first < 0:
            first = 0
        if last >= len(self._document.entries):
            last = len(self._document.entries) - 1
        if first > last:
            return
        top_left = self.index(first, 0)
        bottom_right = self.index(last, COLUMN_COUNT - 1)
        self.dataChanged.emit(top_left, bottom_right)
