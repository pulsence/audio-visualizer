"""Application settings dialog.

Provides a modal dialog with application-level settings such as theme mode.
Uses explicit accept/apply semantics — changes are not persisted until the user
confirms.
"""
from __future__ import annotations

import logging

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

_THEME_OPTIONS = [
    ("off", "Off (Light)"),
    ("on", "On (Dark)"),
    ("auto", "Auto (System)"),
]


class SettingsDialog(QDialog):
    """Modal settings dialog with accept/apply semantics."""

    def __init__(self, current_settings: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)
        self._result_settings: dict = {}
        self._build_ui(current_settings)

    def _build_ui(self, settings: dict) -> None:
        layout = QVBoxLayout()

        # Theme group
        theme_group = QGroupBox("Appearance")
        theme_layout = QFormLayout()

        self._theme_combo = QComboBox()
        for value, label in _THEME_OPTIONS:
            self._theme_combo.addItem(label, value)

        # Set current
        current_theme = settings.get("app", {}).get("theme_mode", "off")
        for i in range(self._theme_combo.count()):
            if self._theme_combo.itemData(i) == current_theme:
                self._theme_combo.setCurrentIndex(i)
                break

        theme_layout.addRow("Theme:", self._theme_combo)
        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)

        # Project folder group
        folder_group = QGroupBox("Project")
        folder_layout = QFormLayout()

        self._project_folder_row = QHBoxLayout()
        self._project_folder_edit = QLineEdit()
        self._project_folder_edit.setPlaceholderText("(not set)")
        self._project_folder_row.addWidget(self._project_folder_edit)
        self._project_folder_browse = QPushButton("Browse...")
        self._project_folder_browse.clicked.connect(self._browse_project_folder)
        self._project_folder_row.addWidget(self._project_folder_browse)
        folder_layout.addRow("Project Folder:", self._project_folder_row)
        folder_group.setLayout(folder_layout)
        layout.addWidget(folder_group)

        current_folder = settings.get("session", {}).get("project_folder", "")
        self._project_folder_edit.setText(current_folder or "")

        layout.addStretch()

        # Dialog buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self.setLayout(layout)

    def _on_accept(self) -> None:
        self._result_settings = {
            "app": {
                "theme_mode": self._theme_combo.currentData() or "off",
            },
            "project_folder": self._project_folder_edit.text().strip(),
        }
        self.accept()

    def _browse_project_folder(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        path = QFileDialog.getExistingDirectory(self, "Select Project Folder")
        if path:
            self._project_folder_edit.setText(path)

    @property
    def result_settings(self) -> dict:
        return self._result_settings
