"""Tests for the SRT Edit document model."""
from __future__ import annotations

import json
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

    def test_add_entry_sorted_insert(self):
        """New entries are inserted in sorted order by start_ms."""
        doc = SubtitleDocument()
        doc.add_entry(SubtitleEntry(index=0, start_ms=1000, end_ms=2000, text="First"))
        doc.add_entry(SubtitleEntry(index=0, start_ms=5000, end_ms=6000, text="Third"))
        # This should be inserted between the other two
        pos = doc.add_entry(SubtitleEntry(index=0, start_ms=3000, end_ms=4000, text="Second"))

        assert pos == 1
        assert len(doc.entries) == 3
        assert doc.entries[0].text == "First"
        assert doc.entries[1].text == "Second"
        assert doc.entries[2].text == "Third"

    def test_add_entry_returns_insertion_index(self):
        """add_entry returns the 0-based index of the inserted entry."""
        doc = SubtitleDocument()
        pos0 = doc.add_entry(SubtitleEntry(index=0, start_ms=0, end_ms=1000, text="A"))
        pos1 = doc.add_entry(SubtitleEntry(index=0, start_ms=5000, end_ms=6000, text="C"))
        pos2 = doc.add_entry(SubtitleEntry(index=0, start_ms=2000, end_ms=3000, text="B"))

        assert pos0 == 0
        assert pos1 == 1
        assert pos2 == 1  # inserted between A and C


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


class TestSortedInsertAndAutoOrdering:
    """Test that entries maintain sorted order."""

    def test_entries_inserted_in_sorted_order(self):
        doc = SubtitleDocument()
        doc.add_entry(SubtitleEntry(index=0, start_ms=5000, end_ms=6000, text="C"))
        doc.add_entry(SubtitleEntry(index=0, start_ms=1000, end_ms=2000, text="A"))
        doc.add_entry(SubtitleEntry(index=0, start_ms=3000, end_ms=4000, text="B"))

        assert [e.text for e in doc.entries] == ["A", "B", "C"]
        assert [e.index for e in doc.entries] == [1, 2, 3]

    def test_update_start_time_re_sorts(self):
        """Moving an entry's start_ms past another entry triggers re-sort."""
        doc = SubtitleDocument()
        doc.add_entry(SubtitleEntry(index=0, start_ms=1000, end_ms=2000, text="A"))
        doc.add_entry(SubtitleEntry(index=0, start_ms=3000, end_ms=4000, text="B"))
        doc.add_entry(SubtitleEntry(index=0, start_ms=5000, end_ms=6000, text="C"))

        # Move A after C
        doc.update_entry(0, start_ms=7000, end_ms=8000)

        assert [e.text for e in doc.entries] == ["B", "C", "A"]
        assert [e.index for e in doc.entries] == [1, 2, 3]


class TestSegmentOverlapClamping:
    """Test segment boundary clamping."""

    def test_clamp_segment_bounds_against_neighbors(self):
        doc = SubtitleDocument()
        doc.add_entry(SubtitleEntry(index=0, start_ms=0, end_ms=2000, text="A"))
        doc.add_entry(SubtitleEntry(index=0, start_ms=3000, end_ms=5000, text="B"))
        doc.add_entry(SubtitleEntry(index=0, start_ms=6000, end_ms=8000, text="C"))

        # Try to expand B to overlap A and C
        start, end = doc.clamp_segment_bounds(1, 1000, 7000)
        assert start >= 2000  # must not go before A's end
        assert end <= 6000    # must not go past C's start

    def test_clamp_segment_bounds_first_entry(self):
        doc = SubtitleDocument()
        doc.add_entry(SubtitleEntry(index=0, start_ms=1000, end_ms=3000, text="A"))
        doc.add_entry(SubtitleEntry(index=0, start_ms=4000, end_ms=6000, text="B"))

        # First entry has no predecessor
        start, end = doc.clamp_segment_bounds(0, 500, 5000)
        assert start == 500  # No constraint from previous
        assert end <= 4000   # Must not pass B's start

    def test_clamp_segment_bounds_last_entry(self):
        doc = SubtitleDocument()
        doc.add_entry(SubtitleEntry(index=0, start_ms=1000, end_ms=3000, text="A"))
        doc.add_entry(SubtitleEntry(index=0, start_ms=4000, end_ms=6000, text="B"))

        # Last entry has no successor
        start, end = doc.clamp_segment_bounds(1, 2000, 9000)
        assert start >= 3000  # Must not go before A's end
        assert end == 9000    # No constraint from next


class TestWordLevelHelpers:
    """Test word-level update and clamping."""

    def _make_doc_with_words(self):
        """Create a doc with one entry that has 3 words."""
        from audio_visualizer.srt.models import WordItem
        doc = SubtitleDocument()
        words = [
            WordItem(start=1.0, end=1.5, text="Hello", id="w1", subtitle_id="s1"),
            WordItem(start=1.5, end=2.0, text="beautiful", id="w2", subtitle_id="s1"),
            WordItem(start=2.0, end=2.5, text="world", id="w3", subtitle_id="s1"),
        ]
        entry = SubtitleEntry(
            index=1, start_ms=1000, end_ms=3000, text="Hello beautiful world",
            id="s1", words=words,
        )
        doc._entries = [entry]
        doc._dirty = False
        return doc

    def test_update_word_text(self):
        doc = self._make_doc_with_words()
        doc.update_word(0, 1, text="wonderful")
        assert doc.entries[0].words[1].text == "wonderful"
        assert doc.entries[0].dirty is True

    def test_update_word_timing(self):
        doc = self._make_doc_with_words()
        doc.update_word(0, 0, start=1.1, end=1.4)
        assert doc.entries[0].words[0].start == 1.1
        assert doc.entries[0].words[0].end == 1.4

    def test_update_word_out_of_range(self):
        doc = self._make_doc_with_words()
        with pytest.raises(IndexError):
            doc.update_word(0, 5, text="oops")
        with pytest.raises(IndexError):
            doc.update_word(5, 0, text="oops")

    def test_clamp_word_bounds_within_segment(self):
        doc = self._make_doc_with_words()
        # Try to move word beyond segment boundary
        start, end = doc.clamp_word_bounds(0, 2, 0.5, 4.0)
        assert start >= 2.0   # Must not go before previous word's end
        assert end <= 3.0     # Must not exceed segment end (3000ms = 3.0s)

    def test_clamp_word_bounds_against_neighbors(self):
        doc = self._make_doc_with_words()
        # Middle word: bounded by neighbors
        start, end = doc.clamp_word_bounds(0, 1, 0.5, 2.8)
        assert start >= 1.5  # Must not go before word[0].end
        assert end <= 2.0    # Must not go past word[2].start


class TestBundleLoadSave:
    """Test JSON bundle round-tripping through the document model."""

    def test_load_bundle(self, tmp_path):
        """Load a v2 bundle and verify entries have words and provenance."""
        bundle = {
            "bundle_version": 2,
            "tool_version": "0.7.0",
            "input_file": "test.wav",
            "device_used": "cpu",
            "compute_type_used": "int8",
            "model_name": "tiny",
            "subtitles": [
                {
                    "id": "sub1",
                    "start": 1.0,
                    "end": 3.0,
                    "text": "Hello world",
                    "original_text": "Hello world",
                    "words": [
                        {"id": "w1", "subtitle_id": "sub1", "text": "Hello", "start": 1.0, "end": 2.0},
                        {"id": "w2", "subtitle_id": "sub1", "text": "world", "start": 2.0, "end": 3.0},
                    ],
                    "source_media_path": "test.wav",
                    "model_name": "tiny",
                },
            ],
            "words": [],
        }
        path = tmp_path / "test.bundle.json"
        path.write_text(json.dumps(bundle), encoding="utf-8")

        doc = SubtitleDocument()
        doc.load_bundle(str(path))

        assert len(doc.entries) == 1
        assert doc.entries[0].text == "Hello world"
        assert doc.entries[0].id == "sub1"
        assert len(doc.entries[0].words) == 2
        assert doc.entries[0].words[0].text == "Hello"
        assert doc.entries[0].words[1].text == "world"
        assert doc.entries[0].original_text == "Hello world"
        assert doc.entries[0].source_media_path == "test.wav"
        assert doc.entries[0].model_name == "tiny"
        assert doc.is_dirty is False

    def test_save_bundle(self, tmp_path):
        """Save a document with words as a v2 bundle."""
        from audio_visualizer.srt.models import WordItem

        doc = SubtitleDocument()
        words = [
            WordItem(start=1.0, end=2.0, text="Hello", id="w1", subtitle_id="s1"),
            WordItem(start=2.0, end=3.0, text="world", id="w2", subtitle_id="s1"),
        ]
        doc._entries = [
            SubtitleEntry(
                index=1, start_ms=1000, end_ms=3000, text="Hello world",
                id="s1", words=words, original_text="Hello world",
                source_media_path="test.wav", model_name="tiny",
            ),
        ]
        doc._dirty = True

        path = tmp_path / "output.bundle.json"
        doc.save_bundle(str(path))

        assert doc.is_dirty is False
        data = json.loads(path.read_text())
        assert data["bundle_version"] == 2
        assert len(data["subtitles"]) == 1
        assert data["subtitles"][0]["id"] == "s1"
        assert len(data["subtitles"][0]["words"]) == 2
        assert data["subtitles"][0]["words"][0]["text"] == "Hello"

    def test_bundle_roundtrip(self, tmp_path):
        """Bundle load -> save -> reload preserves data."""
        from audio_visualizer.srt.models import WordItem

        doc = SubtitleDocument()
        words = [
            WordItem(start=1.0, end=2.0, text="Hello", id="w1", subtitle_id="s1"),
        ]
        doc._entries = [
            SubtitleEntry(
                index=1, start_ms=1000, end_ms=3000, text="Hello",
                id="s1", words=words, original_text="Hello",
            ),
        ]

        path = tmp_path / "roundtrip.json"
        doc.save_bundle(str(path))

        doc2 = SubtitleDocument()
        doc2.load_bundle(str(path))

        assert len(doc2.entries) == 1
        assert doc2.entries[0].id == "s1"
        assert len(doc2.entries[0].words) == 1
        assert doc2.entries[0].words[0].text == "Hello"
