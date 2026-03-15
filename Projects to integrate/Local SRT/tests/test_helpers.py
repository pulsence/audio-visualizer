#!/usr/bin/env python3
"""Tests for helper utilities."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import compare_srt


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_compare_srt_empty(tmp_path: Path) -> None:
    actual = tmp_path / "actual.srt"
    expected = tmp_path / "expected.srt"
    _write(actual, "\n")
    _write(expected, "")

    compare_srt(actual, expected)


def test_compare_srt_single_cue(tmp_path: Path) -> None:
    actual = tmp_path / "actual.srt"
    expected = tmp_path / "expected.srt"
    srt = (
        "1\n"
        "00:00:00,000 --> 00:00:01,000\n"
        "Hello world.\n\n"
    )
    _write(actual, srt)
    _write(expected, srt)

    compare_srt(actual, expected)


def test_compare_srt_mismatched_cues(tmp_path: Path) -> None:
    actual = tmp_path / "actual.srt"
    expected = tmp_path / "expected.srt"
    _write(
        expected,
        "1\n00:00:00,000 --> 00:00:01,000\nHello.\n\n",
    )
    _write(
        actual,
        "1\n00:00:00,000 --> 00:00:01,000\nHello.\n\n"
        "2\n00:00:02,000 --> 00:00:03,000\nWorld.\n\n",
    )

    with pytest.raises(AssertionError):
        compare_srt(actual, expected)
