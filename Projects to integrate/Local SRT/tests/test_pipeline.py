#!/usr/bin/env python3
"""Deterministic pipeline tests (word-level)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from local_srt.models import FormattingConfig, ResolvedConfig, SubtitleBlock
from local_srt.output_writers import write_srt
from local_srt.subtitle_generation import (
    apply_silence_alignment,
    chunk_segments_to_subtitles,
    chunk_segments_to_transcript_blocks,
    chunk_words_to_subtitles,
    hygiene_and_polish,
    words_to_subtitles,
)


def run_pipeline(
    *,
    words,
    cfg: ResolvedConfig,
    silences: List[Tuple[float, float]],
) -> List[SubtitleBlock]:
    subs = chunk_words_to_subtitles(words, cfg, silences)
    subs = apply_silence_alignment(subs, silences)
    subs = hygiene_and_polish(
        subs,
        min_gap=cfg.formatting.min_gap,
        pad=cfg.formatting.pad,
        silence_intervals=silences,
    )
    return subs


def assert_blocks_close(
    actual: List[SubtitleBlock],
    expected: List[SubtitleBlock],
    tol: float = 0.05,
) -> None:
    assert len(actual) == len(expected)
    for a, e in zip(actual, expected):
        assert abs(a.start - e.start) <= tol
        assert abs(a.end - e.end) <= tol
        assert a.lines == e.lines


def test_pipeline_single_sentence_no_silence(mock_word_items):
    cfg = ResolvedConfig()
    words = mock_word_items(
        [
            ("Hello", 0.0, 0.4),
            ("world", 0.5, 1.0),
        ]
    )
    silences: List[Tuple[float, float]] = []

    subs = run_pipeline(words=words, cfg=cfg, silences=silences)

    expected = [SubtitleBlock(0.0, 1.0, ["Hello world"])]
    assert_blocks_close(subs, expected)


def test_pipeline_silence_split(mock_word_items):
    cfg = ResolvedConfig()
    words = mock_word_items(
        [
            ("Hello", 0.0, 0.4),
            ("there", 0.5, 0.9),
            ("General", 3.0, 3.4),
            ("Kenobi", 3.5, 4.0),
        ]
    )
    silences = [(1.0, 2.5)]

    pre_subs = chunk_words_to_subtitles(words, cfg, silences)
    assert len(pre_subs) == 2
    assert pre_subs[0].end <= silences[0][0]
    assert pre_subs[1].start >= silences[0][1]

    subs = run_pipeline(words=words, cfg=cfg, silences=silences)
    expected = [
        SubtitleBlock(0.0, 0.9, ["Hello there"]),
        SubtitleBlock(3.0, 4.0, ["General Kenobi"]),
    ]
    assert_blocks_close(subs, expected)


def test_pipeline_max_chars_wrap(mock_word_items):
    cfg = ResolvedConfig(formatting=FormattingConfig(max_chars=10, max_lines=3))
    words = mock_word_items(
        [
            ("one", 0.0, 0.4),
            ("two", 0.4, 0.8),
            ("three", 0.8, 1.4),
            ("four", 1.4, 2.0),
            ("five", 2.0, 2.5),
        ]
    )
    silences: List[Tuple[float, float]] = []

    pre_subs = chunk_words_to_subtitles(words, cfg, silences)
    assert len(pre_subs) == 1
    assert pre_subs[0].lines == ["one two", "three four", "five"]

    subs = run_pipeline(words=words, cfg=cfg, silences=silences)
    expected = [SubtitleBlock(0.0, 2.5, ["one two three four five"])]
    assert_blocks_close(subs, expected)


def test_shorts_pipeline_outputs_two_lists(mock_word_items):
    cfg = ResolvedConfig()
    words = mock_word_items(
        [
            ("Hello", 0.0, 0.4),
            ("world", 0.4, 0.9),
        ]
    )
    silences: List[Tuple[float, float]] = []

    sentence_subs = chunk_words_to_subtitles(words, cfg, silences)
    word_subs = words_to_subtitles(words)

    assert sentence_subs == [SubtitleBlock(0.0, 0.9, ["Hello world"])]
    assert word_subs == [
        SubtitleBlock(0.0, 0.4, ["Hello"]),
        SubtitleBlock(0.4, 0.9, ["world"]),
    ]


def test_transcript_blocks_larger_than_general(mock_segments):
    cfg = ResolvedConfig(formatting=FormattingConfig(max_dur=30.0))
    segments = mock_segments(
        [
            {"start": 0.0, "end": 1.0, "text": "First sentence."},
            {"start": 1.1, "end": 2.0, "text": "Second sentence."},
            {"start": 2.1, "end": 3.0, "text": "Third sentence."},
        ]
    )
    silences: List[Tuple[float, float]] = []

    general = chunk_segments_to_subtitles(segments, cfg)
    transcript = chunk_segments_to_transcript_blocks(segments, cfg, silences)

    assert len(transcript) < len(general)


def test_transcript_splits_on_silence(mock_segments):
    cfg = ResolvedConfig(formatting=FormattingConfig(max_dur=30.0))
    segments = mock_segments(
        [
            {"start": 0.0, "end": 1.0, "text": "Hello there."},
            {"start": 3.0, "end": 4.0, "text": "General Kenobi."},
        ]
    )
    silences = [(1.2, 2.5)]

    transcript = chunk_segments_to_transcript_blocks(segments, cfg, silences)

    assert len(transcript) == 2
    assert transcript[0].end <= silences[0][0]
    assert transcript[1].start >= silences[0][1]


def test_speaker_prefix_rendered(tmp_path):
    subs = [SubtitleBlock(0.0, 1.0, ["Hello world"], speaker="Alex")]
    out_path = tmp_path / "speaker.srt"

    write_srt(subs, out_path, max_chars=42, max_lines=2)

    content = out_path.read_text(encoding="utf-8")
    assert "Alex: Hello world" in content


@dataclass
class _Seg:
    start: float
    end: float
    text: str
    words: None = None
    speaker: str | None = None


def test_transcript_speaker_single_label():
    cfg = ResolvedConfig(formatting=FormattingConfig(max_dur=30.0))
    segments = [
        _Seg(0.0, 1.0, "Hello there.", speaker="S1"),
        _Seg(1.0, 2.0, "General Kenobi.", speaker="S1"),
    ]
    silences: List[Tuple[float, float]] = []

    transcript = chunk_segments_to_transcript_blocks(segments, cfg, silences)

    assert transcript
    assert all(block.speaker == "S1" for block in transcript)


def test_transcript_speaker_change_on_silence():
    cfg = ResolvedConfig(formatting=FormattingConfig(max_dur=30.0))
    segments = [
        _Seg(0.0, 1.0, "Hello there.", speaker="S1"),
        _Seg(3.0, 4.0, "General Kenobi.", speaker="S2"),
    ]
    silences = [(1.2, 2.5)]

    transcript = chunk_segments_to_transcript_blocks(segments, cfg, silences)

    assert len(transcript) == 2
    assert transcript[0].speaker == "S1"
    assert transcript[1].speaker == "S2"
