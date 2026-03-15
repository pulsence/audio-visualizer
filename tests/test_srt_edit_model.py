"""Tests for the SRT Edit document model."""
from __future__ import annotations

import os
import tempfile

import pytest

from audio_visualizer.ui.tabs.srtEdit.document import SubtitleDocument, SubtitleEntry


class TestLoadSaveRoundtrip:
    """Test loading and saving .srt files round-trips correctly."""

    def test_load_save_roundtrip(self, tmp_path):
        """Create a temp .srt, load, save, and compare."""
        srt_content = (
            "1\n"
            "00:00:01,000 --> 00:00:03,000\n"
            "Hello world\n"
            "\n"
            "2\n"
            "00:00:04,000 --> 00:00:06,500\n"
            "Second subtitle\n"
            "\n"
            "3\n"
            "00:00:07,000 --> 00:00:10,000\n"
            "Third subtitle here\n"
            "\n"
        )
        src = tmp_path / "input.srt"
        src.write_text(srt_content, encoding="utf-8")

        doc = SubtitleDocument()
        doc.load_srt(str(src))

        assert len(doc.entries) == 3
        assert doc.entries[0].text == "Hello world"
        assert doc.entries[0].start_ms == 1000
        assert doc.entries[0].end_ms == 3000
        assert doc.entries[1].text == "Second subtitle"
        assert doc.entries[2].text == "Third subtitle here"

        # Save and reload
        dst = tmp_path / "output.srt"
        doc.save_srt(str(dst))

        doc2 = SubtitleDocument()
        doc2.load_srt(str(dst))

        assert len(doc2.entries) == 3
        for orig, reloaded in zip(doc.entries, doc2.entries):
            assert orig.start_ms == reloaded.start_ms
            assert orig.end_ms == reloaded.end_ms
            assert orig.text == reloaded.text


class TestAddEntry:
    """Test adding entries to a document."""

    def test_add_entry(self):
        doc = SubtitleDocument()
        entry = SubtitleEntry(index=0, start_ms=0, end_ms=2000, text="Test")
        doc.add_entry(entry)

        assert len(doc.entries) == 1
        assert doc.entries[0].index == 1
        assert doc.entries[0].text == "Test"
        assert doc.entries[0].dirty is True

    def test_add_multiple_entries(self):
        doc = SubtitleDocument()
        for i in range(5):
            doc.add_entry(
                SubtitleEntry(
                    index=0,
                    start_ms=i * 2000,
                    end_ms=(i + 1) * 2000,
                    text=f"Entry {i + 1}",
                )
            )

        assert len(doc.entries) == 5
        for i, entry in enumerate(doc.entries):
            assert entry.index == i + 1


class TestRemoveEntry:
    """Test removing entries from a document."""

    def test_remove_entry(self):
        doc = SubtitleDocument()
        for i in range(3):
            doc.add_entry(
                SubtitleEntry(index=0, start_ms=i * 1000, end_ms=(i + 1) * 1000, text=f"E{i}")
            )

        removed = doc.remove_entry(1)
        assert removed.text == "E1"
        assert len(doc.entries) == 2
        assert doc.entries[0].index == 1
        assert doc.entries[1].index == 2

    def test_remove_entry_out_of_range(self):
        doc = SubtitleDocument()
        with pytest.raises(IndexError):
            doc.remove_entry(0)

    def test_remove_entry_negative_index(self):
        doc = SubtitleDocument()
        doc.add_entry(SubtitleEntry(index=0, start_ms=0, end_ms=1000, text="X"))
        with pytest.raises(IndexError):
            doc.remove_entry(-1)


class TestSplitEntry:
    """Test splitting entries."""

    def test_split_entry(self):
        doc = SubtitleDocument()
        doc.add_entry(
            SubtitleEntry(index=0, start_ms=0, end_ms=4000, text="Hello beautiful world")
        )

        doc.split_entry(0, 2000)

        assert len(doc.entries) == 2
        assert doc.entries[0].start_ms == 0
        assert doc.entries[0].end_ms == 2000
        assert doc.entries[1].start_ms == 2000
        assert doc.entries[1].end_ms == 4000
        # Text should be split
        assert doc.entries[0].text == "Hello"
        assert doc.entries[1].text == "beautiful world"

    def test_split_entry_invalid_time(self):
        doc = SubtitleDocument()
        doc.add_entry(SubtitleEntry(index=0, start_ms=1000, end_ms=3000, text="Test"))

        with pytest.raises(ValueError):
            doc.split_entry(0, 500)  # before start

        with pytest.raises(ValueError):
            doc.split_entry(0, 3500)  # after end

    def test_split_single_word_entry(self):
        doc = SubtitleDocument()
        doc.add_entry(SubtitleEntry(index=0, start_ms=0, end_ms=2000, text="Hello"))

        doc.split_entry(0, 1000)

        assert len(doc.entries) == 2
        # Single word gets duplicated
        assert doc.entries[0].text == "Hello"
        assert doc.entries[1].text == "Hello"


class TestMergeEntries:
    """Test merging entries."""

    def test_merge_entries(self):
        doc = SubtitleDocument()
        doc.add_entry(SubtitleEntry(index=0, start_ms=0, end_ms=2000, text="Hello"))
        doc.add_entry(SubtitleEntry(index=0, start_ms=2000, end_ms=4000, text="world"))

        doc.merge_entries(0, 1)

        assert len(doc.entries) == 1
        assert doc.entries[0].start_ms == 0
        assert doc.entries[0].end_ms == 4000
        assert doc.entries[0].text == "Hello world"

    def test_merge_non_adjacent_raises(self):
        doc = SubtitleDocument()
        for i in range(3):
            doc.add_entry(
                SubtitleEntry(index=0, start_ms=i * 1000, end_ms=(i + 1) * 1000, text=f"E{i}")
            )

        with pytest.raises(ValueError):
            doc.merge_entries(0, 2)

    def test_merge_out_of_range_raises(self):
        doc = SubtitleDocument()
        doc.add_entry(SubtitleEntry(index=0, start_ms=0, end_ms=1000, text="X"))

        with pytest.raises(IndexError):
            doc.merge_entries(0, 5)


class TestNormalizeTimestamps:
    """Test timestamp normalization."""

    def test_normalize_timestamps_sorts(self):
        doc = SubtitleDocument()
        doc.add_entry(SubtitleEntry(index=0, start_ms=5000, end_ms=7000, text="Second"))
        doc.add_entry(SubtitleEntry(index=0, start_ms=1000, end_ms=3000, text="First"))

        doc.normalize_timestamps()

        assert doc.entries[0].text == "First"
        assert doc.entries[1].text == "Second"

    def test_normalize_timestamps_fixes_overlaps(self):
        doc = SubtitleDocument()
        doc.add_entry(SubtitleEntry(index=0, start_ms=0, end_ms=3000, text="One"))
        doc.add_entry(SubtitleEntry(index=0, start_ms=2000, end_ms=5000, text="Two"))

        doc.normalize_timestamps()

        # First entry's end should be clamped before second entry's start
        assert doc.entries[0].end_ms < doc.entries[1].start_ms


class TestDirtyTracking:
    """Test dirty flag behavior."""

    def test_new_document_is_clean(self):
        doc = SubtitleDocument()
        assert doc.is_dirty is False

    def test_add_entry_makes_dirty(self):
        doc = SubtitleDocument()
        doc.add_entry(SubtitleEntry(index=0, start_ms=0, end_ms=1000, text="X"))
        assert doc.is_dirty is True

    def test_mark_clean_resets_dirty(self):
        doc = SubtitleDocument()
        doc.add_entry(SubtitleEntry(index=0, start_ms=0, end_ms=1000, text="X"))
        assert doc.is_dirty is True

        doc.mark_clean()
        assert doc.is_dirty is False

    def test_update_entry_marks_dirty(self):
        doc = SubtitleDocument()
        doc.add_entry(SubtitleEntry(index=0, start_ms=0, end_ms=1000, text="X"))
        doc.mark_clean()

        doc.update_entry(0, text="Y")
        assert doc.is_dirty is True
        assert doc.entries[0].dirty is True

    def test_load_is_clean(self, tmp_path):
        srt_content = (
            "1\n"
            "00:00:01,000 --> 00:00:03,000\n"
            "Hello\n"
            "\n"
        )
        src = tmp_path / "test.srt"
        src.write_text(srt_content, encoding="utf-8")

        doc = SubtitleDocument()
        doc.load_srt(str(src))

        assert doc.is_dirty is False
        assert all(not e.dirty for e in doc.entries)

    def test_save_marks_clean(self, tmp_path):
        doc = SubtitleDocument()
        doc.add_entry(SubtitleEntry(index=0, start_ms=0, end_ms=1000, text="Test"))
        assert doc.is_dirty is True

        path = tmp_path / "out.srt"
        doc.save_srt(str(path))

        assert doc.is_dirty is False
