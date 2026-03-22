"""Tests for the Advanced tab prompt and replacement rule management.

These tests validate the AdvancedTab's data layer interactions — speaker
filtering, table refresh, and the helpers that read/write through the
correction database.  Qt widget tests use qtbot where needed.
"""
from __future__ import annotations

import json

import pytest

from audio_visualizer.core.correctionDb import CorrectionDatabase


# ------------------------------------------------------------------
# Database-level tests (no Qt required)
# ------------------------------------------------------------------


class TestAdvancedTabDbIntegration:
    """Test the data operations that the Advanced tab relies on."""

    @pytest.fixture
    def db(self, tmp_path):
        return CorrectionDatabase(db_path=tmp_path / "test.db")

    def test_prompt_terms_lifecycle(self, db):
        """Add, list, update, remove prompt terms."""
        db.add_prompt_term("Kubernetes", category="tech")
        db.add_prompt_term("Docker", category="tech")
        db.add_prompt_term("Whisper", category="model")

        terms = db.list_prompt_terms()
        assert len(terms) == 3

        # Filter by text
        filtered = db.list_prompt_terms(filter_text="Kube")
        assert len(filtered) == 1
        assert filtered[0]["term"] == "Kubernetes"

        # Update
        db.update_prompt_term(terms[0]["id"], term="NewTerm")
        updated = db.list_prompt_terms()
        term_names = {t["term"] for t in updated}
        assert "NewTerm" in term_names

        # Remove
        db.remove_prompt_term(terms[1]["id"])
        assert db.prompt_term_count() == 2

    def test_replacement_rules_lifecycle(self, db):
        """Add, list, update, remove replacement rules."""
        db.add_replacement_rule("gonna", "going to")
        db.add_replacement_rule("wanna", "want to")
        db.add_replacement_rule(r"\bum+\b", "", is_regex=True)

        rules = db.list_replacement_rules()
        assert len(rules) == 3

        # Filter
        filtered = db.list_replacement_rules(filter_text="gonna")
        assert len(filtered) == 1

        # Update — find "gonna" by pattern and update it
        gonna_rule = next(r for r in rules if r["pattern"] == "gonna")
        db.update_replacement_rule(gonna_rule["id"], replacement="going to (updated)")
        updated = db.list_replacement_rules()
        replacements = {r["pattern"]: r["replacement"] for r in updated}
        assert replacements["gonna"] == "going to (updated)"

        # Remove — find the regex rule
        regex_rule = next(r for r in rules if r["pattern"] == r"\bum+\b")
        db.remove_replacement_rule(regex_rule["id"])
        assert db.replacement_rule_count() == 2

    def test_speaker_filtering(self, db):
        """Speaker filter should partition data correctly."""
        db.add_prompt_term("TermA", speaker_label="Alice")
        db.add_prompt_term("TermB", speaker_label="Bob")
        db.add_prompt_term("TermC")

        alice = db.list_prompt_terms(speaker_label="Alice")
        assert len(alice) == 1
        assert alice[0]["term"] == "TermA"

        no_speaker = db.list_prompt_terms(speaker_label=None)
        assert len(no_speaker) == 1
        assert no_speaker[0]["term"] == "TermC"

        # All (no filter = Ellipsis)
        all_terms = db.list_prompt_terms()
        assert len(all_terms) == 3

    def test_speaker_labels_from_corrections(self, db):
        """distinct_speaker_labels pulls from correction rows."""
        db.record_correction(
            source_media_path="/a.wav",
            time_start_ms=0,
            time_end_ms=100,
            original_text="a",
            corrected_text="b",
            speaker_label="Alice",
        )
        db.record_correction(
            source_media_path="/a.wav",
            time_start_ms=100,
            time_end_ms=200,
            original_text="c",
            corrected_text="d",
            speaker_label="Bob",
        )
        labels = db.distinct_speaker_labels()
        assert labels == ["Alice", "Bob"]

    def test_speaker_labels_include_prompt_terms_and_rules(self, db):
        """Speaker label discovery should include all correction DB tables."""
        db.add_prompt_term("DomainTerm", speaker_label="Carol")
        db.add_replacement_rule("foo", "bar", speaker_label="Dave")

        labels = db.distinct_speaker_labels()
        assert labels == ["Carol", "Dave"]

    def test_export_prompt_text(self, db):
        """Export produces comma-separated terms."""
        db.add_prompt_term("Alpha")
        db.add_prompt_term("Beta")
        text = db.export_prompt_text()
        assert "Alpha" in text
        assert "Beta" in text
        assert ", " in text

    def test_export_replacement_dict(self, db):
        """Export produces a list of rule dicts."""
        db.add_replacement_rule("pat1", "repl1")
        db.add_replacement_rule("pat2", "repl2", is_regex=True)
        exported = db.export_replacement_dict()
        assert len(exported) == 2
        patterns = {r["pattern"] for r in exported}
        assert patterns == {"pat1", "pat2"}

    def test_export_prompt_text_empty(self, db):
        """Empty database produces empty export string."""
        assert db.export_prompt_text() == ""

    def test_export_replacement_dict_empty(self, db):
        """Empty database produces empty export list."""
        assert db.export_replacement_dict() == []


# ------------------------------------------------------------------
# Qt widget tests (require qtbot)
# ------------------------------------------------------------------


class TestAdvancedTabWidget:
    """Test the AdvancedTab widget construction and refresh."""

    @pytest.fixture
    def tab(self, qtbot, tmp_path):
        from audio_visualizer.ui.tabs.advancedTab import AdvancedTab

        tab = AdvancedTab()
        qtbot.addWidget(tab)

        # Inject a temp DB so tests don't touch real data
        db = CorrectionDatabase(db_path=tmp_path / "test.db")
        tab._db = db
        return tab

    def test_tab_identity(self, tab):
        assert tab.tab_id == "advanced"
        assert tab.tab_title == "Advanced"

    def test_validate_settings(self, tab):
        valid, msg = tab.validate_settings()
        assert valid is True

    def test_collect_settings(self, tab):
        settings = tab.collect_settings()
        assert isinstance(settings, dict)
        assert "speaker_filter" in settings

    def test_prompt_table_refreshes(self, tab):
        db = tab._db
        db.add_prompt_term("TestTerm", category="test")
        tab._refresh_prompt_terms()
        assert tab._prompt_table.rowCount() == 1
        assert tab._prompt_table.item(0, 0).text() == "TestTerm"

    def test_rules_table_refreshes(self, tab):
        db = tab._db
        db.add_replacement_rule("gonna", "going to")
        tab._refresh_replacement_rules()
        assert tab._rules_table.rowCount() == 1
        assert tab._rules_table.item(0, 0).text() == "gonna"
        assert tab._rules_table.item(0, 1).text() == "going to"

    def test_speaker_combo_populates(self, tab):
        db = tab._db
        db.record_correction(
            source_media_path="/a.wav",
            time_start_ms=0,
            time_end_ms=100,
            original_text="a",
            corrected_text="b",
            speaker_label="Alice",
        )
        tab._refresh_speaker_labels()
        # Should have "(all speakers)" + "Alice"
        assert tab._speaker_combo.count() == 2
        assert tab._speaker_combo.itemText(1) == "Alice"

    def test_apply_settings_restores_pending_speaker_filter(self, tab):
        db = tab._db
        db.record_correction(
            source_media_path="/a.wav",
            time_start_ms=0,
            time_end_ms=100,
            original_text="a",
            corrected_text="b",
            speaker_label="Alice",
        )

        tab.apply_settings({"speaker_filter": "Alice"})
        assert tab._speaker_combo.currentData() is None

        tab._refresh_speaker_labels()
        assert tab._speaker_combo.currentData() == "Alice"

    def test_speaker_filter_partitions_terms(self, tab):
        db = tab._db
        db.add_prompt_term("Global", speaker_label=None)
        db.add_prompt_term("ForAlice", speaker_label="Alice")

        # Record a correction so Alice appears in the speaker combo
        db.record_correction(
            source_media_path="/a.wav",
            time_start_ms=0,
            time_end_ms=100,
            original_text="x",
            corrected_text="y",
            speaker_label="Alice",
        )
        tab._refresh_speaker_labels()

        # Default: all speakers
        tab._refresh_prompt_terms()
        assert tab._prompt_table.rowCount() == 2

        # Select Alice
        idx = tab._speaker_combo.findData("Alice")
        tab._speaker_combo.setCurrentIndex(idx)
        tab._refresh_prompt_terms()
        assert tab._prompt_table.rowCount() == 1
        assert tab._prompt_table.item(0, 0).text() == "ForAlice"

    def test_prompt_filter_text(self, tab):
        db = tab._db
        db.add_prompt_term("Alpha")
        db.add_prompt_term("Beta")
        db.add_prompt_term("AlphaBeta")

        tab._prompt_filter_edit.setText("Alpha")
        # textChanged signal triggers refresh
        assert tab._prompt_table.rowCount() == 2

    def test_rules_filter_text(self, tab):
        db = tab._db
        db.add_replacement_rule("gonna", "going to")
        db.add_replacement_rule("wanna", "want to")

        tab._rules_filter_edit.setText("gonna")
        assert tab._rules_table.rowCount() == 1

    def test_prompt_remove(self, tab):
        db = tab._db
        db.add_prompt_term("ToRemove")
        tab._refresh_prompt_terms()
        assert tab._prompt_table.rowCount() == 1

        # Select the row
        tab._prompt_table.selectRow(0)
        term_id = tab._selected_prompt_term_id()
        assert term_id is not None

        # Remove directly (avoids dialog)
        db.remove_prompt_term(term_id)
        tab._refresh_prompt_terms()
        assert tab._prompt_table.rowCount() == 0

    def test_rules_remove(self, tab):
        db = tab._db
        db.add_replacement_rule("pat", "repl")
        tab._refresh_replacement_rules()
        assert tab._rules_table.rowCount() == 1

        tab._rules_table.selectRow(0)
        rule_id = tab._selected_rule_id()
        assert rule_id is not None

        db.remove_replacement_rule(rule_id)
        tab._refresh_replacement_rules()
        assert tab._rules_table.rowCount() == 0

    def test_rules_add_can_create_regex_rule(self, tab, monkeypatch):
        db = tab._db
        text_answers = iter([
            ("\\bum\\b", True),
            ("", True),
        ])

        monkeypatch.setattr(
            "audio_visualizer.ui.tabs.advancedTab.QInputDialog.getText",
            lambda *args, **kwargs: next(text_answers),
        )
        monkeypatch.setattr(
            "audio_visualizer.ui.tabs.advancedTab.QInputDialog.getItem",
            lambda *args, **kwargs: ("Yes", True),
        )

        tab._on_rules_add()

        rules = db.list_replacement_rules()
        assert len(rules) == 1
        assert rules[0]["pattern"] == "\\bum\\b"
        assert bool(rules[0]["is_regex"]) is True

    def test_rules_edit_can_toggle_regex_flag(self, tab, monkeypatch):
        db = tab._db
        db.add_replacement_rule("gonna", "going to", is_regex=False)
        tab._refresh_replacement_rules()
        tab._rules_table.selectRow(0)

        text_answers = iter([
            ("gonna+", True),
            ("going to", True),
        ])

        monkeypatch.setattr(
            "audio_visualizer.ui.tabs.advancedTab.QInputDialog.getText",
            lambda *args, **kwargs: next(text_answers),
        )
        monkeypatch.setattr(
            "audio_visualizer.ui.tabs.advancedTab.QInputDialog.getItem",
            lambda *args, **kwargs: ("Yes", True),
        )

        tab._on_rules_edit()

        rules = db.list_replacement_rules()
        assert len(rules) == 1
        assert rules[0]["pattern"] == "gonna+"
        assert bool(rules[0]["is_regex"]) is True

    def test_export_prompt_file(self, tab, tmp_path):
        """Export prompt terms to a file."""
        db = tab._db
        db.add_prompt_term("Kubernetes")
        db.add_prompt_term("Docker")

        out_path = tmp_path / "prompt.txt"
        text = db.export_prompt_text()
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)

        content = out_path.read_text(encoding="utf-8")
        assert "Kubernetes" in content
        assert "Docker" in content

    def test_export_rules_file(self, tab, tmp_path):
        """Export replacement rules to a JSON file."""
        db = tab._db
        db.add_replacement_rule("gonna", "going to")
        db.add_replacement_rule(r"\bum\b", "", is_regex=True)

        rules = db.export_replacement_dict()
        out_path = tmp_path / "rules.json"
        export_data = [
            {
                "pattern": r["pattern"],
                "replacement": r["replacement"],
                "is_regex": bool(r.get("is_regex")),
            }
            for r in rules
        ]
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)

        loaded = json.loads(out_path.read_text(encoding="utf-8"))
        assert len(loaded) == 2
        patterns = {r["pattern"] for r in loaded}
        assert "gonna" in patterns
