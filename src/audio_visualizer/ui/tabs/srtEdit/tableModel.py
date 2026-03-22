"""Qt table model backed by SubtitleDocument.

Provides SubtitleTableModel (QAbstractTableModel) that exposes subtitle
entries as an editable table with columns for index, start, end,
duration, text, and speaker.

Supports expand/collapse per subtitle row to show inline word rows
below the parent entry.  Word rows display indented word text, start
time, and end time with inline editing.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QEvent, QModelIndex, Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import QPlainTextEdit, QStyledItemDelegate, QWidget

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


def _seconds_to_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS.mmm display string."""
    return _ms_to_timestamp(int(round(seconds * 1000)))


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


@dataclass
class _RowMapping:
    """Mapping from a display row to underlying data.

    For subtitle rows: entry_index is set, word_index is -1.
    For word rows: both entry_index and word_index are set.
    """

    entry_index: int
    word_index: int = -1  # -1 means subtitle row

    @property
    def is_word_row(self) -> bool:
        return self.word_index >= 0


class SubtitleTableModel(QAbstractTableModel):
    """Table model that exposes SubtitleDocument entries.

    Editable columns: Start, End, Text, Speaker.
    Read-only columns: #, Duration.

    Supports expand/collapse per subtitle row to show inline word rows
    below the parent, with a stable mapping from display rows to
    subtitle/word indices.
    """

    inline_edit_requested = Signal(int, int, object)  # row, column, value
    word_edit_requested = Signal(int, int, int, object)  # entry_idx, word_idx, column, value
    word_selected = Signal(int, int)  # entry_index, word_index

    def __init__(self, document: SubtitleDocument, parent: Any = None) -> None:
        super().__init__(parent)
        self._document = document
        self._expanded: set[int] = set()  # set of expanded entry indices
        self._row_map: list[_RowMapping] = []
        self._rebuild_row_map()

    @property
    def document(self) -> SubtitleDocument:
        """Return the backing SubtitleDocument."""
        return self._document

    def set_document(self, document: SubtitleDocument) -> None:
        """Replace the backing document and refresh the view."""
        self.beginResetModel()
        self._document = document
        self._expanded.clear()
        self._rebuild_row_map()
        self.endResetModel()

    # ------------------------------------------------------------------
    # Expand / collapse
    # ------------------------------------------------------------------

    def toggle_expand(self, entry_index: int) -> None:
        """Toggle expand/collapse for the given subtitle entry index."""
        if entry_index in self._expanded:
            self._expanded.discard(entry_index)
        else:
            self._expanded.add(entry_index)
        self.beginResetModel()
        self._rebuild_row_map()
        self.endResetModel()

    def is_expanded(self, entry_index: int) -> bool:
        """Return True if the given entry has its word rows expanded."""
        return entry_index in self._expanded

    def collapse_all(self) -> None:
        """Collapse all expanded entries."""
        self.beginResetModel()
        self._expanded.clear()
        self._rebuild_row_map()
        self.endResetModel()

    # ------------------------------------------------------------------
    # Row mapping
    # ------------------------------------------------------------------

    def row_mapping(self, row: int) -> _RowMapping | None:
        """Return the row mapping for a display row, or None."""
        if 0 <= row < len(self._row_map):
            return self._row_map[row]
        return None

    def entry_index_for_row(self, row: int) -> int:
        """Return the subtitle entry index for a display row, or -1."""
        mapping = self.row_mapping(row)
        if mapping is not None:
            return mapping.entry_index
        return -1

    def subtitle_row_for_entry(self, entry_index: int) -> int:
        """Return the display row for a subtitle entry, or -1."""
        for i, m in enumerate(self._row_map):
            if m.entry_index == entry_index and not m.is_word_row:
                return i
        return -1

    def word_row_for(self, entry_index: int, word_index: int) -> int:
        """Return the display row for a specific word, or -1."""
        for i, m in enumerate(self._row_map):
            if m.entry_index == entry_index and m.word_index == word_index:
                return i
        return -1

    def _rebuild_row_map(self) -> None:
        """Rebuild the flat row map from document entries and expansion state."""
        self._row_map.clear()
        for i, entry in enumerate(self._document.entries):
            self._row_map.append(_RowMapping(entry_index=i))
            if i in self._expanded and entry.words:
                for wi in range(len(entry.words)):
                    self._row_map.append(_RowMapping(entry_index=i, word_index=wi))

    # ------------------------------------------------------------------
    # QAbstractTableModel interface
    # ------------------------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._row_map)

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
        if row < 0 or row >= len(self._row_map):
            return None

        mapping = self._row_map[row]

        if mapping.is_word_row:
            return self._word_data(mapping, col, role)
        return self._entry_data(mapping, col, role)

    def _entry_data(self, mapping: _RowMapping, col: int, role: int) -> Any:
        """Return data for a subtitle entry row."""
        entry_idx = mapping.entry_index
        if entry_idx < 0 or entry_idx >= len(self._document.entries):
            return None
        entry = self._document.entries[entry_idx]

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if col == COL_INDEX:
                # Show expand indicator when words are available
                prefix = ""
                if entry.words:
                    prefix = "- " if entry_idx in self._expanded else "+ "
                return f"{prefix}{entry.index}"
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
                from PySide6.QtGui import QColor, QPalette
                from PySide6.QtWidgets import QApplication
                palette = QApplication.palette()
                base = palette.color(QPalette.ColorRole.Base)
                if base.lightness() < 128:
                    return QColor(60, 55, 40)
                else:
                    return QColor(255, 255, 220)

        return None

    def _word_data(self, mapping: _RowMapping, col: int, role: int) -> Any:
        """Return data for an inline word row."""
        entry_idx = mapping.entry_index
        word_idx = mapping.word_index
        if entry_idx < 0 or entry_idx >= len(self._document.entries):
            return None
        entry = self._document.entries[entry_idx]
        if word_idx < 0 or word_idx >= len(entry.words):
            return None
        word = entry.words[word_idx]

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if col == COL_INDEX:
                return ""  # No index for word rows
            elif col == COL_START:
                return _seconds_to_timestamp(word.start)
            elif col == COL_END:
                return _seconds_to_timestamp(word.end)
            elif col == COL_DURATION:
                dur = max(0.0, word.end - word.start)
                return _ms_to_timestamp(int(round(dur * 1000)))
            elif col == COL_TEXT:
                return f"    {word.text}"  # Indented for visual hierarchy
            elif col == COL_SPEAKER:
                return ""

        if role == Qt.ItemDataRole.FontRole:
            if col == COL_TEXT:
                font = QFont()
                font.setItalic(True)
                return font

        if role == Qt.ItemDataRole.BackgroundRole:
            from PySide6.QtGui import QColor, QPalette
            from PySide6.QtWidgets import QApplication
            palette = QApplication.palette()
            base = palette.color(QPalette.ColorRole.Base)
            if base.lightness() < 128:
                return QColor(45, 45, 55)
            else:
                return QColor(235, 235, 245)

        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        base_flags = super().flags(index)
        if not index.isValid():
            return base_flags
        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self._row_map):
            return base_flags

        mapping = self._row_map[row]

        if mapping.is_word_row:
            # Word rows: start, end, text editable
            if col in (COL_START, COL_END, COL_TEXT):
                return base_flags | Qt.ItemFlag.ItemIsEditable
            return base_flags

        # Subtitle entry rows
        if col in (COL_START, COL_END, COL_TEXT, COL_SPEAKER):
            return base_flags | Qt.ItemFlag.ItemIsEditable
        return base_flags

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False
        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self._row_map):
            return False

        mapping = self._row_map[row]

        if mapping.is_word_row:
            return self._set_word_data(mapping, col, value)

        return self._set_entry_data(mapping, col, value)

    def _set_entry_data(self, mapping: _RowMapping, col: int, value: Any) -> bool:
        """Handle setData for a subtitle entry row."""
        entry_idx = mapping.entry_index
        if entry_idx < 0 or entry_idx >= len(self._document.entries):
            return False

        if col == COL_START:
            ms = _timestamp_to_ms(str(value))
            if ms is None:
                return False
            self.inline_edit_requested.emit(entry_idx, col, ms)
        elif col == COL_END:
            ms = _timestamp_to_ms(str(value))
            if ms is None:
                return False
            self.inline_edit_requested.emit(entry_idx, col, ms)
        elif col == COL_TEXT:
            self.inline_edit_requested.emit(entry_idx, col, str(value))
        elif col == COL_SPEAKER:
            val = str(value).strip()
            self.inline_edit_requested.emit(entry_idx, col, val if val else None)
        else:
            return False

        return True

    def _set_word_data(self, mapping: _RowMapping, col: int, value: Any) -> bool:
        """Handle setData for a word row."""
        entry_idx = mapping.entry_index
        word_idx = mapping.word_index

        if col == COL_START:
            ms = _timestamp_to_ms(str(value))
            if ms is None:
                return False
            self.word_edit_requested.emit(entry_idx, word_idx, col, ms / 1000.0)
        elif col == COL_END:
            ms = _timestamp_to_ms(str(value))
            if ms is None:
                return False
            self.word_edit_requested.emit(entry_idx, word_idx, col, ms / 1000.0)
        elif col == COL_TEXT:
            text = str(value).strip()
            self.word_edit_requested.emit(entry_idx, word_idx, col, text)
        else:
            return False

        return True

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    def get_entry(self, row: int):
        """Return the SubtitleEntry at *row*, or None."""
        if 0 <= row < len(self._row_map):
            mapping = self._row_map[row]
            if not mapping.is_word_row:
                idx = mapping.entry_index
                if 0 <= idx < len(self._document.entries):
                    return self._document.entries[idx]
        return None

    def refresh(self) -> None:
        """Emit a full model reset so the view redraws."""
        self.beginResetModel()
        self._rebuild_row_map()
        self.endResetModel()

    def notify_rows_changed(self, first: int, last: int) -> None:
        """Emit dataChanged for a range of rows.

        The arguments are *entry indices* (not display rows).  This
        method translates them to the display row range, accounting
        for any expanded word rows in between.
        """
        if first < 0:
            first = 0
        if last >= len(self._document.entries):
            last = len(self._document.entries) - 1
        if first > last:
            return
        # Find display row range covering these entry indices
        first_display = None
        last_display = None
        for i, m in enumerate(self._row_map):
            if m.entry_index >= first and first_display is None:
                first_display = i
            if m.entry_index <= last:
                last_display = i
        if first_display is None or last_display is None:
            return
        top_left = self.index(first_display, 0)
        bottom_right = self.index(last_display, COLUMN_COUNT - 1)
        self.dataChanged.emit(top_left, bottom_right)


class MultilineTextDelegate(QStyledItemDelegate):
    """Delegate that uses a QPlainTextEdit for multiline editing.

    Shift+Enter inserts a newline. Enter commits the edit.
    """

    def createEditor(self, parent: QWidget, option, index: QModelIndex) -> QWidget:
        editor = QPlainTextEdit(parent)
        editor.setFrameShape(QPlainTextEdit.Shape.NoFrame)
        editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        return editor

    def setEditorData(self, editor: QPlainTextEdit, index: QModelIndex) -> None:
        text = index.data(Qt.ItemDataRole.EditRole)
        if text is not None:
            editor.setPlainText(str(text))

    def setModelData(self, editor: QPlainTextEdit, model, index: QModelIndex) -> None:
        model.setData(index, editor.toPlainText(), Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor: QWidget, option, index: QModelIndex) -> None:
        editor.setGeometry(option.rect)

    def eventFilter(self, editor: QWidget, event: QEvent) -> bool:
        if isinstance(event, QKeyEvent):
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    # Shift+Enter: insert newline
                    return False  # Let the editor handle it
                else:
                    # Enter without Shift: commit the edit
                    self.commitData.emit(editor)
                    self.closeEditor.emit(editor)
                    return True
        return super().eventFilter(editor, event)
