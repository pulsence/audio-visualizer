"""Tests for bundle loading in SubtitleFile (Phase 10.1)."""

import json
import pytest
from pathlib import Path

from audio_visualizer.caption.core.subtitle import SubtitleFile


class TestSubtitleBundleLoading:
    """Tests for SubtitleFile.load_bundle() and bundle support in load()."""

    def test_load_v2_bundle(self, tmp_path):
        bundle = {
            "bundle_version": 2,
            "tool_version": "0.7.0",
            "input_file": "test.mp3",
            "device_used": "cpu",
            "compute_type_used": "int8",
            "model_name": "base",
            "subtitles": [
                {
                    "id": "sub1",
                    "start": 1.0,
                    "end": 3.5,
                    "text": "Hello world",
                    "words": [
                        {"start": 1.0, "end": 1.5, "text": "Hello"},
                        {"start": 1.5, "end": 3.5, "text": "world"},
                    ],
                },
                {
                    "id": "sub2",
                    "start": 4.0,
                    "end": 6.0,
                    "text": "Second line",
                    "words": [
                        {"start": 4.0, "end": 4.5, "text": "Second"},
                        {"start": 4.5, "end": 6.0, "text": "line"},
                    ],
                },
            ],
        }
        bundle_path = tmp_path / "test.json"
        bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

        sub = SubtitleFile.load_bundle(bundle_path)

        assert sub.source_format == "bundle"
        assert len(sub.subs.events) == 2
        assert sub.subs.events[0].text == "Hello world"
        assert int(sub.subs.events[0].start) == 1000
        assert int(sub.subs.events[0].end) == 3500

    def test_bundle_has_word_timing(self, tmp_path):
        bundle = {
            "bundle_version": 2,
            "subtitles": [
                {
                    "start": 0.0,
                    "end": 2.0,
                    "text": "Hello world",
                    "words": [
                        {"start": 0.0, "end": 0.5, "text": "Hello"},
                        {"start": 0.5, "end": 2.0, "text": "world"},
                    ],
                },
            ],
        }
        bundle_path = tmp_path / "test.json"
        bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

        sub = SubtitleFile.load_bundle(bundle_path)

        assert sub.has_word_timing is True
        wt = sub.get_word_timing(0)
        assert wt is not None
        assert len(wt) == 2
        assert wt[0]["text"] == "Hello"
        assert wt[0]["start"] == 0.0
        assert wt[0]["end"] == 0.5

    def test_bundle_without_words_no_word_timing(self, tmp_path):
        bundle = {
            "bundle_version": 2,
            "subtitles": [
                {
                    "start": 0.0,
                    "end": 2.0,
                    "text": "Hello world",
                    "words": [],
                },
            ],
        }
        bundle_path = tmp_path / "test.json"
        bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

        sub = SubtitleFile.load_bundle(bundle_path)

        assert sub.has_word_timing is False
        assert sub.get_word_timing(0) is None

    def test_load_json_via_generic_load(self, tmp_path):
        """SubtitleFile.load() should handle .json files by delegating to load_bundle()."""
        bundle = {
            "bundle_version": 2,
            "subtitles": [
                {
                    "start": 0.0,
                    "end": 1.0,
                    "text": "Test",
                },
            ],
        }
        bundle_path = tmp_path / "test.json"
        bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

        sub = SubtitleFile.load(bundle_path)

        assert sub.source_format == "bundle"
        assert len(sub.subs.events) == 1

    def test_load_bundle_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            SubtitleFile.load_bundle(tmp_path / "nonexistent.json")

    def test_load_bundle_invalid_json(self, tmp_path):
        bad_path = tmp_path / "bad.json"
        bad_path.write_text("not json", encoding="utf-8")
        with pytest.raises(ValueError):
            SubtitleFile.load_bundle(bad_path)

    def test_plain_srt_no_word_timing(self, tmp_path):
        srt_content = (
            "1\n"
            "00:00:01,000 --> 00:00:03,000\n"
            "Hello world\n\n"
        )
        srt_path = tmp_path / "test.srt"
        srt_path.write_text(srt_content, encoding="utf-8")

        sub = SubtitleFile.load(srt_path)

        assert sub.source_format == "srt"
        assert sub.has_word_timing is False

    def test_unsupported_format_raises(self, tmp_path):
        txt_path = tmp_path / "test.txt"
        txt_path.write_text("plain text", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported"):
            SubtitleFile.load(txt_path)

    def test_v1_bundle_loading(self, tmp_path):
        """V1 bundles should also load correctly."""
        bundle = {
            "input_file": "test.mp3",
            "device_used": "cpu",
            "compute_type_used": "int8",
            "segments": [
                {
                    "words": [
                        {"word": "Hello", "start": 0.0, "end": 0.5},
                        {"word": "world", "start": 0.5, "end": 1.0},
                    ]
                }
            ],
            "subtitles": [
                {"start": 0.0, "end": 1.0, "text": "Hello world"},
            ],
        }
        bundle_path = tmp_path / "v1.json"
        bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

        sub = SubtitleFile.load_bundle(bundle_path)

        assert sub.source_format == "bundle"
        assert len(sub.subs.events) == 1
        assert sub.subs.events[0].text == "Hello world"
        # V1 bundles should also have word timing
        assert sub.has_word_timing is True
