"""Advanced tab — correction database management, prompt terms, and replacement rules.

Provides user-facing tools for managing prompt terms (used as Whisper
initial_prompt) and replacement rules (post-transcription dictionary).
Phase 6 will add LoRA training controls.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from audio_visualizer.ui.tabs.baseTab import BaseTab

logger = logging.getLogger(__name__)


class AdvancedTab(BaseTab):
    """Advanced tab for prompt management, replacement rules, and training.

    Manages prompt terms that feed Whisper initial_prompt and replacement
    rules for post-transcription dictionary corrections.  Per-speaker
    filtering is supported via a shared speaker-label combo box.
    """

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def tab_id(self) -> str:
        return "advanced"

    @property
    def tab_title(self) -> str:
        return "Advanced"

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._db: Any = None  # Lazy CorrectionDatabase

        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # Lazy DB access
    # ------------------------------------------------------------------

    def _get_db(self):
        """Lazily create and return the CorrectionDatabase."""
        if self._db is None:
            try:
                from audio_visualizer.core.correctionDb import CorrectionDatabase

                self._db = CorrectionDatabase()
            except Exception:
                logger.exception("Failed to initialise correction database")
                return None
        return self._db

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(6, 6, 6, 6)

        # -- Speaker filter row --
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Speaker Filter:"))
        self._speaker_combo = QComboBox()
        self._speaker_combo.setMinimumWidth(160)
        self._speaker_combo.addItem("(all speakers)", None)
        filter_row.addWidget(self._speaker_combo)
        self._refresh_speakers_btn = QPushButton("Refresh")
        self._refresh_speakers_btn.setToolTip("Reload speaker labels from correction database")
        filter_row.addWidget(self._refresh_speakers_btn)
        filter_row.addStretch()
        root_layout.addLayout(filter_row)

        # -- Main splitter (prompt terms top, replacement rules bottom) --
        splitter = QSplitter(Qt.Orientation.Vertical)

        splitter.addWidget(self._build_prompt_terms_section())
        splitter.addWidget(self._build_replacement_rules_section())

        splitter.setSizes([300, 300])
        root_layout.addWidget(splitter, stretch=1)

        self.setLayout(root_layout)

    def _build_prompt_terms_section(self) -> QWidget:
        """Build the Prompt Terms management group."""
        group = QGroupBox("Prompt Terms")
        layout = QVBoxLayout()

        # Filter + action bar
        bar = QHBoxLayout()
        self._prompt_filter_edit = QLineEdit()
        self._prompt_filter_edit.setPlaceholderText("Filter terms...")
        bar.addWidget(self._prompt_filter_edit)
        self._prompt_add_btn = QPushButton("Add")
        self._prompt_edit_btn = QPushButton("Edit")
        self._prompt_remove_btn = QPushButton("Remove")
        self._prompt_export_btn = QPushButton("Export to Prompt")
        bar.addWidget(self._prompt_add_btn)
        bar.addWidget(self._prompt_edit_btn)
        bar.addWidget(self._prompt_remove_btn)
        bar.addWidget(self._prompt_export_btn)
        layout.addLayout(bar)

        # Table
        self._prompt_table = QTableWidget()
        self._prompt_table.setColumnCount(4)
        self._prompt_table.setHorizontalHeaderLabels(
            ["Term", "Category", "Speaker", "Source"]
        )
        self._prompt_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._prompt_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._prompt_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._prompt_table.setAlternatingRowColors(True)
        self._prompt_table.verticalHeader().setVisible(False)
        header = self._prompt_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._prompt_table)

        group.setLayout(layout)
        return group

    def _build_replacement_rules_section(self) -> QWidget:
        """Build the Replacement Rules management group."""
        group = QGroupBox("Replacement Rules")
        layout = QVBoxLayout()

        # Filter + action bar
        bar = QHBoxLayout()
        self._rules_filter_edit = QLineEdit()
        self._rules_filter_edit.setPlaceholderText("Filter rules...")
        bar.addWidget(self._rules_filter_edit)
        self._rules_add_btn = QPushButton("Add")
        self._rules_edit_btn = QPushButton("Edit")
        self._rules_remove_btn = QPushButton("Remove")
        self._rules_export_btn = QPushButton("Export to Dictionary")
        bar.addWidget(self._rules_add_btn)
        bar.addWidget(self._rules_edit_btn)
        bar.addWidget(self._rules_remove_btn)
        bar.addWidget(self._rules_export_btn)
        layout.addLayout(bar)

        # Table
        self._rules_table = QTableWidget()
        self._rules_table.setColumnCount(4)
        self._rules_table.setHorizontalHeaderLabels(
            ["Pattern", "Replacement", "Regex", "Speaker"]
        )
        self._rules_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._rules_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._rules_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._rules_table.setAlternatingRowColors(True)
        self._rules_table.verticalHeader().setVisible(False)
        header = self._rules_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._rules_table)

        group.setLayout(layout)
        return group

    # ------------------------------------------------------------------
    # Signal connections
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._refresh_speakers_btn.clicked.connect(self._refresh_speaker_labels)
        self._speaker_combo.currentIndexChanged.connect(self._on_speaker_filter_changed)

        # Prompt terms
        self._prompt_filter_edit.textChanged.connect(self._refresh_prompt_terms)
        self._prompt_add_btn.clicked.connect(self._on_prompt_add)
        self._prompt_edit_btn.clicked.connect(self._on_prompt_edit)
        self._prompt_remove_btn.clicked.connect(self._on_prompt_remove)
        self._prompt_export_btn.clicked.connect(self._on_prompt_export)

        # Replacement rules
        self._rules_filter_edit.textChanged.connect(self._refresh_replacement_rules)
        self._rules_add_btn.clicked.connect(self._on_rules_add)
        self._rules_edit_btn.clicked.connect(self._on_rules_edit)
        self._rules_remove_btn.clicked.connect(self._on_rules_remove)
        self._rules_export_btn.clicked.connect(self._on_rules_export)

    # ------------------------------------------------------------------
    # Speaker filter
    # ------------------------------------------------------------------

    def _refresh_speaker_labels(self) -> None:
        """Reload distinct speaker labels from the correction database."""
        db = self._get_db()
        if db is None:
            return

        current = self._speaker_combo.currentData()
        self._speaker_combo.blockSignals(True)
        self._speaker_combo.clear()
        self._speaker_combo.addItem("(all speakers)", None)

        try:
            labels = db.distinct_speaker_labels()
            for label in labels:
                self._speaker_combo.addItem(label, label)
        except Exception:
            logger.exception("Failed to load speaker labels")

        # Restore selection if still present
        if current is not None:
            idx = self._speaker_combo.findData(current)
            if idx >= 0:
                self._speaker_combo.setCurrentIndex(idx)
        self._speaker_combo.blockSignals(False)

    def _on_speaker_filter_changed(self) -> None:
        self._refresh_prompt_terms()
        self._refresh_replacement_rules()

    def _selected_speaker(self):
        """Return the selected speaker label, or Ellipsis for 'all'."""
        data = self._speaker_combo.currentData()
        if data is None:
            return ...  # No filter
        return data

    # ------------------------------------------------------------------
    # Prompt terms table
    # ------------------------------------------------------------------

    def _refresh_prompt_terms(self) -> None:
        """Reload the prompt terms table from the database."""
        db = self._get_db()
        if db is None:
            self._prompt_table.setRowCount(0)
            return

        speaker = self._selected_speaker()
        filter_text = self._prompt_filter_edit.text().strip() or None

        try:
            terms = db.list_prompt_terms(
                speaker_label=speaker,
                filter_text=filter_text,
            )
        except Exception:
            logger.exception("Failed to load prompt terms")
            terms = []

        self._prompt_table.setRowCount(len(terms))
        for row_idx, t in enumerate(terms):
            term_item = QTableWidgetItem(t["term"])
            term_item.setData(Qt.ItemDataRole.UserRole, t["id"])
            self._prompt_table.setItem(row_idx, 0, term_item)
            self._prompt_table.setItem(row_idx, 1, QTableWidgetItem(t.get("category") or ""))
            self._prompt_table.setItem(row_idx, 2, QTableWidgetItem(t.get("speaker_label") or ""))
            self._prompt_table.setItem(row_idx, 3, QTableWidgetItem(t.get("source") or ""))

    def _selected_prompt_term_id(self) -> int | None:
        """Return the id of the selected prompt term, or None."""
        row = self._prompt_table.currentRow()
        if row < 0:
            return None
        item = self._prompt_table.item(row, 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _on_prompt_add(self) -> None:
        db = self._get_db()
        if db is None:
            return

        term, ok = QInputDialog.getText(self, "Add Prompt Term", "Term:")
        if not ok or not term.strip():
            return

        category, ok = QInputDialog.getText(
            self, "Add Prompt Term", "Category (optional):"
        )
        if not ok:
            category = ""

        speaker = self._selected_speaker()
        speaker_label = speaker if speaker is not ... else None

        try:
            db.add_prompt_term(
                term.strip(),
                category=category.strip() or None,
                speaker_label=speaker_label,
            )
        except Exception:
            logger.exception("Failed to add prompt term")
            QMessageBox.warning(self, "Error", "Could not add prompt term.")
            return

        self._refresh_prompt_terms()
        self.settings_changed.emit()

    def _on_prompt_edit(self) -> None:
        db = self._get_db()
        term_id = self._selected_prompt_term_id()
        if db is None or term_id is None:
            return

        row = self._prompt_table.currentRow()
        current_term = self._prompt_table.item(row, 0).text()
        current_category = self._prompt_table.item(row, 1).text()

        new_term, ok = QInputDialog.getText(
            self, "Edit Prompt Term", "Term:", text=current_term
        )
        if not ok or not new_term.strip():
            return

        new_category, ok = QInputDialog.getText(
            self, "Edit Prompt Term", "Category:", text=current_category
        )
        if not ok:
            return

        try:
            db.update_prompt_term(
                term_id,
                term=new_term.strip(),
                category=new_category.strip() or None,
            )
        except Exception:
            logger.exception("Failed to update prompt term")
            QMessageBox.warning(self, "Error", "Could not update prompt term.")
            return

        self._refresh_prompt_terms()
        self.settings_changed.emit()

    def _on_prompt_remove(self) -> None:
        db = self._get_db()
        term_id = self._selected_prompt_term_id()
        if db is None or term_id is None:
            return

        try:
            db.remove_prompt_term(term_id)
        except Exception:
            logger.exception("Failed to remove prompt term")
            return

        self._refresh_prompt_terms()
        self.settings_changed.emit()

    def _on_prompt_export(self) -> None:
        """Export prompt terms as a comma-separated text file."""
        db = self._get_db()
        if db is None:
            return

        speaker = self._selected_speaker()

        try:
            text = db.export_prompt_text(speaker_label=speaker)
        except Exception:
            logger.exception("Failed to export prompt terms")
            QMessageBox.warning(self, "Error", "Could not export prompt terms.")
            return

        if not text:
            QMessageBox.information(self, "Export", "No prompt terms to export.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Prompt Terms",
            "prompt_terms.txt",
            "Text Files (*.txt);;All Files (*)",
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            logger.info("Exported prompt terms to %s", path)
        except Exception:
            logger.exception("Failed to write prompt terms file")
            QMessageBox.warning(self, "Error", f"Could not write file:\n{path}")

    # ------------------------------------------------------------------
    # Replacement rules table
    # ------------------------------------------------------------------

    def _refresh_replacement_rules(self) -> None:
        """Reload the replacement rules table from the database."""
        db = self._get_db()
        if db is None:
            self._rules_table.setRowCount(0)
            return

        speaker = self._selected_speaker()
        filter_text = self._rules_filter_edit.text().strip() or None

        try:
            rules = db.list_replacement_rules(
                speaker_label=speaker,
                filter_text=filter_text,
            )
        except Exception:
            logger.exception("Failed to load replacement rules")
            rules = []

        self._rules_table.setRowCount(len(rules))
        for row_idx, r in enumerate(rules):
            pattern_item = QTableWidgetItem(r["pattern"])
            pattern_item.setData(Qt.ItemDataRole.UserRole, r["id"])
            self._rules_table.setItem(row_idx, 0, pattern_item)
            self._rules_table.setItem(row_idx, 1, QTableWidgetItem(r["replacement"]))
            self._rules_table.setItem(
                row_idx, 2, QTableWidgetItem("Yes" if r.get("is_regex") else "No")
            )
            self._rules_table.setItem(
                row_idx, 3, QTableWidgetItem(r.get("speaker_label") or "")
            )

    def _selected_rule_id(self) -> int | None:
        """Return the id of the selected replacement rule, or None."""
        row = self._rules_table.currentRow()
        if row < 0:
            return None
        item = self._rules_table.item(row, 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _on_rules_add(self) -> None:
        db = self._get_db()
        if db is None:
            return

        pattern, ok = QInputDialog.getText(self, "Add Replacement Rule", "Pattern:")
        if not ok or not pattern.strip():
            return

        replacement, ok = QInputDialog.getText(
            self, "Add Replacement Rule", "Replacement:"
        )
        if not ok:
            return

        speaker = self._selected_speaker()
        speaker_label = speaker if speaker is not ... else None

        try:
            db.add_replacement_rule(
                pattern.strip(),
                replacement.strip(),
                speaker_label=speaker_label,
            )
        except Exception:
            logger.exception("Failed to add replacement rule")
            QMessageBox.warning(self, "Error", "Could not add replacement rule.")
            return

        self._refresh_replacement_rules()
        self.settings_changed.emit()

    def _on_rules_edit(self) -> None:
        db = self._get_db()
        rule_id = self._selected_rule_id()
        if db is None or rule_id is None:
            return

        row = self._rules_table.currentRow()
        current_pattern = self._rules_table.item(row, 0).text()
        current_replacement = self._rules_table.item(row, 1).text()

        new_pattern, ok = QInputDialog.getText(
            self, "Edit Replacement Rule", "Pattern:", text=current_pattern
        )
        if not ok or not new_pattern.strip():
            return

        new_replacement, ok = QInputDialog.getText(
            self, "Edit Replacement Rule", "Replacement:", text=current_replacement
        )
        if not ok:
            return

        try:
            db.update_replacement_rule(
                rule_id,
                pattern=new_pattern.strip(),
                replacement=new_replacement.strip(),
            )
        except Exception:
            logger.exception("Failed to update replacement rule")
            QMessageBox.warning(self, "Error", "Could not update replacement rule.")
            return

        self._refresh_replacement_rules()
        self.settings_changed.emit()

    def _on_rules_remove(self) -> None:
        db = self._get_db()
        rule_id = self._selected_rule_id()
        if db is None or rule_id is None:
            return

        try:
            db.remove_replacement_rule(rule_id)
        except Exception:
            logger.exception("Failed to remove replacement rule")
            return

        self._refresh_replacement_rules()
        self.settings_changed.emit()

    def _on_rules_export(self) -> None:
        """Export replacement rules as a JSON dictionary file."""
        db = self._get_db()
        if db is None:
            return

        speaker = self._selected_speaker()

        try:
            rules = db.export_replacement_dict(speaker_label=speaker)
        except Exception:
            logger.exception("Failed to export replacement rules")
            QMessageBox.warning(self, "Error", "Could not export replacement rules.")
            return

        if not rules:
            QMessageBox.information(self, "Export", "No replacement rules to export.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Replacement Dictionary",
            "replacement_dict.json",
            "JSON Files (*.json);;All Files (*)",
        )
        if not path:
            return

        try:
            import json

            export_data = [
                {
                    "pattern": r["pattern"],
                    "replacement": r["replacement"],
                    "is_regex": bool(r.get("is_regex")),
                }
                for r in rules
            ]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            logger.info("Exported replacement rules to %s", path)
        except Exception:
            logger.exception("Failed to write replacement rules file")
            QMessageBox.warning(self, "Error", f"Could not write file:\n{path}")

    # ------------------------------------------------------------------
    # Tab activation
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:
        """Refresh data when the tab becomes visible."""
        super().showEvent(event)
        self._refresh_speaker_labels()
        self._refresh_prompt_terms()
        self._refresh_replacement_rules()

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------

    def validate_settings(self) -> tuple[bool, str]:
        return True, ""

    def collect_settings(self) -> dict[str, Any]:
        return {
            "speaker_filter": self._speaker_combo.currentData(),
        }

    def apply_settings(self, data: dict[str, Any]) -> None:
        speaker = data.get("speaker_filter")
        if speaker is not None:
            idx = self._speaker_combo.findData(speaker)
            if idx >= 0:
                self._speaker_combo.setCurrentIndex(idx)
