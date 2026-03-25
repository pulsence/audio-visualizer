"""Tests for the srt.io.bundleReader module — unversioned bundle contract."""
import json
import pytest
from pathlib import Path

from audio_visualizer.srt.io.bundleReader import (
    read_json_bundle,
    normalize_bundle,
)
from audio_visualizer.srt.models import WordItem


# ------------------------------------------------------------------
# Fixtures: sample bundle payloads
# ------------------------------------------------------------------

def _bundle() -> dict:
    """Return a sample bundle."""
    return {
        "tool_version": "0.7.0",
        "input_file": "speech.mp3",
        "device_used": "cuda",
        "compute_type_used": "float16",
        "model_name": "large-v3",
        "config": None,
        "subtitles": [
            {
                "id": "sub-001",
                "start": 0.0,
                "end": 2.5,
                "text": "Hello world",
                "original_text": "Hello world",
                "words": [
                    {
                        "id": "w-001",
                        "subtitle_id": "sub-001",
                        "text": "Hello",
                        "start": 0.0,
                        "end": 1.0,
                        "confidence": 0.95,
                    },
                    {
                        "id": "w-002",
                        "subtitle_id": "sub-001",
                        "text": "world",
                        "start": 1.1,
                        "end": 2.5,
                        "confidence": 0.88,
                    },
                ],
                "speaker_label": "Speaker 1",
                "source_media_path": "speech.mp3",
                "model_name": "large-v3",
                "device": "cuda",
                "compute_type": "float16",
            },
        ],
        "words": [
            {
                "id": "w-001",
                "subtitle_id": "sub-001",
                "text": "Hello",
                "start": 0.0,
                "end": 1.0,
                "confidence": 0.95,
            },
            {
                "id": "w-002",
                "subtitle_id": "sub-001",
                "text": "world",
                "start": 1.1,
                "end": 2.5,
                "confidence": 0.88,
            },
        ],
    }


def _minimal_bundle() -> dict:
    """Return a minimal bundle with just subtitles."""
    return {
        "subtitles": [
            {"start": 0.0, "end": 2.5, "text": "Hello world"},
            {"start": 3.0, "end": 5.0, "text": "Testing now"},
        ],
    }


# ------------------------------------------------------------------
# Tests: normalize_bundle
# ------------------------------------------------------------------


class TestNormalizeBundle:
    def test_preserves_metadata(self):
        result = normalize_bundle(_bundle())
        assert result["tool_version"] == "0.7.0"
        assert result["input_file"] == "speech.mp3"
        assert result["device_used"] == "cuda"

    def test_preserves_ids(self):
        result = normalize_bundle(_bundle())
        assert result["subtitles"][0]["id"] == "sub-001"

    def test_words_are_word_items(self):
        result = normalize_bundle(_bundle())
        for w in result["words"]:
            assert isinstance(w, WordItem)

    def test_word_confidence_preserved(self):
        result = normalize_bundle(_bundle())
        w = result["words"][0]
        assert w.confidence == 0.95

    def test_speaker_label_preserved(self):
        result = normalize_bundle(_bundle())
        assert result["subtitles"][0]["speaker_label"] == "Speaker 1"

    def test_model_name_preserved(self):
        result = normalize_bundle(_bundle())
        assert result["model_name"] == "large-v3"

    def test_no_bundle_version_in_output(self):
        result = normalize_bundle(_bundle())
        assert "bundle_version" not in result

    def test_words_linked_to_subtitles(self):
        result = normalize_bundle(_bundle())
        for sub in result["subtitles"]:
            for w in sub["words"]:
                assert w.subtitle_id == sub["id"]

    def test_flat_words_list(self):
        result = normalize_bundle(_bundle())
        assert len(result["words"]) == 2

    def test_subtitle_count(self):
        result = normalize_bundle(_bundle())
        assert len(result["subtitles"]) == 1


class TestNormalizeMinimalBundle:
    def test_subtitles_have_ids(self):
        result = normalize_bundle(_minimal_bundle())
        for sub in result["subtitles"]:
            assert "id" in sub
            assert isinstance(sub["id"], str)
            assert len(sub["id"]) > 0

    def test_words_are_word_items(self):
        result = normalize_bundle(_minimal_bundle())
        # Minimal bundle has no words
        assert result["words"] == []

    def test_original_text_set(self):
        result = normalize_bundle(_minimal_bundle())
        for sub in result["subtitles"]:
            assert sub["original_text"] == sub["text"]

    def test_subtitle_count(self):
        result = normalize_bundle(_minimal_bundle())
        assert len(result["subtitles"]) == 2

    def test_defaults_for_missing_metadata(self):
        result = normalize_bundle(_minimal_bundle())
        assert result["tool_version"] == ""
        assert result["input_file"] == ""
        assert result["device_used"] == ""

    def test_ignores_legacy_bundle_version_key(self):
        """Bundles with a legacy bundle_version key should still load fine."""
        data = _bundle()
        data["bundle_version"] = 2
        result = normalize_bundle(data)
        assert "bundle_version" not in result


# ------------------------------------------------------------------
# Tests: read_json_bundle (file I/O)
# ------------------------------------------------------------------


class TestReadJsonBundle:
    def test_read_bundle_file(self, tmp_path):
        path = tmp_path / "test.bundle.json"
        path.write_text(json.dumps(_bundle()), encoding="utf-8")
        result = read_json_bundle(path)
        assert len(result["subtitles"]) == 1
        assert result["subtitles"][0]["id"] == "sub-001"

    def test_read_minimal_bundle_file(self, tmp_path):
        path = tmp_path / "minimal.json"
        path.write_text(json.dumps(_minimal_bundle()), encoding="utf-8")
        result = read_json_bundle(path)
        assert len(result["subtitles"]) == 2

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            read_json_bundle("/nonexistent/path.json")

    def test_invalid_json_raises(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not json", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid JSON"):
            read_json_bundle(path)

    def test_non_object_raises(self, tmp_path):
        path = tmp_path / "array.json"
        path.write_text("[1,2,3]", encoding="utf-8")
        with pytest.raises(ValueError, match="does not contain a JSON object"):
            read_json_bundle(path)


class TestBundleRoundTrip:
    """Verify write_json_bundle -> read_json_bundle round-trips correctly."""

    def test_round_trip(self, tmp_path):
        from unittest.mock import MagicMock
        from audio_visualizer.srt.io.outputWriters import write_json_bundle
        from audio_visualizer.srt.models import SubtitleBlock, ResolvedConfig

        cfg = ResolvedConfig()
        seg = MagicMock()
        seg.start = 0.0
        seg.end = 2.0
        seg.text = "Hello world"
        word1 = MagicMock()
        word1.start = 0.0
        word1.end = 1.0
        word1.word = "Hello"
        word1.probability = 0.9
        word2 = MagicMock()
        word2.start = 1.1
        word2.end = 2.0
        word2.word = "world"
        word2.probability = 0.85
        seg.words = [word1, word2]

        subs = [SubtitleBlock(0.0, 2.0, ["Hello world"])]

        path = tmp_path / "round_trip.json"
        write_json_bundle(
            path,
            input_file="test.mp3",
            device_used="cpu",
            compute_type_used="int8",
            cfg=cfg,
            segments=[seg],
            subs=subs,
            tool_version="0.7.0",
            model_name="base",
        )

        result = read_json_bundle(path)
        assert "bundle_version" not in result
        assert len(result["subtitles"]) == 1
        assert result["subtitles"][0]["text"] == "Hello world"
        assert len(result["words"]) >= 2
        assert result["words"][0].text == "Hello"
        assert result["words"][1].text == "world"
