"""Tests for TimelineWidget snap-to-align feature."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure src is on the path (mirrors conftest.py)
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QMouseEvent

from audio_visualizer.ui.tabs.renderComposition.timelineWidget import (
    TimelineItem,
    TimelineWidget,
    _SNAP_THRESHOLD_MS,
)


# Ensure a QApplication exists for widget tests.
@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def widget(qapp):
    w = TimelineWidget()
    w.resize(1100, 200)  # gives 1000px of available width (minus 100 header)
    return w


# ---------------------------------------------------------------------------
# _snap_value tests
# ---------------------------------------------------------------------------

class TestSnapValue:
    """Tests for TimelineWidget._snap_value()."""

    def test_snaps_when_within_threshold(self, widget):
        """_snap_value returns snapped ms when within threshold."""
        items = [
            TimelineItem("a", "A", 1000, 3000),
            TimelineItem("b", "B", 5000, 7000),
        ]
        widget.set_items(items)

        # 4900 is 100ms away from item B's start (5000) => within 200ms threshold
        result = widget._snap_value(4900, "a")
        assert result == 5000

    def test_returns_original_when_no_nearby_edge(self, widget):
        """_snap_value returns original ms when no edge is nearby."""
        items = [
            TimelineItem("a", "A", 1000, 2000),
            TimelineItem("b", "B", 5000, 7000),
        ]
        widget.set_items(items)

        # 3500 is 1500ms from nearest edge (2000) => well outside threshold
        result = widget._snap_value(3500, "a")
        assert result == 3500

    def test_excludes_item_with_exclude_id(self, widget):
        """_snap_value ignores edges from the excluded item."""
        items = [
            TimelineItem("a", "A", 1000, 2000),
            TimelineItem("b", "B", 5000, 7000),
        ]
        widget.set_items(items)

        # 1050 is 50ms from item A's start (1000), but item A is excluded.
        # Nearest non-excluded edge is item B's start (5000) => 3950ms away.
        result = widget._snap_value(1050, "a")
        assert result == 1050

    def test_snaps_to_closest_edge(self, widget):
        """_snap_value snaps to the closest edge when multiple are nearby."""
        items = [
            TimelineItem("a", "A", 1000, 2000),
            TimelineItem("b", "B", 2100, 4000),
            TimelineItem("c", "C", 6000, 8000),
        ]
        widget.set_items(items)

        # 2050 is 50ms from A.end (2000) and 50ms from B.start (2100).
        # Both within threshold; should return the closer one or equal.
        result = widget._snap_value(2050, "c")
        assert result in (2000, 2100)  # either is valid; min picks 2000
        assert result == 2000  # min picks the first one checked (2000)

    def test_returns_original_when_only_excluded_item(self, widget):
        """_snap_value returns original ms when the only item is excluded."""
        items = [
            TimelineItem("a", "A", 1000, 2000),
        ]
        widget.set_items(items)

        result = widget._snap_value(1050, "a")
        assert result == 1050

    def test_returns_original_when_no_items(self, widget):
        """_snap_value returns original ms when there are no items."""
        widget.set_items([])
        result = widget._snap_value(500, "nonexistent")
        assert result == 500

    def test_snaps_to_end_edge(self, widget):
        """_snap_value can snap to an item's end edge."""
        items = [
            TimelineItem("a", "A", 1000, 3000),
            TimelineItem("b", "B", 5000, 7000),
        ]
        widget.set_items(items)

        # 2900 is 100ms from A's end (3000) => within threshold
        result = widget._snap_value(2900, "b")
        assert result == 3000

    def test_exact_threshold_boundary(self, widget):
        """_snap_value snaps at exactly the threshold distance."""
        items = [
            TimelineItem("a", "A", 1000, 3000),
            TimelineItem("b", "B", 5000, 7000),
        ]
        widget.set_items(items)

        # Exactly _SNAP_THRESHOLD_MS away from edge 5000
        result = widget._snap_value(5000 - _SNAP_THRESHOLD_MS, "a")
        assert result == 5000

    def test_just_outside_threshold(self, widget):
        """_snap_value does NOT snap when just outside the threshold."""
        items = [
            TimelineItem("a", "A", 1000, 3000),
            TimelineItem("b", "B", 5000, 7000),
        ]
        widget.set_items(items)

        # One ms beyond threshold from edge 5000
        result = widget._snap_value(5000 - _SNAP_THRESHOLD_MS - 1, "a")
        assert result == 5000 - _SNAP_THRESHOLD_MS - 1


# ---------------------------------------------------------------------------
# Snap guide line state tests
# ---------------------------------------------------------------------------

class TestSnapGuideLine:
    """Tests for snap guide line state during drag."""

    def test_snap_line_none_initially(self, widget):
        """Snap guide line is None on a fresh widget."""
        assert widget._snap_line_x is None

    def test_snap_line_set_during_move_drag(self, widget):
        """Snap guide line is set when a move drag snaps."""
        items = [
            TimelineItem("a", "A", 1000, 3000),
            TimelineItem("b", "B", 5000, 7000),
        ]
        widget.set_items(items)

        # Simulate drag state for item A (move mode)
        widget._dragging = True
        widget._drag_item_id = "a"
        widget._drag_mode = "move"
        widget._drag_start_x = widget._ms_to_x(1000)
        widget._drag_original_start = 1000
        widget._drag_original_end = 3000

        # Simulate mouse move that would place A's end near B's start (5000)
        # A has duration 2000ms, so if start = 2900, end = 4900 (100ms from 5000)
        target_x = widget._ms_to_x(2900)
        mock_event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(target_x, 40),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

        with patch.object(widget, "update"):
            widget.mouseMoveEvent(mock_event)

        assert widget._snap_line_x is not None

    def test_snap_line_cleared_on_release(self, widget):
        """Snap guide line is cleared on mouse release."""
        widget._snap_line_x = 150.0  # artificially set

        mock_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(200, 40),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

        with patch.object(widget, "update"):
            widget.mouseReleaseEvent(mock_event)

        assert widget._snap_line_x is None

    def test_snap_line_none_when_no_snap(self, widget):
        """Snap guide line remains None when no snap occurs."""
        items = [
            TimelineItem("a", "A", 1000, 2000),
            TimelineItem("b", "B", 8000, 9000),
        ]
        widget.set_items(items)

        # Simulate drag state for item A
        widget._dragging = True
        widget._drag_item_id = "a"
        widget._drag_mode = "move"
        widget._drag_start_x = widget._ms_to_x(1000)
        widget._drag_original_start = 1000
        widget._drag_original_end = 2000

        # Move to 4000ms — far from any other edge
        target_x = widget._ms_to_x(4000)
        mock_event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(target_x, 40),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

        with patch.object(widget, "update"):
            widget.mouseMoveEvent(mock_event)

        assert widget._snap_line_x is None
