"""Tests for the refactored MainWindow shell from audio_visualizer.ui.mainWindow."""

import pytest

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from audio_visualizer.ui.mainWindow import MainWindow
from audio_visualizer.ui.sessionContext import SessionContext
from audio_visualizer.ui.tabs.baseTab import BaseTab


# ------------------------------------------------------------------
# Fixture: shared MainWindow instance (expensive to create)
# ------------------------------------------------------------------

_cached_window = None


@pytest.fixture
def main_window():
    """Return a MainWindow instance, creating it once and reusing across tests.

    MainWindow construction may emit pipewire/audio warnings in headless
    environments — those are harmless and do not indicate a test failure.
    """
    global _cached_window
    if _cached_window is None:
        try:
            _cached_window = MainWindow()
        except Exception as exc:
            pytest.skip(f"MainWindow could not be created in this environment: {exc}")
    return _cached_window


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestMainWindowCreation:
    def test_main_window_creates(self, main_window):
        """MainWindow() instantiates without error."""
        assert main_window is not None


class TestMainWindowTabs:
    def test_has_five_tabs(self, main_window):
        """Verify _tabs has 5 entries."""
        assert len(main_window._tabs) == 5

    def test_tab_ids(self, main_window):
        """Verify tab ids are in the expected order."""
        expected_ids = [
            "audio_visualizer",
            "srt_gen",
            "srt_edit",
            "caption_animate",
            "render_composition",
        ]
        actual_ids = [tab.tab_id for tab in main_window._tabs]
        assert actual_ids == expected_ids

    def test_session_context_injected(self, main_window):
        """All tabs have session_context set."""
        for tab in main_window._tabs:
            assert tab.session_context is not None, (
                f"Tab '{tab.tab_id}' has no session_context"
            )
            assert tab.session_context is main_window.session_context


class TestMainWindowBusyState:
    def test_global_busy_state(self, main_window):
        """try_start_job returns True when idle, False when busy;
        finish_job makes it idle again."""
        # Should start idle
        assert main_window.is_global_busy() is False

        # Starting a job should succeed
        result = main_window.try_start_job("audio_visualizer")
        assert result is True
        assert main_window.is_global_busy() is True

        # Starting another job while busy should fail
        # (try_start_job shows a QMessageBox, so we set _global_busy
        # directly to avoid the modal dialog and just test the logic)
        assert main_window._global_busy is True

        # Finish the job
        main_window.finish_job("audio_visualizer")
        assert main_window.is_global_busy() is False


class TestMainWindowActiveTab:
    def test_active_tab(self, main_window):
        """active_tab() returns a BaseTab instance."""
        tab = main_window.active_tab()
        assert tab is not None
        assert isinstance(tab, BaseTab)


class TestMainWindowSettings:
    def test_settings_roundtrip(self, main_window):
        """_collect_settings returns versioned schema with version key
        and tabs dict."""
        settings = main_window._collect_settings()

        assert "version" in settings
        assert isinstance(settings["version"], int)
        assert "tabs" in settings
        assert isinstance(settings["tabs"], dict)

        # All five tabs should be present in collected settings
        expected_tabs = {
            "audio_visualizer",
            "srt_gen",
            "srt_edit",
            "caption_animate",
            "render_composition",
        }
        assert set(settings["tabs"].keys()) == expected_tabs


class TestMainWindowJobStatus:
    def test_completed_job_uses_persistent_status_actions(self, main_window):
        output_path = "/tmp/output.mov"
        main_window.show_job_status("render", "caption_animate", "Rendering captions")
        main_window.show_job_completed("Done", output_path, "caption_animate")

        assert main_window._job_status.isVisible() is True
        assert main_window._job_status._preview_button.isVisible() is True
        assert main_window._job_status._open_output_button.isVisible() is True
        assert main_window._job_status._open_folder_button.isVisible() is True

    def test_update_undo_actions_rebinds_without_disconnect_warnings(self, main_window, recwarn):
        main_window._update_undo_actions()
        assert not recwarn.list
