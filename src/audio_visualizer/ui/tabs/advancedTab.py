"""Advanced tab — correction database management, prompt terms, replacement rules,
training data export, and LoRA training controls.

Provides user-facing tools for managing prompt terms (used as Whisper
initial_prompt), replacement rules (post-transcription dictionary), training
dataset export, and LoRA fine-tuning controls.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
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

        # -- Training data export --
        root_layout.addWidget(self._build_training_export_section())

        # -- LoRA training controls --
        root_layout.addWidget(self._build_lora_training_section())

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

    def _build_training_export_section(self) -> QWidget:
        """Build the Training Data Export action group."""
        group = QGroupBox("Training Data Export")
        layout = QHBoxLayout()

        self._export_training_btn = QPushButton("Export Training Data")
        self._export_training_btn.setToolTip(
            "Export correction pairs as audio clips + metadata.csv for LoRA training"
        )
        layout.addWidget(self._export_training_btn)

        self._export_training_status = QLabel("")
        layout.addWidget(self._export_training_status, 1)
        layout.addStretch()

        group.setLayout(layout)
        return group

    def _build_lora_training_section(self) -> QWidget:
        """Build the LoRA training controls group."""
        group = QGroupBox("LoRA Training")
        layout = QVBoxLayout()

        # Capability status
        self._training_capability_label = QLabel("")
        layout.addWidget(self._training_capability_label)

        # Row 1: base model + dataset source + output name
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Base Model:"))
        self._train_base_model_combo = QComboBox()
        self._train_base_model_combo.addItems(["tiny", "base", "small", "medium", "large", "turbo"])
        self._train_base_model_combo.setCurrentText("base")
        row1.addWidget(self._train_base_model_combo)

        row1.addWidget(QLabel("Dataset:"))
        self._train_dataset_edit = QLineEdit()
        self._train_dataset_edit.setPlaceholderText("Path to dataset directory")
        row1.addWidget(self._train_dataset_edit, 1)

        self._train_dataset_browse_btn = QPushButton("Browse...")
        row1.addWidget(self._train_dataset_browse_btn)

        row1.addWidget(QLabel("Output Name:"))
        self._train_output_name_edit = QLineEdit()
        self._train_output_name_edit.setPlaceholderText("my_lora_model")
        row1.addWidget(self._train_output_name_edit)
        layout.addLayout(row1)

        # Row 2: hyperparameters
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Epochs:"))
        self._train_epochs_spin = QSpinBox()
        self._train_epochs_spin.setRange(1, 100)
        self._train_epochs_spin.setValue(3)
        row2.addWidget(self._train_epochs_spin)

        row2.addWidget(QLabel("Learning Rate:"))
        self._train_lr_spin = QDoubleSpinBox()
        self._train_lr_spin.setRange(1e-6, 1e-2)
        self._train_lr_spin.setDecimals(6)
        self._train_lr_spin.setSingleStep(1e-5)
        self._train_lr_spin.setValue(1e-4)
        row2.addWidget(self._train_lr_spin)

        row2.addWidget(QLabel("Batch Size:"))
        self._train_batch_size_spin = QSpinBox()
        self._train_batch_size_spin.setRange(1, 64)
        self._train_batch_size_spin.setValue(4)
        row2.addWidget(self._train_batch_size_spin)

        row2.addWidget(QLabel("LoRA Rank:"))
        self._train_lora_rank_spin = QSpinBox()
        self._train_lora_rank_spin.setRange(1, 128)
        self._train_lora_rank_spin.setValue(8)
        row2.addWidget(self._train_lora_rank_spin)
        row2.addStretch()
        layout.addLayout(row2)

        # Row 3: actions
        row3 = QHBoxLayout()
        self._train_start_btn = QPushButton("Start Training")
        row3.addWidget(self._train_start_btn)

        self._train_cancel_btn = QPushButton("Cancel")
        self._train_cancel_btn.setEnabled(False)
        row3.addWidget(self._train_cancel_btn)
        row3.addStretch()
        layout.addLayout(row3)

        # Progress
        self._train_progress_bar = QProgressBar()
        self._train_progress_bar.setRange(0, 100)
        self._train_progress_bar.setValue(0)
        layout.addWidget(self._train_progress_bar)

        self._train_status_label = QLabel("Ready")
        layout.addWidget(self._train_status_label)

        # Trained models list
        models_row = QHBoxLayout()
        models_row.addWidget(QLabel("Trained Models:"))
        self._trained_models_list = QListWidget()
        self._trained_models_list.setMaximumHeight(100)
        models_row.addWidget(self._trained_models_list, 1)

        models_btn_col = QVBoxLayout()
        self._train_refresh_btn = QPushButton("Refresh")
        models_btn_col.addWidget(self._train_refresh_btn)
        self._train_delete_btn = QPushButton("Delete")
        models_btn_col.addWidget(self._train_delete_btn)
        models_btn_col.addStretch()
        models_row.addLayout(models_btn_col)
        layout.addLayout(models_row)

        group.setLayout(layout)
        self._update_training_capability_label()
        return group

    def _update_training_capability_label(self) -> None:
        """Update the capability status label based on runtime checks."""
        try:
            from audio_visualizer.capabilities import has_training_stack, has_cuda

            if not has_training_stack():
                self._training_capability_label.setText(
                    "<span style='color: orange;'>Training stack unavailable "
                    "(requires torch, transformers, peft, ctranslate2)</span>"
                )
                self._train_start_btn.setEnabled(False)
                return

            if not has_cuda():
                self._training_capability_label.setText(
                    "<span style='color: orange;'>CUDA unavailable — "
                    "training requires a CUDA-capable GPU</span>"
                )
                self._train_start_btn.setEnabled(False)
                return

            self._training_capability_label.setText(
                "<span style='color: green;'>Training stack ready (CUDA available)</span>"
            )
            self._train_start_btn.setEnabled(True)
        except Exception:
            self._training_capability_label.setText(
                "<span style='color: red;'>Could not check training capabilities</span>"
            )
            self._train_start_btn.setEnabled(False)

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

        # Training data export
        self._export_training_btn.clicked.connect(self._on_export_training_data)

        # LoRA training
        self._train_dataset_browse_btn.clicked.connect(self._on_train_browse_dataset)
        self._train_start_btn.clicked.connect(self._on_train_start)
        self._train_cancel_btn.clicked.connect(self._on_train_cancel)
        self._train_refresh_btn.clicked.connect(self._refresh_trained_models)
        self._train_delete_btn.clicked.connect(self._on_train_delete_model)

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
    # Training data export
    # ------------------------------------------------------------------

    def _on_export_training_data(self) -> None:
        """Export correction pairs as audio clips + metadata.csv."""
        db = self._get_db()
        if db is None:
            QMessageBox.warning(self, "Error", "Correction database not available.")
            return

        count = db.correction_count()
        if count == 0:
            QMessageBox.information(
                self, "Export", "No corrections recorded. Nothing to export."
            )
            return

        output_dir = QFileDialog.getExistingDirectory(
            self, "Select Training Data Output Directory"
        )
        if not output_dir:
            return

        self._export_training_btn.setEnabled(False)
        self._export_training_status.setText("Exporting...")

        try:
            exported, skipped, warnings = db.export_training_dataset(
                Path(output_dir),
            )
            summary = f"Exported {exported} clips, skipped {skipped}."
            self._export_training_status.setText(summary)

            if warnings:
                detail = "\n".join(warnings[:20])
                if len(warnings) > 20:
                    detail += f"\n... and {len(warnings) - 20} more warnings."
                QMessageBox.information(
                    self,
                    "Export Complete",
                    f"{summary}\n\nWarnings:\n{detail}",
                )
            else:
                QMessageBox.information(self, "Export Complete", summary)
            logger.info("Training data export: %s", summary)
        except Exception:
            logger.exception("Training data export failed")
            self._export_training_status.setText("Export failed.")
            QMessageBox.warning(
                self, "Error", "Training data export failed. Check logs for details."
            )
        finally:
            self._export_training_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # LoRA training
    # ------------------------------------------------------------------

    def _on_train_browse_dataset(self) -> None:
        """Browse for a dataset directory."""
        d = QFileDialog.getExistingDirectory(
            self, "Select Training Dataset Directory"
        )
        if d:
            self._train_dataset_edit.setText(d)

    def _on_train_start(self) -> None:
        """Validate and start LoRA training in a background worker."""
        try:
            from audio_visualizer.capabilities import has_training_stack, has_cuda
        except ImportError:
            QMessageBox.warning(self, "Error", "Capabilities module not available.")
            return

        if not has_training_stack():
            QMessageBox.warning(
                self,
                "Training Unavailable",
                "Training stack not available. Install torch, transformers, peft, "
                "and ctranslate2 to enable training.",
            )
            return

        if not has_cuda():
            QMessageBox.warning(
                self,
                "CUDA Required",
                "LoRA training requires a CUDA-capable GPU.",
            )
            return

        dataset_path = self._train_dataset_edit.text().strip()
        if not dataset_path:
            QMessageBox.warning(self, "Validation Error", "Please select a dataset directory.")
            return
        dataset_dir = Path(dataset_path)
        if not dataset_dir.is_dir():
            QMessageBox.warning(self, "Validation Error", "Dataset directory does not exist.")
            return
        metadata_csv = dataset_dir / "metadata.csv"
        if not metadata_csv.is_file():
            QMessageBox.warning(
                self,
                "Validation Error",
                "Dataset directory must contain a metadata.csv file.",
            )
            return

        output_name = self._train_output_name_edit.text().strip()
        if not output_name:
            QMessageBox.warning(self, "Validation Error", "Please enter an output model name.")
            return

        # Build config and launch worker
        from audio_visualizer.srt.training.loraTrainer import LoraTrainingConfig

        config = LoraTrainingConfig(
            base_model_name=self._train_base_model_combo.currentText(),
            dataset_dir=dataset_dir,
            output_name=output_name,
            num_epochs=self._train_epochs_spin.value(),
            learning_rate=self._train_lr_spin.value(),
            batch_size=self._train_batch_size_spin.value(),
            lora_rank=self._train_lora_rank_spin.value(),
        )

        from audio_visualizer.ui.workers.loraTrainWorker import LoraTrainWorker

        self._train_worker = LoraTrainWorker(config)
        self._train_worker.signals.progress.connect(self._on_train_progress)
        self._train_worker.signals.log.connect(self._on_train_log)
        self._train_worker.signals.completed.connect(self._on_train_completed)
        self._train_worker.signals.failed.connect(self._on_train_failed)
        self._train_worker.signals.canceled.connect(self._on_train_canceled)

        self._train_start_btn.setEnabled(False)
        self._train_cancel_btn.setEnabled(True)
        self._train_progress_bar.setValue(0)
        self._train_status_label.setText("Starting training...")

        if not hasattr(self, "_train_thread_pool"):
            self._train_thread_pool = QThreadPool()
            self._train_thread_pool.setMaxThreadCount(1)
        self._train_thread_pool.start(self._train_worker)
        logger.info("Started LoRA training for '%s'", output_name)

    def _on_train_cancel(self) -> None:
        """Cancel the running training job."""
        if hasattr(self, "_train_worker") and self._train_worker is not None:
            self._train_worker.cancel()
            self._train_status_label.setText("Cancelling...")

    def _on_train_progress(self, percent: float, message: str, data: dict) -> None:
        if percent >= 0:
            self._train_progress_bar.setValue(int(percent))
        if message:
            self._train_status_label.setText(message)

    def _on_train_log(self, level: str, message: str, data: dict) -> None:
        logger.log(
            logging.getLevelName(level) if isinstance(level, str) else logging.INFO,
            "LoRA Training: %s",
            message,
        )

    def _on_train_completed(self, data: dict) -> None:
        self._train_worker = None
        self._train_start_btn.setEnabled(True)
        self._train_cancel_btn.setEnabled(False)
        self._train_progress_bar.setValue(100)
        model_name = data.get("output_name", "unknown")
        self._train_status_label.setText(f"Training complete: {model_name}")
        self._refresh_trained_models()
        self._update_training_capability_label()
        QMessageBox.information(
            self, "Training Complete", f"LoRA model '{model_name}' trained successfully."
        )

    def _on_train_failed(self, error_message: str, data: dict) -> None:
        self._train_worker = None
        self._train_start_btn.setEnabled(True)
        self._train_cancel_btn.setEnabled(False)
        self._train_progress_bar.setValue(0)
        self._train_status_label.setText(f"Training failed: {error_message}")
        self._update_training_capability_label()
        QMessageBox.warning(
            self, "Training Failed", f"LoRA training failed:\n{error_message}"
        )

    def _on_train_canceled(self, message: str) -> None:
        self._train_worker = None
        self._train_start_btn.setEnabled(True)
        self._train_cancel_btn.setEnabled(False)
        self._train_status_label.setText(f"Cancelled: {message}")
        self._update_training_capability_label()

    # ------------------------------------------------------------------
    # Trained models management
    # ------------------------------------------------------------------

    def _get_lora_models_dir(self) -> Path:
        """Return the LoRA models directory."""
        from audio_visualizer.app_paths import get_data_dir
        return get_data_dir() / "lora_models"

    def _refresh_trained_models(self) -> None:
        """Refresh the list of trained LoRA models."""
        self._trained_models_list.clear()
        models_dir = self._get_lora_models_dir()
        if not models_dir.is_dir():
            return
        for item in sorted(models_dir.iterdir()):
            if item.is_dir():
                self._trained_models_list.addItem(item.name)

    def _on_train_delete_model(self) -> None:
        """Delete the selected trained model."""
        current = self._trained_models_list.currentItem()
        if current is None:
            return

        model_name = current.text()
        reply = QMessageBox.question(
            self,
            "Delete Model",
            f"Delete trained model '{model_name}'? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        model_dir = self._get_lora_models_dir() / model_name
        if model_dir.is_dir():
            import shutil
            try:
                shutil.rmtree(model_dir)
                logger.info("Deleted trained model: %s", model_name)
            except Exception:
                logger.exception("Failed to delete trained model: %s", model_name)
                QMessageBox.warning(
                    self, "Error", f"Could not delete model '{model_name}'."
                )
                return
        self._refresh_trained_models()

    # ------------------------------------------------------------------
    # Tab activation
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:
        """Refresh data when the tab becomes visible."""
        super().showEvent(event)
        self._refresh_speaker_labels()
        self._refresh_prompt_terms()
        self._refresh_replacement_rules()
        self._refresh_trained_models()
        self._update_training_capability_label()

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------

    def validate_settings(self) -> tuple[bool, str]:
        return True, ""

    def collect_settings(self) -> dict[str, Any]:
        return {
            "speaker_filter": self._speaker_combo.currentData(),
            "training": {
                "base_model": self._train_base_model_combo.currentText(),
                "dataset_dir": self._train_dataset_edit.text(),
                "output_name": self._train_output_name_edit.text(),
                "epochs": self._train_epochs_spin.value(),
                "learning_rate": self._train_lr_spin.value(),
                "batch_size": self._train_batch_size_spin.value(),
                "lora_rank": self._train_lora_rank_spin.value(),
            },
        }

    def apply_settings(self, data: dict[str, Any]) -> None:
        speaker = data.get("speaker_filter")
        if speaker is not None:
            idx = self._speaker_combo.findData(speaker)
            if idx >= 0:
                self._speaker_combo.setCurrentIndex(idx)

        training = data.get("training", {})
        if training:
            base_model = training.get("base_model", "base")
            idx = self._train_base_model_combo.findText(base_model)
            if idx >= 0:
                self._train_base_model_combo.setCurrentIndex(idx)
            self._train_dataset_edit.setText(training.get("dataset_dir", ""))
            self._train_output_name_edit.setText(training.get("output_name", ""))
            self._train_epochs_spin.setValue(training.get("epochs", 3))
            self._train_lr_spin.setValue(training.get("learning_rate", 1e-4))
            self._train_batch_size_spin.setValue(training.get("batch_size", 4))
            self._train_lora_rank_spin.setValue(training.get("lora_rank", 8))
