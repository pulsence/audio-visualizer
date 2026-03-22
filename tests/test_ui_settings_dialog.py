"""Tests for audio_visualizer.ui.settingsDialog module."""

import pytest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from audio_visualizer.ui.settingsDialog import (
    SettingsDialog,
    _THEME_OPTIONS,
    _ModelActionWorker,
)


# ------------------------------------------------------------------
# SettingsDialog construction
# ------------------------------------------------------------------


class TestSettingsDialogCreation:
    def test_dialog_creates(self):
        """SettingsDialog instantiates without error."""
        dialog = SettingsDialog({"app": {"theme_mode": "off"}})
        assert dialog is not None
        assert dialog.windowTitle() == "Settings"

    def test_dialog_minimum_width(self):
        dialog = SettingsDialog({})
        assert dialog.minimumWidth() >= 400

    def test_project_folder_prefills_from_session_settings(self):
        dialog = SettingsDialog({"session": {"project_folder": "/tmp/project"}})
        assert dialog._project_folder_edit.text() == "/tmp/project"


# ------------------------------------------------------------------
# Theme combo defaults
# ------------------------------------------------------------------


class TestSettingsDialogThemeCombo:
    def test_default_theme_is_auto(self):
        dialog = SettingsDialog({})
        assert dialog._theme_combo.currentData() == "auto"

    def test_respects_current_setting_on(self):
        dialog = SettingsDialog({"app": {"theme_mode": "on"}})
        assert dialog._theme_combo.currentData() == "on"

    def test_respects_current_setting_auto(self):
        dialog = SettingsDialog({"app": {"theme_mode": "auto"}})
        assert dialog._theme_combo.currentData() == "auto"

    def test_combo_has_all_options(self):
        dialog = SettingsDialog({})
        count = dialog._theme_combo.count()
        assert count == len(_THEME_OPTIONS)
        for i, (value, label) in enumerate(_THEME_OPTIONS):
            assert dialog._theme_combo.itemData(i) == value
            assert dialog._theme_combo.itemText(i) == label


# ------------------------------------------------------------------
# Accept semantics
# ------------------------------------------------------------------


class TestSettingsDialogAccept:
    def test_result_empty_before_accept(self):
        dialog = SettingsDialog({})
        assert dialog.result_settings == {}

    def test_on_accept_populates_result(self):
        dialog = SettingsDialog({"app": {"theme_mode": "on"}})
        # Simulate the accept path directly
        dialog._on_accept()
        result = dialog.result_settings
        assert "app" in result
        assert result["app"]["theme_mode"] == "on"

    def test_on_accept_with_changed_selection(self):
        dialog = SettingsDialog({"app": {"theme_mode": "off"}})
        # Change to "auto"
        for i in range(dialog._theme_combo.count()):
            if dialog._theme_combo.itemData(i) == "auto":
                dialog._theme_combo.setCurrentIndex(i)
                break
        dialog._on_accept()
        assert dialog.result_settings["app"]["theme_mode"] == "auto"

    def test_on_accept_includes_project_folder(self):
        dialog = SettingsDialog({})
        dialog._project_folder_edit.setText("/tmp/project")
        dialog._on_accept()
        assert dialog.result_settings["project_folder"] == "/tmp/project"


# ------------------------------------------------------------------
# Whisper model management section
# ------------------------------------------------------------------


class TestSettingsDialogModelManagement:
    def test_model_table_exists(self):
        """The dialog should have a model management table."""
        dialog = SettingsDialog({})
        assert hasattr(dialog, "_model_table")
        assert dialog._model_table.columnCount() == 4

    def test_model_table_headers(self):
        dialog = SettingsDialog({})
        headers = []
        for col in range(dialog._model_table.columnCount()):
            item = dialog._model_table.horizontalHeaderItem(col)
            headers.append(item.text() if item else "")
        assert headers == ["Model", "Size", "Status", "Action"]

    def test_model_refresh_button_exists(self):
        dialog = SettingsDialog({})
        assert hasattr(dialog, "_model_refresh_btn")
        assert dialog._model_refresh_btn.text() == "Refresh"

    def test_model_progress_hidden_initially(self):
        dialog = SettingsDialog({})
        assert dialog._model_progress.isVisible() is False

    @patch("audio_visualizer.ui.settingsDialog._ModelActionWorker")
    def test_set_model_actions_enabled(self, _mock_worker):
        dialog = SettingsDialog({})
        # Disable all action buttons
        dialog._set_model_actions_enabled(False)
        assert dialog._model_refresh_btn.isEnabled() is False
        # Re-enable
        dialog._set_model_actions_enabled(True)
        assert dialog._model_refresh_btn.isEnabled() is True


class TestModelActionWorker:
    @patch("audio_visualizer.srt.modelManagement.download_model")
    def test_download_worker_emits_completed(self, mock_download):
        mock_download.return_value = "/tmp/models/small"
        worker = _ModelActionWorker("download", "small")

        completed_msgs = []
        worker.signals.completed.connect(lambda msg: completed_msgs.append(msg))

        worker.run()

        assert len(completed_msgs) == 1
        assert "Downloaded" in completed_msgs[0]
        assert "small" in completed_msgs[0]

    @patch("audio_visualizer.srt.modelManagement.download_model")
    def test_download_worker_emits_failed_on_error(self, mock_download):
        mock_download.side_effect = RuntimeError("Network error")
        worker = _ModelActionWorker("download", "small")

        failed_msgs = []
        worker.signals.failed.connect(lambda msg: failed_msgs.append(msg))

        worker.run()

        assert len(failed_msgs) == 1
        assert "Network error" in failed_msgs[0]

    @patch("audio_visualizer.srt.modelManagement.delete_model")
    def test_delete_worker_emits_completed(self, mock_delete):
        mock_delete.return_value = "/tmp/models/small"
        worker = _ModelActionWorker("delete", "small")

        completed_msgs = []
        worker.signals.completed.connect(lambda msg: completed_msgs.append(msg))

        worker.run()

        assert len(completed_msgs) == 1
        assert "Deleted" in completed_msgs[0]
        assert "small" in completed_msgs[0]


class TestModelManagementHelpers:
    def test_get_model_size_label_known(self):
        from audio_visualizer.srt.modelManagement import get_model_size_label

        label = get_model_size_label("small")
        assert "244M" in label

    def test_get_model_size_label_unknown(self):
        from audio_visualizer.srt.modelManagement import get_model_size_label

        label = get_model_size_label("nonexistent_model")
        assert label == "unknown"

    def test_model_info_dataclass(self):
        from audio_visualizer.srt.modelManagement import ModelInfo

        info = ModelInfo(name="small", size_label="244M params", is_downloaded=True)
        assert info.name == "small"
        assert info.is_downloaded is True
