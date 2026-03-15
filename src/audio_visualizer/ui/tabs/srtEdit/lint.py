"""QA lint system for subtitle validation.

Provides lint rules, profiles, and a runner that checks a
SubtitleDocument for common issues like excessive character count,
high reading speed, overlapping timestamps, and more.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from audio_visualizer.ui.tabs.srtEdit.document import SubtitleDocument

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Data classes
# ------------------------------------------------------------------

@dataclass
class LintIssue:
    """A single lint finding.

    Attributes:
        entry_index: 0-based index of the entry with the issue.
        severity: One of 'error', 'warning', 'info'.
        rule_id: Machine-readable rule identifier.
        message: Human-readable description of the issue.
        auto_fixable: Whether this issue can be fixed automatically.
    """

    entry_index: int
    severity: str
    rule_id: str
    message: str
    auto_fixable: bool = False


@dataclass
class LintProfile:
    """A named collection of lint thresholds.

    Attributes:
        name: Profile display name.
        rules: Dict of rule-specific thresholds.
    """

    name: str
    rules: dict[str, object] = field(default_factory=dict)


# ------------------------------------------------------------------
# Built-in profiles
# ------------------------------------------------------------------

def pipeline_default() -> LintProfile:
    """Pipeline default profile using FormattingConfig defaults."""
    return LintProfile(
        name="Pipeline Default",
        rules={
            "max_chars": 42,
            "max_lines": 2,
            "target_cps": 20,
            "min_dur_ms": 800,
            "max_dur_ms": 7000,
            "min_gap_ms": 80,
        },
    )


def accessible_general() -> LintProfile:
    """Accessible / general audience — relaxed thresholds."""
    return LintProfile(
        name="Accessible General",
        rules={
            "max_chars": 37,
            "max_lines": 2,
            "target_cps": 15,
            "min_dur_ms": 1000,
            "max_dur_ms": 7000,
            "min_gap_ms": 80,
        },
    )


def short_form_social() -> LintProfile:
    """Short-form / social media — tight constraints."""
    return LintProfile(
        name="Short-form Social",
        rules={
            "max_chars": 30,
            "max_lines": 1,
            "target_cps": 25,
            "min_dur_ms": 800,
            "max_dur_ms": 3000,
            "min_gap_ms": 80,
        },
    )


BUILTIN_PROFILES: dict[str, LintProfile] = {
    "pipeline_default": pipeline_default(),
    "accessible_general": accessible_general(),
    "short_form_social": short_form_social(),
}


# ------------------------------------------------------------------
# Individual lint rules
# ------------------------------------------------------------------

def check_max_chars(document: SubtitleDocument, max_chars: int) -> list[LintIssue]:
    """Check that no single line exceeds *max_chars*."""
    issues: list[LintIssue] = []
    for i, entry in enumerate(document.entries):
        for line in entry.text.split("\n"):
            if len(line) > max_chars:
                issues.append(LintIssue(
                    entry_index=i,
                    severity="warning",
                    rule_id="max_chars",
                    message=f"Line has {len(line)} chars (max {max_chars}): \"{line[:50]}...\"",
                    auto_fixable=False,
                ))
                break  # one issue per entry
    return issues


def check_max_lines(document: SubtitleDocument, max_lines: int) -> list[LintIssue]:
    """Check that no entry exceeds *max_lines* lines."""
    issues: list[LintIssue] = []
    for i, entry in enumerate(document.entries):
        line_count = len(entry.text.split("\n"))
        if line_count > max_lines:
            issues.append(LintIssue(
                entry_index=i,
                severity="warning",
                rule_id="max_lines",
                message=f"Entry has {line_count} lines (max {max_lines}).",
                auto_fixable=False,
            ))
    return issues


def check_cps(document: SubtitleDocument, target_cps: float) -> list[LintIssue]:
    """Check that characters-per-second does not exceed *target_cps*."""
    issues: list[LintIssue] = []
    for i, entry in enumerate(document.entries):
        dur_s = (entry.end_ms - entry.start_ms) / 1000.0
        if dur_s <= 0:
            continue
        char_count = len(entry.text.replace("\n", ""))
        cps = char_count / dur_s
        if cps > target_cps:
            issues.append(LintIssue(
                entry_index=i,
                severity="warning",
                rule_id="cps",
                message=f"CPS is {cps:.1f} (target max {target_cps:.0f}).",
                auto_fixable=False,
            ))
    return issues


def check_min_duration(document: SubtitleDocument, min_dur_ms: int) -> list[LintIssue]:
    """Check that no entry is shorter than *min_dur_ms*."""
    issues: list[LintIssue] = []
    for i, entry in enumerate(document.entries):
        dur = entry.end_ms - entry.start_ms
        if dur < min_dur_ms:
            issues.append(LintIssue(
                entry_index=i,
                severity="warning",
                rule_id="min_duration",
                message=f"Duration is {dur} ms (min {min_dur_ms} ms).",
                auto_fixable=False,
            ))
    return issues


def check_max_duration(document: SubtitleDocument, max_dur_ms: int) -> list[LintIssue]:
    """Check that no entry is longer than *max_dur_ms*."""
    issues: list[LintIssue] = []
    for i, entry in enumerate(document.entries):
        dur = entry.end_ms - entry.start_ms
        if dur > max_dur_ms:
            issues.append(LintIssue(
                entry_index=i,
                severity="warning",
                rule_id="max_duration",
                message=f"Duration is {dur} ms (max {max_dur_ms} ms).",
                auto_fixable=False,
            ))
    return issues


def check_min_gap(document: SubtitleDocument, min_gap_ms: int) -> list[LintIssue]:
    """Check that the gap between consecutive entries is at least *min_gap_ms*."""
    issues: list[LintIssue] = []
    entries = document.entries
    for i in range(len(entries) - 1):
        gap = entries[i + 1].start_ms - entries[i].end_ms
        if gap < min_gap_ms:
            issues.append(LintIssue(
                entry_index=i,
                severity="warning",
                rule_id="min_gap",
                message=f"Gap to next entry is {gap} ms (min {min_gap_ms} ms).",
                auto_fixable=True,
            ))
    return issues


def check_overlap(document: SubtitleDocument) -> list[LintIssue]:
    """Check for overlapping entries."""
    issues: list[LintIssue] = []
    entries = document.entries
    for i in range(len(entries) - 1):
        if entries[i].end_ms > entries[i + 1].start_ms:
            overlap = entries[i].end_ms - entries[i + 1].start_ms
            issues.append(LintIssue(
                entry_index=i,
                severity="error",
                rule_id="overlap",
                message=f"Overlaps next entry by {overlap} ms.",
                auto_fixable=True,
            ))
    return issues


def check_empty_text(document: SubtitleDocument) -> list[LintIssue]:
    """Check for entries with empty or whitespace-only text."""
    issues: list[LintIssue] = []
    for i, entry in enumerate(document.entries):
        if not entry.text.strip():
            issues.append(LintIssue(
                entry_index=i,
                severity="error",
                rule_id="empty_text",
                message="Entry has empty text.",
                auto_fixable=False,
            ))
    return issues


# ------------------------------------------------------------------
# Runner
# ------------------------------------------------------------------

def run_lint(document: SubtitleDocument, profile: LintProfile) -> list[LintIssue]:
    """Run all lint rules against a document using the given profile.

    Args:
        document: The SubtitleDocument to validate.
        profile: A LintProfile containing rule thresholds.

    Returns:
        List of LintIssue objects, sorted by entry index.
    """
    issues: list[LintIssue] = []
    rules = profile.rules

    max_chars = int(rules.get("max_chars", 42))
    max_lines = int(rules.get("max_lines", 2))
    target_cps = float(rules.get("target_cps", 20))
    min_dur_ms = int(rules.get("min_dur_ms", 800))
    max_dur_ms = int(rules.get("max_dur_ms", 7000))
    min_gap_ms = int(rules.get("min_gap_ms", 80))

    issues.extend(check_max_chars(document, max_chars))
    issues.extend(check_max_lines(document, max_lines))
    issues.extend(check_cps(document, target_cps))
    issues.extend(check_min_duration(document, min_dur_ms))
    issues.extend(check_max_duration(document, max_dur_ms))
    issues.extend(check_min_gap(document, min_gap_ms))
    issues.extend(check_overlap(document))
    issues.extend(check_empty_text(document))

    issues.sort(key=lambda issue: issue.entry_index)
    return issues
