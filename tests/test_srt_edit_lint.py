"""Tests for the SRT Edit lint system."""
from __future__ import annotations

import pytest

from audio_visualizer.ui.tabs.srtEdit.document import SubtitleDocument, SubtitleEntry
from audio_visualizer.ui.tabs.srtEdit.lint import (
    BUILTIN_PROFILES,
    LintIssue,
    LintProfile,
    check_cps,
    check_empty_text,
    check_max_chars,
    check_max_lines,
    check_min_duration,
    check_min_gap,
    check_overlap,
    pipeline_default,
    run_lint,
)


def _make_doc(*entries_data) -> SubtitleDocument:
    """Helper to create a SubtitleDocument from (start_ms, end_ms, text) tuples."""
    doc = SubtitleDocument()
    for i, (start, end, text) in enumerate(entries_data):
        entry = SubtitleEntry(index=i + 1, start_ms=start, end_ms=end, text=text)
        doc._entries.append(entry)
    return doc


class TestPipelineDefaultProfile:
    """Test the pipeline_default lint profile."""

    def test_profile_exists(self):
        profile = pipeline_default()
        assert profile.name == "Pipeline Default"
        assert "max_chars" in profile.rules
        assert "target_cps" in profile.rules
        assert "min_dur_ms" in profile.rules
        assert "max_dur_ms" in profile.rules
        assert "min_gap_ms" in profile.rules

    def test_profile_default_values(self):
        profile = pipeline_default()
        assert profile.rules["max_chars"] == 42
        assert profile.rules["max_lines"] == 2
        assert profile.rules["target_cps"] == 20
        assert profile.rules["min_dur_ms"] == 800
        assert profile.rules["max_dur_ms"] == 7000
        assert profile.rules["min_gap_ms"] == 80

    def test_all_builtin_profiles_exist(self):
        assert "pipeline_default" in BUILTIN_PROFILES
        assert "accessible_general" in BUILTIN_PROFILES
        assert "short_form_social" in BUILTIN_PROFILES

    def test_clean_document_has_no_issues(self):
        """A well-formed document should produce no lint issues."""
        doc = _make_doc(
            (0, 2000, "Short text"),
            (2100, 4000, "Another line"),
            (4100, 6000, "Third one here"),
        )
        profile = pipeline_default()
        issues = run_lint(doc, profile)
        assert len(issues) == 0


class TestCheckMaxChars:
    """Test the max_chars lint rule."""

    def test_short_lines_pass(self):
        doc = _make_doc((0, 2000, "Short text"))
        issues = check_max_chars(doc, 42)
        assert len(issues) == 0

    def test_long_line_flagged(self):
        long_text = "A" * 50
        doc = _make_doc((0, 5000, long_text))
        issues = check_max_chars(doc, 42)
        assert len(issues) == 1
        assert issues[0].rule_id == "max_chars"
        assert issues[0].entry_index == 0

    def test_multiline_checks_each_line(self):
        doc = _make_doc((0, 5000, "Short\n" + "B" * 50))
        issues = check_max_chars(doc, 42)
        assert len(issues) == 1


class TestCheckCps:
    """Test the CPS (characters per second) lint rule."""

    def test_normal_cps_passes(self):
        # 10 chars in 2 seconds = 5 CPS
        doc = _make_doc((0, 2000, "0123456789"))
        issues = check_cps(doc, 20)
        assert len(issues) == 0

    def test_high_cps_flagged(self):
        # 40 chars in 1 second = 40 CPS
        doc = _make_doc((0, 1000, "A" * 40))
        issues = check_cps(doc, 20)
        assert len(issues) == 1
        assert issues[0].rule_id == "cps"

    def test_zero_duration_skipped(self):
        doc = _make_doc((1000, 1000, "Some text"))
        issues = check_cps(doc, 20)
        assert len(issues) == 0


class TestCheckMinGap:
    """Test the min_gap lint rule."""

    def test_sufficient_gap_passes(self):
        doc = _make_doc(
            (0, 1000, "First"),
            (1100, 2000, "Second"),
        )
        issues = check_min_gap(doc, 80)
        assert len(issues) == 0

    def test_small_gap_flagged(self):
        doc = _make_doc(
            (0, 1000, "First"),
            (1050, 2000, "Second"),
        )
        issues = check_min_gap(doc, 80)
        assert len(issues) == 1
        assert issues[0].rule_id == "min_gap"
        assert issues[0].auto_fixable is True

    def test_no_gap_flagged(self):
        doc = _make_doc(
            (0, 1000, "First"),
            (1000, 2000, "Second"),
        )
        issues = check_min_gap(doc, 80)
        assert len(issues) == 1


class TestCheckOverlap:
    """Test the overlap lint rule."""

    def test_no_overlap_passes(self):
        doc = _make_doc(
            (0, 1000, "First"),
            (1500, 2500, "Second"),
        )
        issues = check_overlap(doc)
        assert len(issues) == 0

    def test_overlap_flagged(self):
        doc = _make_doc(
            (0, 2000, "First"),
            (1500, 3000, "Second"),
        )
        issues = check_overlap(doc)
        assert len(issues) == 1
        assert issues[0].rule_id == "overlap"
        assert issues[0].severity == "error"

    def test_multiple_overlaps(self):
        doc = _make_doc(
            (0, 2000, "First"),
            (1500, 3000, "Second"),
            (2500, 4000, "Third"),
        )
        issues = check_overlap(doc)
        assert len(issues) == 2


class TestCheckEmptyText:
    """Test the empty_text lint rule."""

    def test_non_empty_passes(self):
        doc = _make_doc((0, 1000, "Hello"))
        issues = check_empty_text(doc)
        assert len(issues) == 0

    def test_empty_text_flagged(self):
        doc = _make_doc((0, 1000, ""))
        issues = check_empty_text(doc)
        assert len(issues) == 1
        assert issues[0].rule_id == "empty_text"
        assert issues[0].severity == "error"

    def test_whitespace_only_flagged(self):
        doc = _make_doc((0, 1000, "   "))
        issues = check_empty_text(doc)
        assert len(issues) == 1


class TestRunLint:
    """Test the full lint runner."""

    def test_run_lint_returns_sorted_issues(self):
        doc = _make_doc(
            (0, 1000, "A" * 50),   # max_chars violation
            (1050, 1200, "Short"),  # min_duration violation (150ms < 800ms)
            (1100, 2000, "Ok"),     # overlap with previous
        )
        profile = pipeline_default()
        issues = run_lint(doc, profile)

        assert len(issues) > 0
        # Issues should be sorted by entry_index
        indices = [issue.entry_index for issue in issues]
        assert indices == sorted(indices)

    def test_run_lint_with_different_profiles(self):
        doc = _make_doc((0, 2000, "A" * 35))

        # Pipeline default: max_chars=42, should pass
        issues_default = run_lint(doc, BUILTIN_PROFILES["pipeline_default"])

        # Short-form social: max_chars=30, should flag
        issues_social = run_lint(doc, BUILTIN_PROFILES["short_form_social"])

        default_char_issues = [i for i in issues_default if i.rule_id == "max_chars"]
        social_char_issues = [i for i in issues_social if i.rule_id == "max_chars"]

        assert len(default_char_issues) == 0
        assert len(social_char_issues) == 1
