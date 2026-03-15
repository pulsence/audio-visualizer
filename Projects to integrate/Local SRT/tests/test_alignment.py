#!/usr/bin/env python3
"""Tests for corrected SRT alignment."""
from __future__ import annotations

from pathlib import Path

from local_srt.alignment import align_corrected_srt, align_script_to_segments
from local_srt.models import WordItem


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
