#!/usr/bin/env python3
"""Tests for corrected SRT alignment and cue-to-word alignment."""
from __future__ import annotations

from pathlib import Path

from audio_visualizer.srt.core.alignment import (
    AlignedCue,
    align_corrected_srt,
    align_cues_to_whisper_words,
    align_script_to_segments,
    _align_cue_words_to_whisper_span,
)
from audio_visualizer.srt.models import SubtitleBlock, WordItem


def _write_srt(path: Path, text: str) -> None:
    path.write_text(
        "\n".join(
            [
                "1",
                "00:00:00,000 --> 00:00:02,000",
                text,
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_alignment_exact_match(tmp_path):
    words = [
        WordItem(0.0, 0.4, "Hello"),
        WordItem(0.5, 1.0, "world"),
    ]
    srt = tmp_path / "corrected.srt"
    _write_srt(srt, "Hello world")

    aligned = align_corrected_srt(srt, words)

    assert aligned == words


def test_alignment_word_replacement(tmp_path):
    words = [
        WordItem(0.0, 0.4, "Hello"),
        WordItem(0.5, 1.0, "world"),
    ]
    srt = tmp_path / "corrected.srt"
    _write_srt(srt, "Hello earth")

    aligned = align_corrected_srt(srt, words)

    assert aligned[0].text == "Hello"
    assert aligned[1].text == "earth"
    assert aligned[1].start == words[1].start
    assert aligned[1].end == words[1].end


def test_alignment_word_insertion(tmp_path):
    words = [
        WordItem(0.0, 0.4, "Hello"),
        WordItem(0.6, 1.0, "world"),
    ]
    srt = tmp_path / "corrected.srt"
    _write_srt(srt, "Hello brave world")

    aligned = align_corrected_srt(srt, words)

    assert len(aligned) == 3
    assert aligned[1].text == "brave"
    assert aligned[1].start >= words[0].end
    assert aligned[1].end <= words[1].start


def test_alignment_word_deletion(tmp_path):
    words = [
        WordItem(0.0, 0.4, "Hello"),
        WordItem(0.5, 1.0, "world"),
    ]
    srt = tmp_path / "corrected.srt"
    _write_srt(srt, "Hello")

    aligned = align_corrected_srt(srt, words)

    assert len(aligned) == 1
    assert aligned[0].text == "Hello"


def test_align_script_matches_all_segments(mock_segments):
    segments = mock_segments(
        [
            {"start": 0.0, "end": 1.0, "text": "Hello there."},
            {"start": 1.0, "end": 2.0, "text": "General Kenobi."},
            {"start": 2.0, "end": 3.0, "text": "You are a bold one."},
        ]
    )
    script = ["Hello there!", "General Kenobi.", "You are a bold one."]

    updated = align_script_to_segments(script, segments)

    assert updated[0].text == "Hello there!"
    assert updated[1].text == "General Kenobi."
    assert updated[2].text == "You are a bold one."


def test_align_script_extra_sentence_dropped(mock_segments):
    segments = mock_segments(
        [
            {"start": 0.0, "end": 1.0, "text": "Hello there."},
            {"start": 1.0, "end": 2.0, "text": "General Kenobi."},
            {"start": 2.0, "end": 3.0, "text": "You are a bold one."},
        ]
    )
    script = ["Hello there.", "Extra line.", "General Kenobi.", "You are a bold one."]

    updated = align_script_to_segments(script, segments)

    assert updated[0].text == "Hello there."
    assert updated[1].text == "General Kenobi."
    assert updated[2].text == "You are a bold one."


def test_align_script_missing_sentence_keeps_whisper(mock_segments):
    segments = mock_segments(
        [
            {"start": 0.0, "end": 1.0, "text": "Hello there."},
            {"start": 1.0, "end": 2.0, "text": "General Kenobi."},
            {"start": 2.0, "end": 3.0, "text": "You are a bold one."},
        ]
    )
    script = ["Hello there.", "You are a bold one."]

    updated = align_script_to_segments(script, segments)

    assert updated[0].text == "Hello there."
    assert updated[1].text == "General Kenobi."
    assert updated[2].text == "You are a bold one."


# ============================================================
# Cue-to-word alignment tests (bundle-from-SRT)
# ============================================================


class TestAlignedCue:
    def test_default_values(self):
        cue = AlignedCue(cue_text="Hello world", start=0.0, end=1.0)
        assert cue.alignment_status == "estimated"
        assert cue.alignment_confidence == 0.0
        assert cue.words == []

    def test_with_words(self):
        words = [WordItem(0.0, 0.5, "Hello"), WordItem(0.5, 1.0, "world")]
        cue = AlignedCue(
            cue_text="Hello world",
            start=0.0,
            end=1.0,
            words=words,
            alignment_status="matched",
            alignment_confidence=0.95,
        )
        assert len(cue.words) == 2
        assert cue.alignment_status == "matched"


class TestAlignCuesToWhisperWords:
    def test_exact_match_produces_matched_status(self):
        """Identical text in cue and Whisper should produce 'matched' status."""
        cues = [SubtitleBlock(start=0.0, end=2.0, lines=["Hello world"])]
        whisper = [
            WordItem(0.1, 0.5, "Hello"),
            WordItem(0.6, 1.0, "world"),
        ]
        result = align_cues_to_whisper_words(cues, whisper)

        assert len(result) == 1
        assert result[0].cue_text == "Hello world"
        assert result[0].alignment_status == "matched"
        assert result[0].alignment_confidence >= 0.8
        assert len(result[0].words) == 2
        # Preserves cue text
        assert result[0].words[0].text == "Hello"
        assert result[0].words[1].text == "world"

    def test_casing_differences_handled(self):
        """Punctuation and casing differences should not prevent matching."""
        cues = [SubtitleBlock(start=0.0, end=2.0, lines=["Hello, World!"])]
        whisper = [
            WordItem(0.1, 0.5, "hello"),
            WordItem(0.6, 1.0, "world"),
        ]
        result = align_cues_to_whisper_words(cues, whisper)

        assert len(result) == 1
        # Original cue text preserved
        assert result[0].cue_text == "Hello, World!"
        # Words should use cue tokens, not Whisper tokens
        assert result[0].words[0].text == "Hello,"
        assert result[0].words[1].text == "World!"
        # Should still be matched
        assert result[0].alignment_status == "matched"

    def test_empty_whisper_produces_estimated(self):
        """No Whisper words should produce estimated status."""
        cues = [SubtitleBlock(start=0.0, end=2.0, lines=["Hello world"])]
        result = align_cues_to_whisper_words(cues, [])

        assert len(result) == 1
        assert result[0].alignment_status == "estimated"
        assert result[0].alignment_confidence == 0.0
        assert result[0].words == []

    def test_multiple_cues_sequential(self):
        """Multiple cues should be aligned in order."""
        cues = [
            SubtitleBlock(start=0.0, end=1.0, lines=["Hello world"]),
            SubtitleBlock(start=1.5, end=3.0, lines=["How are you"]),
        ]
        whisper = [
            WordItem(0.1, 0.4, "Hello"),
            WordItem(0.5, 0.9, "world"),
            WordItem(1.6, 2.0, "How"),
            WordItem(2.1, 2.4, "are"),
            WordItem(2.5, 2.9, "you"),
        ]
        result = align_cues_to_whisper_words(cues, whisper)

        assert len(result) == 2
        assert result[0].cue_text == "Hello world"
        assert result[1].cue_text == "How are you"
        assert len(result[0].words) == 2
        assert len(result[1].words) == 3

    def test_preserves_original_timing(self):
        """AlignedCue should keep the original cue start/end times."""
        cues = [SubtitleBlock(start=5.0, end=8.0, lines=["Test cue"])]
        whisper = [WordItem(5.1, 5.5, "Test"), WordItem(5.6, 7.0, "cue")]
        result = align_cues_to_whisper_words(cues, whisper)

        assert result[0].start == 5.0
        assert result[0].end == 8.0

    def test_partial_match_status(self):
        """When some words match and some don't, status should be partial or matched."""
        cues = [SubtitleBlock(start=0.0, end=2.0, lines=["Hello beautiful world"])]
        # Whisper only has 2 of 3 words
        whisper = [
            WordItem(0.1, 0.5, "Hello"),
            WordItem(0.6, 1.0, "world"),
        ]
        result = align_cues_to_whisper_words(cues, whisper)

        assert len(result) == 1
        # Should have words for all cue tokens
        assert len(result[0].words) == 3
        # The middle word should have estimated timing
        assert result[0].words[1].text == "beautiful"

    def test_empty_cue_text_produces_estimated(self):
        """Cues with empty text produce estimated status."""
        cues = [SubtitleBlock(start=0.0, end=1.0, lines=[""])]
        whisper = [WordItem(0.1, 0.5, "Hello")]
        result = align_cues_to_whisper_words(cues, whisper)

        assert len(result) == 1
        assert result[0].alignment_status == "estimated"


class TestAlignCueWordsToWhisperSpan:
    def test_exact_tokens(self):
        """When tokens match exactly, timing comes from Whisper."""
        cue_tokens = ["Hello", "world"]
        whisper_span = [
            WordItem(1.0, 1.5, "Hello"),
            WordItem(1.6, 2.0, "world"),
        ]
        words = _align_cue_words_to_whisper_span(
            cue_tokens, whisper_span, 0.0, 3.0
        )
        assert len(words) == 2
        assert words[0].text == "Hello"
        assert words[0].start == 1.0
        assert words[1].text == "world"
        assert words[1].start == 1.6

    def test_no_whisper_words_distributes_evenly(self):
        """With no Whisper words, timing is evenly distributed."""
        cue_tokens = ["Hello", "world"]
        words = _align_cue_words_to_whisper_span(
            cue_tokens, [], 0.0, 2.0
        )
        assert len(words) == 2
        assert words[0].start == 0.0
        assert words[1].start == 1.0

    def test_empty_cue_tokens(self):
        words = _align_cue_words_to_whisper_span(
            [], [WordItem(0.0, 1.0, "test")], 0.0, 1.0
        )
        assert words == []

    def test_preserves_cue_token_text(self):
        """Should use cue token text, not Whisper text."""
        cue_tokens = ["Hello,", "World!"]
        whisper_span = [
            WordItem(0.0, 0.5, "hello"),
            WordItem(0.6, 1.0, "world"),
        ]
        words = _align_cue_words_to_whisper_span(
            cue_tokens, whisper_span, 0.0, 2.0
        )
        assert words[0].text == "Hello,"
        assert words[1].text == "World!"
