#!/usr/bin/env python3
"""Tests for diarization utilities."""
from __future__ import annotations

from dataclasses import dataclass

from local_srt.diarization import assign_speakers, is_diarization_available


def test_is_diarization_available_returns_bool():
    assert isinstance(is_diarization_available(), bool)


@dataclass
class _Seg:
    start: float
    end: float
    text: str
    words: None = None
    speaker: str | None = None


def test_assign_speakers_overlaps():
    segments = [
        _Seg(0.0, 1.0, "Hello"),
        _Seg(1.0, 2.0, "World"),
    ]
    diarization = [
        (0.0, 1.2, "SPEAKER_00"),
        (1.2, 2.0, "SPEAKER_01"),
    ]

    updated = assign_speakers(segments, diarization)

    assert updated[0].speaker == "SPEAKER_00"
    assert updated[1].speaker == "SPEAKER_01"
