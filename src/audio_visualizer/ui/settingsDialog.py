"""Application settings dialog.

Provides a modal dialog with application-level settings such as theme mode
and Whisper model management.  Uses explicit accept/apply semantics --
changes are not persisted until the user confirms.
"""
from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

_THEME_OPTIONS = [
    ("off", "Light"),
    ("on", "Dark"),
    ("auto", "Auto"),
]


class _ModelActionSignals(QObject):
    """Signals emitted by the background model download/delete worker."""

    completed = Signal(str)  # success message
    failed = Signal(str)  # error message
    progress = Signal(str)  # progress message


class _ModelActionWorker(QRunnable):
    """Background worker for model download or delete operations."""

    def __init__(self, action: str, model_name: str) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._action = action
        self._model_name = model_name
        self.signals = _ModelActionSignals()

    def run(self) -> None:
        try:
            if self._action == "download":
                self.signals.progress.emit(f"Downloading '{self._model_name}'...")
                from audio_visualizer.srt.modelManagement import download_model

                path = download_model(self._model_name)
                self.signals.completed.emit(
                    f"Downloaded '{self._model_name}' to {path}"
                )
            elif self._action == "delete":
                from audio_visualizer.srt.modelManagement import delete_model

                path = delete_model(self._model_name)
                self.signals.completed.emit(
                    f"Deleted '{self._model_name}' from {path}"
                )
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class SettingsDialog(QDialog):
    """Modal settings dialog with accept/apply semantics."""

    def __init__(self, current_settings: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(550)
        self._result_settings: dict = {}
        self._thread_pool = QThreadPool()
        self._thread_pool.setMaxThreadCount(1)
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
        current_theme = settings.get("app", {}).get("theme_mode", "auto")
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

        # Whisper Models group
        self._build_model_management_section(layout)

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

    # ------------------------------------------------------------------
    # Whisper Models section
    # ------------------------------------------------------------------

    def _build_model_management_section(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Whisper Models")
        layout = QVBoxLayout()

        # Model table: Name | Size | Status | Action
        self._model_table = QTableWidget()
        self._model_table.setColumnCount(4)
        self._model_table.setHorizontalHeaderLabels(
            ["Model", "Size", "Status", "Action"]
        )
        self._model_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._model_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._model_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._model_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self._model_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self._model_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._model_table.verticalHeader().setVisible(False)
        self._model_table.setMaximumHeight(250)
        layout.addWidget(self._model_table)

        # Refresh + status row
        status_row = QHBoxLayout()
        self._model_refresh_btn = QPushButton("Refresh")
        self._model_refresh_btn.clicked.connect(self._refresh_model_table)
        status_row.addWidget(self._model_refresh_btn)

        self._model_status_label = QLabel("")
        status_row.addWidget(self._model_status_label, 1)

        self._model_progress = QProgressBar()
        self._model_progress.setRange(0, 0)  # indeterminate
        self._model_progress.setVisible(False)
        self._model_progress.setMaximumWidth(200)
        status_row.addWidget(self._model_progress)

        layout.addLayout(status_row)

        group.setLayout(layout)
        parent_layout.addWidget(group)

        # Populate the table
        self._refresh_model_table()

    def _refresh_model_table(self) -> None:
        """Populate the model table with current model info."""
        self._model_table.setRowCount(0)

        try:
            from audio_visualizer.srt.modelManagement import list_models_with_status

            models = list_models_with_status()
        except Exception as exc:
            logger.debug("Could not load model list: %s", exc)
            self._model_status_label.setText(
                "Could not load model list (faster-whisper not available)"
            )
            return

        self._model_table.setRowCount(len(models))
        for row, info in enumerate(models):
            # Name
            name_item = QTableWidgetItem(info.name)
            self._model_table.setItem(row, 0, name_item)

            # Size
            size_item = QTableWidgetItem(info.size_label)
            self._model_table.setItem(row, 1, size_item)

            # Status
            status_text = "Downloaded" if info.is_downloaded else "Not downloaded"
            status_item = QTableWidgetItem(status_text)
            self._model_table.setItem(row, 2, status_item)

            # Action button
            if info.is_downloaded:
                btn = QPushButton("Delete")
                btn.setProperty("model_name", info.name)
                btn.clicked.connect(
                    lambda checked=False, name=info.name: self._on_delete_model(name)
                )
            else:
                btn = QPushButton("Download")
                btn.setProperty("model_name", info.name)
                btn.clicked.connect(
                    lambda checked=False, name=info.name: self._on_download_model(name)
                )
            self._model_table.setCellWidget(row, 3, btn)

        self._model_status_label.setText(
            f"{len(models)} models available"
        )

    def _on_download_model(self, model_name: str) -> None:
        """Start downloading a model in the background."""
        self._set_model_actions_enabled(False)
        self._model_progress.setVisible(True)
        self._model_status_label.setText(f"Downloading '{model_name}'...")

        worker = _ModelActionWorker("download", model_name)
        worker.signals.completed.connect(self._on_model_action_completed)
        worker.signals.failed.connect(self._on_model_action_failed)
        worker.signals.progress.connect(self._on_model_action_progress)
        self._thread_pool.start(worker)

    def _on_delete_model(self, model_name: str) -> None:
        """Delete a model after confirmation."""
        reply = QMessageBox.question(
            self,
            "Delete Model",
            f"Are you sure you want to delete the '{model_name}' model?\n\n"
            "You will need to re-download it to use it again.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._set_model_actions_enabled(False)
        self._model_progress.setVisible(True)
        self._model_status_label.setText(f"Deleting '{model_name}'...")

        worker = _ModelActionWorker("delete", model_name)
        worker.signals.completed.connect(self._on_model_action_completed)
        worker.signals.failed.connect(self._on_model_action_failed)
        self._thread_pool.start(worker)

    def _on_model_action_completed(self, message: str) -> None:
        self._model_progress.setVisible(False)
        self._model_status_label.setText(message)
        self._set_model_actions_enabled(True)
        self._refresh_model_table()

    def _on_model_action_failed(self, error_message: str) -> None:
        self._model_progress.setVisible(False)
        self._model_status_label.setText(f"Error: {error_message}")
        self._set_model_actions_enabled(True)

    def _on_model_action_progress(self, message: str) -> None:
        self._model_status_label.setText(message)

    def _set_model_actions_enabled(self, enabled: bool) -> None:
        """Enable or disable all action buttons in the model table."""
        for row in range(self._model_table.rowCount()):
            widget = self._model_table.cellWidget(row, 3)
            if widget:
                widget.setEnabled(enabled)
        self._model_refresh_btn.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Standard dialog actions
    # ------------------------------------------------------------------

    def _on_accept(self) -> None:
        self._result_settings = {
            "app": {
                "theme_mode": self._theme_combo.currentData() or "auto",
            },
            "project_folder": self._project_folder_edit.text().strip(),
        }
        self.accept()

    def _browse_project_folder(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        from audio_visualizer.ui.sessionFilePicker import resolve_browse_directory

        start_dir = resolve_browse_directory(self._project_folder_edit.text().strip())
        path = QFileDialog.getExistingDirectory(self, "Select Project Folder", start_dir)
        if path:
            self._project_folder_edit.setText(path)

    @property
    def result_settings(self) -> dict:
        return self._result_settings
