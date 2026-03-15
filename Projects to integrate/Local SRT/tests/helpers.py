#!/usr/bin/env python3
"""Test helpers for Local SRT."""
from __future__ import annotations

import difflib
from pathlib import Path
from typing import List, Tuple


def _parse_srt_time(value: str) -> float:
    hhmmss, ms = value.split(",")
    h, m, s = [int(part) for part in hhmmss.split(":")]
    return (h * 3600) + (m * 60) + s + (int(ms) / 1000.0)


def _parse_srt(path: Path) -> List[Tuple[float, float, List[str]]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    blocks = [b for b in text.split("\n\n") if b.strip()]
    parsed: List[Tuple[float, float, List[str]]] = []
    for block in blocks:
        lines = block.splitlines()
        if not lines:
            continue
        if "-->" in lines[0]:
            time_line = lines[0]
            text_lines = lines[1:]
        else:
            if len(lines) < 2:
                continue
            time_line = lines[1]
            text_lines = lines[2:]
        start_s, end_s = [p.strip() for p in time_line.split("-->")]
        start = _parse_srt_time(start_s)
        end = _parse_srt_time(end_s)
        parsed.append((start, end, text_lines))
    return parsed


def compare_srt(actual_path: Path, expected_path: Path, time_tol: float = 0.05) -> None:
    """Compare two SRT files, tolerating small timestamp differences."""
    actual_text = Path(actual_path).read_text(encoding="utf-8")
    expected_text = Path(expected_path).read_text(encoding="utf-8")

    actual = _parse_srt(Path(actual_path))
    expected = _parse_srt(Path(expected_path))

    if len(actual) != len(expected):
        diff = "\n".join(
            difflib.unified_diff(
                expected_text.splitlines(),
                actual_text.splitlines(),
                fromfile="expected",
                tofile="actual",
                lineterm="",
            )
        )
        raise AssertionError(f"Cue count mismatch: {len(actual)} != {len(expected)}\n{diff}")

    for idx, (act, exp) in enumerate(zip(actual, expected), start=1):
        a_start, a_end, a_lines = act
        e_start, e_end, e_lines = exp
        if abs(a_start - e_start) > time_tol or abs(a_end - e_end) > time_tol:
            diff = "\n".join(
                difflib.unified_diff(
                    expected_text.splitlines(),
                    actual_text.splitlines(),
                    fromfile="expected",
                    tofile="actual",
                    lineterm="",
                )
            )
            raise AssertionError(
                "Timestamp mismatch in cue "
                f"{idx}: expected ({e_start:.3f}, {e_end:.3f}) "
                f"got ({a_start:.3f}, {a_end:.3f})\n{diff}"
            )
        if a_lines != e_lines:
            diff = "\n".join(
                difflib.unified_diff(
                    expected_text.splitlines(),
                    actual_text.splitlines(),
                    fromfile="expected",
                    tofile="actual",
                    lineterm="",
                )
            )
            raise AssertionError(f"Text mismatch in cue {idx}\n{diff}")


def compare_srt_timing(actual_path: Path, expected_path: Path, time_tol: float = 0.05) -> None:
    """Compare SRT timing only, tolerating small timestamp differences."""
    actual_text = Path(actual_path).read_text(encoding="utf-8")
    expected_text = Path(expected_path).read_text(encoding="utf-8")

    actual = _parse_srt(Path(actual_path))
    expected = _parse_srt(Path(expected_path))

    if len(actual) != len(expected):
        diff = "\n".join(
            difflib.unified_diff(
                expected_text.splitlines(),
                actual_text.splitlines(),
                fromfile="expected",
                tofile="actual",
                lineterm="",
            )
        )
        raise AssertionError(f"Cue count mismatch: {len(actual)} != {len(expected)}\n{diff}")

    for idx, (act, exp) in enumerate(zip(actual, expected), start=1):
        a_start, a_end, _ = act
        e_start, e_end, _ = exp
        if abs(a_start - e_start) > time_tol or abs(a_end - e_end) > time_tol:
            diff = "\n".join(
                difflib.unified_diff(
                    expected_text.splitlines(),
                    actual_text.splitlines(),
                    fromfile="expected",
                    tofile="actual",
                    lineterm="",
                )
            )
            raise AssertionError(
                "Timestamp mismatch in cue "
                f"{idx}: expected ({e_start:.3f}, {e_end:.3f}) "
                f"got ({a_start:.3f}, {a_end:.3f})\n{diff}"
            )
