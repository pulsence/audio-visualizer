"""Tests for the correction database (CorrectionDatabase)."""
from __future__ import annotations

import pytest

from audio_visualizer.core.correctionDb import CorrectionDatabase


@pytest.fixture
def db(tmp_path):
    """Return a CorrectionDatabase backed by a temp file."""
    return CorrectionDatabase(db_path=tmp_path / "test_corrections.db")


# ------------------------------------------------------------------
# Schema
# ------------------------------------------------------------------


class TestSchema:
    """Verify schema creation and re-open safety."""

    def test_schema_creates_tables(self, db):
        conn = db._connect()
        try:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        finally:
            conn.close()
        assert "corrections" in tables
        assert "prompt_terms" in tables
        assert "replacement_rules" in tables
        assert "meta" in tables

    def test_reopen_is_safe(self, tmp_path):
        path = tmp_path / "reopen.db"
        db1 = CorrectionDatabase(db_path=path)
        db1.add_prompt_term("test_term")
        db2 = CorrectionDatabase(db_path=path)
        assert db2.prompt_term_count() == 1


# ------------------------------------------------------------------
# Corrections CRUD
# ------------------------------------------------------------------


class TestCorrections:
    """Test recording and querying corrections."""

    def _record(self, db, **overrides):
        defaults = dict(
            source_media_path="/media/audio.wav",
            time_start_ms=1000,
            time_end_ms=3000,
            original_text="hello world",
            corrected_text="Hello, world!",
            speaker_label="SPEAKER_00",
            model_name="large-v3",
            bundle_entry_id="entry-001",
        )
        defaults.update(overrides)
        return db.record_correction(**defaults)

    def test_record_and_query(self, db):
        rowid = self._record(db)
        assert rowid > 0

        rows = db.query_corrections()
        assert len(rows) == 1
        assert rows[0]["original_text"] == "hello world"
        assert rows[0]["corrected_text"] == "Hello, world!"
        assert rows[0]["speaker_label"] == "SPEAKER_00"

    def test_no_change_skipped(self, db):
        rowid = db.record_correction(
            source_media_path="/media/a.wav",
            time_start_ms=0,
            time_end_ms=1000,
            original_text="same",
            corrected_text="same",
        )
        assert rowid == -1
        assert db.correction_count() == 0

    def test_query_filter_by_speaker(self, db):
        self._record(db, speaker_label="A", corrected_text="x1")
        self._record(db, speaker_label="B", corrected_text="x2")

        rows_a = db.query_corrections(speaker_label="A")
        assert len(rows_a) == 1
        assert rows_a[0]["speaker_label"] == "A"

    def test_query_filter_by_media(self, db):
        self._record(db, source_media_path="/a.wav", corrected_text="x1")
        self._record(db, source_media_path="/b.wav", corrected_text="x2")

        rows = db.query_corrections(source_media_path="/a.wav")
        assert len(rows) == 1

    def test_duplicate_correction_skipped(self, db):
        first = self._record(db)
        duplicate = self._record(db)

        assert first > 0
        assert duplicate == -1
        assert db.correction_count() == 1

    def test_query_filter_by_model(self, db):
        self._record(db, model_name="tiny", corrected_text="x1")
        self._record(db, model_name="large-v3", corrected_text="x2")

        rows = db.query_corrections(model_name="tiny")
        assert len(rows) == 1

    def test_query_limit(self, db):
        for i in range(10):
            self._record(db, corrected_text=f"edit_{i}")
        rows = db.query_corrections(limit=3)
        assert len(rows) == 3

    def test_distinct_speaker_labels(self, db):
        self._record(db, speaker_label="A", corrected_text="x1")
        self._record(db, speaker_label="B", corrected_text="x2")
        self._record(db, speaker_label="A", corrected_text="x3")
        self._record(db, speaker_label=None, corrected_text="x4")

        labels = db.distinct_speaker_labels()
        assert labels == ["A", "B"]

    def test_correction_count(self, db):
        assert db.correction_count() == 0
        self._record(db)
        assert db.correction_count() == 1


# ------------------------------------------------------------------
# Prompt terms CRUD
# ------------------------------------------------------------------


class TestPromptTerms:
    """Test prompt term management."""

    def test_add_and_list(self, db):
        db.add_prompt_term("Kubernetes")
        db.add_prompt_term("Docker")

        terms = db.list_prompt_terms()
        names = [t["term"] for t in terms]
        assert "Docker" in names
        assert "Kubernetes" in names

    def test_duplicate_ignored(self, db):
        db.add_prompt_term("MyTerm")
        db.add_prompt_term("MyTerm")
        assert db.prompt_term_count() == 1

    def test_same_term_different_speaker(self, db):
        db.add_prompt_term("Word", speaker_label="A")
        db.add_prompt_term("Word", speaker_label="B")
        assert db.prompt_term_count() == 2

    def test_update_prompt_term(self, db):
        db.add_prompt_term("OldTerm")
        terms = db.list_prompt_terms()
        term_id = terms[0]["id"]

        ok = db.update_prompt_term(term_id, term="NewTerm", category="domain")
        assert ok is True

        updated = db.list_prompt_terms()
        assert updated[0]["term"] == "NewTerm"
        assert updated[0]["category"] == "domain"

    def test_remove_prompt_term(self, db):
        db.add_prompt_term("ToRemove")
        terms = db.list_prompt_terms()
        assert len(terms) == 1

        ok = db.remove_prompt_term(terms[0]["id"])
        assert ok is True
        assert db.prompt_term_count() == 0

    def test_remove_nonexistent(self, db):
        assert db.remove_prompt_term(9999) is False

    def test_filter_by_speaker(self, db):
        db.add_prompt_term("TermA", speaker_label="X")
        db.add_prompt_term("TermB", speaker_label="Y")
        db.add_prompt_term("TermC")

        results = db.list_prompt_terms(speaker_label="X")
        assert len(results) == 1
        assert results[0]["term"] == "TermA"

        results_none = db.list_prompt_terms(speaker_label=None)
        assert len(results_none) == 1
        assert results_none[0]["term"] == "TermC"

    def test_filter_by_text(self, db):
        db.add_prompt_term("Alpha")
        db.add_prompt_term("Beta")
        db.add_prompt_term("AlphaBeta")

        results = db.list_prompt_terms(filter_text="Alpha")
        assert len(results) == 2

    def test_export_prompt_text(self, db):
        db.add_prompt_term("Docker")
        db.add_prompt_term("Kubernetes")
        text = db.export_prompt_text()
        assert "Docker" in text
        assert "Kubernetes" in text
        assert ", " in text

    def test_prompt_term_count(self, db):
        assert db.prompt_term_count() == 0
        db.add_prompt_term("A")
        assert db.prompt_term_count() == 1


# ------------------------------------------------------------------
# Replacement rules CRUD
# ------------------------------------------------------------------


class TestReplacementRules:
    """Test replacement rule management."""

    def test_add_and_list(self, db):
        db.add_replacement_rule("gonna", "going to")
        db.add_replacement_rule("wanna", "want to")

        rules = db.list_replacement_rules()
        patterns = [r["pattern"] for r in rules]
        assert "gonna" in patterns
        assert "wanna" in patterns

    def test_add_regex_rule(self, db):
        rid = db.add_replacement_rule(r"\bum+\b", "", is_regex=True)
        assert rid > 0

        rules = db.list_replacement_rules()
        assert rules[0]["is_regex"] == 1

    def test_update_replacement_rule(self, db):
        db.add_replacement_rule("old_pat", "old_repl")
        rules = db.list_replacement_rules()
        rule_id = rules[0]["id"]

        ok = db.update_replacement_rule(rule_id, pattern="new_pat", replacement="new_repl")
        assert ok is True

        updated = db.list_replacement_rules()
        assert updated[0]["pattern"] == "new_pat"
        assert updated[0]["replacement"] == "new_repl"

    def test_remove_replacement_rule(self, db):
        db.add_replacement_rule("pat", "repl")
        rules = db.list_replacement_rules()
        assert len(rules) == 1

        ok = db.remove_replacement_rule(rules[0]["id"])
        assert ok is True
        assert db.replacement_rule_count() == 0

    def test_remove_nonexistent(self, db):
        assert db.remove_replacement_rule(9999) is False

    def test_filter_by_speaker(self, db):
        db.add_replacement_rule("a", "b", speaker_label="X")
        db.add_replacement_rule("c", "d", speaker_label="Y")

        results = db.list_replacement_rules(speaker_label="X")
        assert len(results) == 1
        assert results[0]["pattern"] == "a"

    def test_filter_by_text(self, db):
        db.add_replacement_rule("alpha", "ALPHA")
        db.add_replacement_rule("beta", "BETA")

        results = db.list_replacement_rules(filter_text="alpha")
        assert len(results) == 1

    def test_export_replacement_dict(self, db):
        db.add_replacement_rule("x", "y")
        exported = db.export_replacement_dict()
        assert len(exported) == 1
        assert exported[0]["pattern"] == "x"

    def test_replacement_rule_count(self, db):
        assert db.replacement_rule_count() == 0
        db.add_replacement_rule("p", "r")
        assert db.replacement_rule_count() == 1


# ------------------------------------------------------------------
# Training export
# ------------------------------------------------------------------


class TestTrainingExport:
    """Test the training pairs export."""

    def test_export_all(self, db):
        db.record_correction(
            source_media_path="/a.wav",
            time_start_ms=100,
            time_end_ms=200,
            original_text="wrong",
            corrected_text="right",
            speaker_label="S0",
            model_name="tiny",
        )
        pairs = db.export_training_pairs()
        assert len(pairs) == 1
        assert pairs[0]["audio_ref"] == "/a.wav"
        assert pairs[0]["original_text"] == "wrong"
        assert pairs[0]["corrected_text"] == "right"

    def test_export_filtered(self, db):
        db.record_correction(
            source_media_path="/a.wav",
            time_start_ms=0,
            time_end_ms=100,
            original_text="a",
            corrected_text="b",
            model_name="tiny",
        )
        db.record_correction(
            source_media_path="/b.wav",
            time_start_ms=0,
            time_end_ms=100,
            original_text="c",
            corrected_text="d",
            model_name="large",
        )

        pairs = db.export_training_pairs(model_name="tiny")
        assert len(pairs) == 1
        assert pairs[0]["audio_ref"] == "/a.wav"
