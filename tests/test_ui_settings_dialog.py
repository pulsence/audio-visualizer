"""Tests for audio_visualizer.ui.settingsDialog module."""

import pytest

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from audio_visualizer.ui.settingsDialog import SettingsDialog, _THEME_OPTIONS


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


# ------------------------------------------------------------------
# Theme combo defaults
# ------------------------------------------------------------------


class TestSettingsDialogThemeCombo:
    def test_default_theme_is_off(self):
        dialog = SettingsDialog({})
        assert dialog._theme_combo.currentData() == "off"

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
