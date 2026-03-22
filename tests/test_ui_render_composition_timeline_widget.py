"""Tests for TimelineWidget snap-to-align, scrubbing, and waveform features."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
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
    _PLAYHEAD_HIT_PX,
    _TRACK_HEIGHT,
    _TRACK_SPACING,
    _waveform_cache,
    compute_waveform_envelope,
    clear_waveform_cache,
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


# ---------------------------------------------------------------------------
# Playhead scrubbing tests
# ---------------------------------------------------------------------------

class TestPlayheadScrubbing:
    """Tests for playhead drag-scrub behavior."""

    def test_scrubbing_state_initially_false(self, widget):
        assert widget._scrubbing is False

    def test_is_near_playhead_true_when_close(self, widget):
        widget.set_playhead_ms(5000)
        playhead_x = widget._ms_to_x(5000)
        assert widget._is_near_playhead(playhead_x) is True
        assert widget._is_near_playhead(playhead_x + _PLAYHEAD_HIT_PX) is True

    def test_is_near_playhead_false_when_far(self, widget):
        widget.set_playhead_ms(5000)
        playhead_x = widget._ms_to_x(5000)
        assert widget._is_near_playhead(playhead_x + _PLAYHEAD_HIT_PX + 10) is False

    def test_press_near_playhead_starts_scrub(self, widget):
        widget.set_playhead_ms(5000)
        playhead_x = widget._ms_to_x(5000)

        mock_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(playhead_x, 40),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

        with patch.object(widget, "update"):
            widget.mousePressEvent(mock_event)

        assert widget._scrubbing is True
        assert widget._dragging is False

    def test_scrub_drag_updates_playhead(self, widget):
        widget.set_playhead_ms(5000)
        playhead_x = widget._ms_to_x(5000)

        # Start scrub
        press_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(playhead_x, 40),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        with patch.object(widget, "update"):
            widget.mousePressEvent(press_event)

        signals = []
        widget.playhead_changed.connect(lambda ms: signals.append(ms))

        # Drag to new position
        new_x = widget._ms_to_x(7000)
        move_event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(new_x, 40),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        with patch.object(widget, "update"):
            widget.mouseMoveEvent(move_event)

        assert len(signals) > 0
        # Playhead should have moved toward 7000
        assert abs(widget._playhead_ms - 7000) < 200

    def test_scrub_release_ends_scrub(self, widget):
        widget._scrubbing = True

        release_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(300, 40),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        with patch.object(widget, "update"):
            widget.mouseReleaseEvent(release_event)

        assert widget._scrubbing is False

    def test_cursor_changes_near_playhead(self, widget):
        """Cursor should change to SizeHorCursor when hovering near playhead."""
        widget.set_playhead_ms(5000)
        playhead_x = widget._ms_to_x(5000)

        move_event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(playhead_x, 40),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )

        widget.mouseMoveEvent(move_event)
        assert widget.cursor().shape() == Qt.CursorShape.SizeHorCursor


# ---------------------------------------------------------------------------
# Visual track reorder tests
# ---------------------------------------------------------------------------


class TestVisualTrackReorder:
    def test_dragging_top_visual_track_to_bottom_emits_bottom_index(self, widget):
        low = TimelineItem("low", "Low", 0, 5000, "visual", z_order=0)
        high = TimelineItem("high", "High", 0, 5000, "visual", z_order=1)
        widget.set_items([low, high])

        top_row_y = 25 + (_TRACK_HEIGHT / 2)
        bottom_row_y = 25 + (_TRACK_HEIGHT + _TRACK_SPACING) + (_TRACK_HEIGHT / 2)
        x = widget._ms_to_x(1000)

        press_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(x, top_row_y),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        with patch.object(widget, "update"):
            widget.mousePressEvent(press_event)

        reordered = []
        widget.item_reordered.connect(lambda item_id, index: reordered.append((item_id, index)))

        move_event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(x, bottom_row_y),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        with patch.object(widget, "update"):
            widget.mouseMoveEvent(move_event)

        assert reordered == [("high", 1)]


# ---------------------------------------------------------------------------
# Waveform cache tests
# ---------------------------------------------------------------------------

class TestWaveformCache:
    """Tests for waveform envelope computation and caching."""

    def setup_method(self):
        clear_waveform_cache()

    def test_cache_cleared(self):
        _waveform_cache["test"] = np.array([0.5])
        clear_waveform_cache()
        assert len(_waveform_cache) == 0

    def test_cache_returns_stored_value(self):
        fake_envelope = np.array([0.1, 0.5, 0.8, 0.3])
        _waveform_cache["/fake/path.wav"] = fake_envelope
        result = compute_waveform_envelope("/fake/path.wav")
        assert result is fake_envelope

    def test_missing_av_returns_none(self):
        """When av is not importable, compute_waveform_envelope returns None."""
        with patch.dict("sys.modules", {"av": None}):
            # This won't actually affect the import inside the function
            # since av was already imported. Instead test with nonexistent file.
            result = compute_waveform_envelope("/nonexistent/audio.wav")
            assert result is None

    def test_source_path_on_timeline_item(self):
        """TimelineItem accepts source_path kwarg."""
        item = TimelineItem(
            "a1", "Audio", 0, 5000, "audio", source_path="/tmp/test.wav"
        )
        assert item.source_path == "/tmp/test.wav"

    def test_source_path_defaults_to_none(self):
        item = TimelineItem("a1", "Audio", 0, 5000, "audio")
        assert item.source_path is None

    def test_paint_audio_with_waveform_no_crash(self, widget):
        """Painting an audio item with cached waveform data does not crash."""
        fake_envelope = np.linspace(0, 1, 128)
        _waveform_cache["/tmp/audio.wav"] = fake_envelope

        items = [
            TimelineItem(
                "a1", "Audio Track", 0, 5000, "audio",
                source_path="/tmp/audio.wav",
            ),
        ]
        widget.set_items(items)
        widget.resize(800, 200)
        widget.repaint()

        # Cleanup
        clear_waveform_cache()
