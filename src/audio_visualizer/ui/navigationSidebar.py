"""Navigation sidebar widget for the multi-tab application shell.

Provides a vertical sidebar with a heading label and a QListWidget that
displays one entry per registered tab.  Each entry stores its tab_id as
item data, supports a busy-spinner indicator, and emits a signal when the
user selects a different tab.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

SIDEBAR_WIDTH = 180
SPINNER_PREFIX = "\u27f3 "  # "⟳ "


class NavigationSidebar(QWidget):
    """Vertical sidebar listing registered tabs for quick navigation.

    Signals
    -------
    tab_selected(int)
        Emitted when the user clicks a tab entry.  The payload is the
        row index of the selected item.
    """

    tab_selected = Signal(int)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(SIDEBAR_WIDTH)

        self._list = QListWidget()
        self._list.setObjectName("navigationList")
        self._list.setSpacing(2)

        heading = QLabel("Navigation")
        heading.setObjectName("navigationHeading")
        heading.setAlignment(Qt.AlignmentFlag.AlignLeft)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(heading)
        layout.addWidget(self._list)

        self._list.currentRowChanged.connect(self._on_row_changed)

        self._apply_styles()
        logger.debug("NavigationSidebar initialised (width=%d)", SIDEBAR_WIDTH)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_tab(self, tab_id: str, title: str, index: int) -> None:
        """Add a navigation entry for a tab.

        Parameters
        ----------
        tab_id : str
            Stable identifier stored as ``Qt.ItemDataRole.UserRole`` data.
        title : str
            Display text for the list entry.
        index : int
            Position at which to insert the entry.  Use ``-1`` or a value
            equal to the current count to append.
        """
        item = QListWidgetItem(title)
        item.setData(Qt.ItemDataRole.UserRole, tab_id)
        if index < 0 or index >= self._list.count():
            self._list.addItem(item)
        else:
            self._list.insertItem(index, item)
        logger.debug(
            "Tab added to sidebar: id='%s', title='%s', index=%d",
            tab_id,
            title,
            index,
        )

    def set_active(self, index: int) -> None:
        """Highlight the tab at *index* as the active entry.

        Parameters
        ----------
        index : int
            Row index of the entry to activate.  Out-of-range values
            are silently ignored.
        """
        if index < 0 or index >= self._list.count():
            logger.warning(
                "set_active called with out-of-range index %d (count=%d)",
                index,
                self._list.count(),
            )
            return
        self._list.blockSignals(True)
        self._list.setCurrentRow(index)
        self._list.blockSignals(False)

    def set_busy(self, index: int, busy: bool) -> None:
        """Show or hide a busy spinner on the tab entry at *index*.

        When *busy* is ``True`` a spinner character is prepended to the
        item text.  When ``False`` the spinner prefix is removed.

        Parameters
        ----------
        index : int
            Row index of the entry to update.
        busy : bool
            Whether to show the busy indicator.
        """
        item = self._list.item(index)
        if item is None:
            logger.warning(
                "set_busy called with invalid index %d (count=%d)",
                index,
                self._list.count(),
            )
            return

        text = item.text()
        has_spinner = text.startswith(SPINNER_PREFIX)

        if busy and not has_spinner:
            item.setText(SPINNER_PREFIX + text)
        elif not busy and has_spinner:
            item.setText(text[len(SPINNER_PREFIX):])

    def get_active_index(self) -> int:
        """Return the row index of the currently selected entry.

        Returns
        -------
        int
            The current row, or ``-1`` if nothing is selected.
        """
        return self._list.currentRow()

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    def _on_row_changed(self, row: int) -> None:
        """Handle ``currentRowChanged`` from the internal list widget."""
        if row >= 0:
            logger.debug("Sidebar selection changed to row %d", row)
            self.tab_selected.emit(row)

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------

    def _apply_styles(self) -> None:
        """Apply minimal stylesheet to the sidebar and its children."""
        self.setStyleSheet(
            """
            #navigationHeading {
                font-weight: bold;
                padding: 4px 2px;
            }
            #navigationList {
                border: none;
                padding: 2px;
            }
            #navigationList::item {
                padding: 4px 6px;
            }
            #navigationList::item:selected {
                background-color: palette(highlight);
                color: palette(highlighted-text);
            }
            """
        )
