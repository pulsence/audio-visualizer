"""Tests for BaseTab from audio_visualizer.ui.tabs.baseTab."""

from typing import Any

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

import pytest

from audio_visualizer.ui.tabs.baseTab import BaseTab
from audio_visualizer.ui.sessionContext import SessionContext


# ------------------------------------------------------------------
# Concrete stub for the abstract BaseTab
# ------------------------------------------------------------------


class DummyTab(BaseTab):
    """Minimal concrete subclass of BaseTab for testing."""

    TAB_ID = "dummy"
    TAB_TITLE = "Dummy Tab"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings: dict[str, Any] = {"volume": 75, "muted": False}

    @property
    def tab_id(self) -> str:
        return self.TAB_ID

    @property
    def tab_title(self) -> str:
        return self.TAB_TITLE

    def validate_settings(self) -> tuple[bool, str]:
        return (True, "")

    def collect_settings(self) -> dict[str, Any]:
        return dict(self._settings)

    def apply_settings(self, data: dict[str, Any]) -> None:
        self._settings.update(data)


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestBaseTabIdentity:
    def test_tab_id_and_title(self):
        tab = DummyTab()
        assert tab.tab_id == "dummy"
        assert tab.tab_title == "Dummy Tab"


class TestBaseTabSettings:
    def test_validate_settings(self):
        tab = DummyTab()
        valid, msg = tab.validate_settings()
        assert valid is True
        assert msg == ""

    def test_collect_apply_settings(self):
        tab = DummyTab()
        original = tab.collect_settings()
        assert original == {"volume": 75, "muted": False}

        # Modify and apply back
        original["volume"] = 100
        original["muted"] = True
        tab.apply_settings(original)

        restored = tab.collect_settings()
        assert restored["volume"] == 100
        assert restored["muted"] is True


class TestBaseTabSessionContext:
    def test_set_session_context(self):
        tab = DummyTab()
        assert tab.session_context is None

        ctx = SessionContext()
        tab.set_session_context(ctx)
        assert tab.session_context is ctx


class TestBaseTabUndo:
    def test_undo_stack_init(self):
        tab = DummyTab()
        tab._init_undo_stack(limit=50)
        assert tab.has_undo_support is True

    def test_undo_stack_not_init(self):
        tab = DummyTab()
        assert tab.has_undo_support is False

    def test_push_command_without_init_raises(self):
        tab = DummyTab()
        with pytest.raises(RuntimeError, match="Undo stack not initialised"):
            tab._push_command(object())

    def test_clear_undo_without_init_raises(self):
        tab = DummyTab()
        with pytest.raises(RuntimeError, match="Undo stack not initialised"):
            tab._clear_undo_stack()

    def test_undo_redo_actions(self):
        tab = DummyTab()
        tab._init_undo_stack()
        undo = tab.undo_action()
        redo = tab.redo_action()
        assert undo is not None
        assert redo is not None

    def test_undo_redo_actions_without_stack(self):
        tab = DummyTab()
        assert tab.undo_action() is None
        assert tab.redo_action() is None
