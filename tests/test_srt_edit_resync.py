"""Tests for the SRT Edit resync tools."""
from __future__ import annotations

import pytest

from audio_visualizer.ui.tabs.srtEdit.document import SubtitleDocument, SubtitleEntry
from audio_visualizer.ui.tabs.srtEdit.resync import (
    fps_drift_correction,
    global_shift,
    shift_from_cursor,
    two_point_stretch,
)


def _make_doc(*entries_data) -> SubtitleDocument:
    """Helper to create a SubtitleDocument from (start_ms, end_ms, text) tuples."""
    doc = SubtitleDocument()
    for i, (start, end, text) in enumerate(entries_data):
        entry = SubtitleEntry(index=i + 1, start_ms=start, end_ms=end, text=text)
        doc._entries.append(entry)
    return doc


class TestGlobalShift:
    """Test global_shift resync tool."""

    def test_positive_shift(self):
        doc = _make_doc(
            (1000, 3000, "First"),
            (4000, 6000, "Second"),
        )
        changes = global_shift(doc, 500)

        assert len(changes) == 2
        # Each change is (index, old_start, old_end, new_start, new_end)
        assert changes[0] == (0, 1000, 3000, 1500, 3500)
        assert changes[1] == (1, 4000, 6000, 4500, 6500)

    def test_negative_shift(self):
        doc = _make_doc(
            (1000, 3000, "First"),
            (4000, 6000, "Second"),
        )
        changes = global_shift(doc, -500)

        assert len(changes) == 2
        assert changes[0] == (0, 1000, 3000, 500, 2500)
        assert changes[1] == (1, 4000, 6000, 3500, 5500)

    def test_shift_clamps_to_zero(self):
        doc = _make_doc((200, 1000, "Test"))
        changes = global_shift(doc, -500)

        assert len(changes) == 1
        assert changes[0][3] == 0  # new_start clamped to 0
        assert changes[0][4] >= 1  # new_end at least 1

    def test_zero_shift_returns_identity(self):
        doc = _make_doc((1000, 3000, "Test"))
        changes = global_shift(doc, 0)

        assert len(changes) == 1
        assert changes[0] == (0, 1000, 3000, 1000, 3000)

    def test_empty_document(self):
        doc = _make_doc()
        changes = global_shift(doc, 100)
        assert changes == []


class TestShiftFromCursor:
    """Test shift_from_cursor resync tool."""

    def test_shift_from_middle(self):
        doc = _make_doc(
            (1000, 2000, "First"),
            (3000, 4000, "Second"),
            (5000, 6000, "Third"),
        )
        changes = shift_from_cursor(doc, 1, 500)

        # Only entries at index 1 and 2 should be shifted
        assert len(changes) == 2
        assert changes[0] == (1, 3000, 4000, 3500, 4500)
        assert changes[1] == (2, 5000, 6000, 5500, 6500)

    def test_shift_from_first(self):
        doc = _make_doc(
            (1000, 2000, "First"),
            (3000, 4000, "Second"),
        )
        changes = shift_from_cursor(doc, 0, 100)

        assert len(changes) == 2
        assert changes[0] == (0, 1000, 2000, 1100, 2100)
        assert changes[1] == (1, 3000, 4000, 3100, 4100)

    def test_shift_from_last(self):
        doc = _make_doc(
            (1000, 2000, "First"),
            (3000, 4000, "Second"),
        )
        changes = shift_from_cursor(doc, 1, -200)

        assert len(changes) == 1
        assert changes[0] == (1, 3000, 4000, 2800, 3800)

    def test_shift_from_beyond_end(self):
        doc = _make_doc((1000, 2000, "Test"))
        changes = shift_from_cursor(doc, 5, 100)
        assert changes == []


class TestTwoPointStretch:
    """Test two_point_stretch resync tool."""

    def test_basic_stretch(self):
        doc = _make_doc(
            (0, 1000, "First"),
            (2000, 3000, "Second"),
            (4000, 5000, "Third"),
        )
        # Map entry 0 to 0ms, entry 2 to 8000ms
        # Original: anchor1 at 0, anchor2 at 4000
        # Scale = (8000 - 0) / (4000 - 0) = 2.0
        changes = two_point_stretch(doc, 0, 0, 2, 8000)

        assert len(changes) == 3
        # Entry 0: start=0*2=0, end=1000*2=2000
        assert changes[0][3] == 0
        assert changes[0][4] == 2000
        # Entry 1: start=2000*2=4000, end=3000*2=6000
        assert changes[1][3] == 4000
        assert changes[1][4] == 6000
        # Entry 2: start=4000*2=8000, end=5000*2=10000
        assert changes[2][3] == 8000
        assert changes[2][4] == 10000

    def test_identity_stretch(self):
        doc = _make_doc(
            (1000, 2000, "First"),
            (3000, 4000, "Second"),
        )
        # Map to same positions — should be identity
        changes = two_point_stretch(doc, 0, 1000, 1, 3000)

        assert len(changes) == 2
        assert changes[0][3] == 1000
        assert changes[0][4] == 2000
        assert changes[1][3] == 3000
        assert changes[1][4] == 4000

    def test_compress(self):
        doc = _make_doc(
            (0, 2000, "First"),
            (4000, 6000, "Second"),
        )
        # Compress: map entry 0 to 0, entry 1 to 2000
        # Scale = (2000 - 0) / (4000 - 0) = 0.5
        changes = two_point_stretch(doc, 0, 0, 1, 2000)

        assert len(changes) == 2
        assert changes[0][3] == 0
        assert changes[0][4] == 1000  # 2000 * 0.5
        assert changes[1][3] == 2000  # 4000 * 0.5
        assert changes[1][4] == 3000  # 6000 * 0.5

    def test_empty_document(self):
        doc = _make_doc()
        changes = two_point_stretch(doc, 0, 0, 1, 1000)
        assert changes == []

    def test_invalid_indices(self):
        doc = _make_doc((0, 1000, "Test"))
        changes = two_point_stretch(doc, 0, 0, 5, 1000)
        assert changes == []


class TestFpsDriftCorrection:
    """Test fps_drift_correction resync tool."""

    def test_25_to_23976(self):
        doc = _make_doc(
            (0, 1000, "First"),
            (2000, 3000, "Second"),
        )
        changes = fps_drift_correction(doc, 25.0, 23.976)

        assert len(changes) == 2
        # factor = 25.0 / 23.976 ~= 1.04271
        factor = 25.0 / 23.976
        assert changes[0][3] == 0  # 0 * factor = 0
        assert changes[0][4] == round(1000 * factor)
        assert changes[1][3] == round(2000 * factor)
        assert changes[1][4] == round(3000 * factor)

    def test_same_fps_is_identity(self):
        doc = _make_doc((1000, 2000, "Test"))
        changes = fps_drift_correction(doc, 30.0, 30.0)

        assert len(changes) == 1
        assert changes[0][3] == 1000
        assert changes[0][4] == 2000

    def test_invalid_fps_returns_empty(self):
        doc = _make_doc((0, 1000, "Test"))
        assert fps_drift_correction(doc, 0.0, 30.0) == []
        assert fps_drift_correction(doc, 30.0, 0.0) == []
        assert fps_drift_correction(doc, -1.0, 30.0) == []

    def test_30_to_25(self):
        doc = _make_doc((0, 3000, "Test"))
        changes = fps_drift_correction(doc, 30.0, 25.0)

        assert len(changes) == 1
        factor = 30.0 / 25.0  # 1.2
        assert changes[0][3] == 0
        assert changes[0][4] == round(3000 * factor)

    def test_empty_document(self):
        doc = _make_doc()
        changes = fps_drift_correction(doc, 25.0, 30.0)
        assert changes == []
