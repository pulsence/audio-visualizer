"""Widget-level tests for SrtEditTab session integration and undo scoping."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from audio_visualizer.ui.workspaceContext import SessionAsset, WorkspaceContext
from audio_visualizer.ui.tabs.srtEdit.commands import (
    EditSpeakerCommand,
    EditTextCommand,
    EditTimestampCommand,
)
from audio_visualizer.ui.tabs.srtEdit.document import SubtitleDocument, SubtitleEntry
from audio_visualizer.ui.tabs.srtEdit.tableModel import (
    COL_END,
    COL_SPEAKER,
    COL_START,
    COL_TEXT,
    SubtitleTableModel,
)
from audio_visualizer.ui.tabs.srtEditTab import SrtEditTab


class TestSrtEditTabSessionIntegration:
    def test_selecting_session_audio_loads_the_asset(self, monkeypatch):
        tab = SrtEditTab()
        ctx = WorkspaceContext()
        tab.set_workspace_context(ctx)

        audio_path = Path("/tmp/session-audio.wav")
        ctx.register_asset(
            SessionAsset(
                id="audio1",
                display_name="Session Audio",
                path=audio_path,
                category="audio",
            )
        )

        monkeypatch.setattr(
            tab,
            "_load_waveform_data",
            lambda path: (np.array([0.0, 0.25, 0.0]), 44100),
        )

        tab._audio_combo.setCurrentIndex(1)
        assert tab._audio_path == str(audio_path)

    def test_waveform_loading_reuses_session_cache(self, monkeypatch):
        tab = SrtEditTab()
        ctx = WorkspaceContext()
        tab.set_workspace_context(ctx)

        audio_path = Path("/tmp/cached-audio.wav")
        ctx.register_asset(
            SessionAsset(
                id="audio1",
                display_name="Cached Audio",
                path=audio_path,
                category="audio",
            )
        )

        calls = {"count": 0}

        def fake_load(_path, sr=None, mono=True):
            calls["count"] += 1
            return np.array([0.0, 0.5, 0.0]), 44100

        import librosa

        monkeypatch.setattr(librosa, "load", fake_load)
        first = tab._load_waveform_data(str(audio_path))
        second = tab._load_waveform_data(str(audio_path))

        assert calls["count"] == 1
        assert np.array_equal(first[0], second[0])
        assert first[1] == second[1] == 44100

    def test_save_registers_subtitle_asset(self, tmp_path):
        tab = SrtEditTab()
        ctx = WorkspaceContext()
        tab.set_workspace_context(ctx)

        output_path = tmp_path / "edited.srt"
        tab._subtitle_path = str(output_path)
        tab._document._entries = [
            SubtitleEntry(index=1, start_ms=0, end_ms=1000, text="Hello world")
        ]

        tab._on_save()

        assets = ctx.list_assets(category="subtitle")
        assert len(assets) == 1
        assert assets[0].path == output_path
        assert assets[0].source_tab == "srt_edit"
        assert assets[0].role == "subtitle_source"


class TestInlineEditUndoRedo:
    """Tests that inline table edits go through the undo stack."""

    def _make_tab_with_entries(self):
        """Create an SrtEditTab with two subtitle entries."""
        tab = SrtEditTab()
        tab._document._entries = [
            SubtitleEntry(index=1, start_ms=0, end_ms=2000, text="Hello"),
            SubtitleEntry(index=2, start_ms=3000, end_ms=5000, text="World"),
        ]
        tab._table_model.refresh()
        return tab

    def test_inline_text_edit_pushes_undo_command(self):
        tab = self._make_tab_with_entries()
        assert tab._undo_stack.count() == 0

        tab._on_inline_edit(0, COL_TEXT, "Changed text")

        assert tab._document.entries[0].text == "Changed text"
        assert tab._undo_stack.count() == 1

    def test_inline_text_edit_undo(self):
        tab = self._make_tab_with_entries()
        tab._on_inline_edit(0, COL_TEXT, "Changed text")

        tab._undo_stack.undo()

        assert tab._document.entries[0].text == "Hello"

    def test_inline_text_edit_redo(self):
        tab = self._make_tab_with_entries()
        tab._on_inline_edit(0, COL_TEXT, "Changed text")
        tab._undo_stack.undo()

        tab._undo_stack.redo()

        assert tab._document.entries[0].text == "Changed text"

    def test_inline_start_timestamp_edit_pushes_command(self):
        tab = self._make_tab_with_entries()
        tab._on_inline_edit(0, COL_START, 500)

        assert tab._document.entries[0].start_ms == 500
        assert tab._undo_stack.count() == 1

        tab._undo_stack.undo()
        assert tab._document.entries[0].start_ms == 0

    def test_inline_end_timestamp_edit_pushes_command(self):
        tab = self._make_tab_with_entries()
        tab._on_inline_edit(0, COL_END, 2500)

        assert tab._document.entries[0].end_ms == 2500
        assert tab._undo_stack.count() == 1

        tab._undo_stack.undo()
        assert tab._document.entries[0].end_ms == 2000

    def test_inline_speaker_edit_pushes_command(self):
        tab = self._make_tab_with_entries()
        tab._on_inline_edit(0, COL_SPEAKER, "Alice")

        assert tab._document.entries[0].speaker == "Alice"
        assert tab._undo_stack.count() == 1

        tab._undo_stack.undo()
        assert tab._document.entries[0].speaker is None

    def test_setdata_emits_inline_edit_signal(self):
        doc = SubtitleDocument()
        doc._entries = [
            SubtitleEntry(index=1, start_ms=0, end_ms=2000, text="Hello"),
        ]
        model = SubtitleTableModel(doc)

        received = []
        model.inline_edit_requested.connect(
            lambda row, col, val: received.append((row, col, val))
        )

        index = model.index(0, COL_TEXT)
        result = model.setData(index, "New text", Qt.ItemDataRole.EditRole)

        assert result is True
        assert len(received) == 1
        assert received[0] == (0, COL_TEXT, "New text")
        # Document should NOT have been mutated directly
        assert doc.entries[0].text == "Hello"

    def test_setdata_emits_signal_for_speaker(self):
        doc = SubtitleDocument()
        doc._entries = [
            SubtitleEntry(index=1, start_ms=0, end_ms=2000, text="Hello"),
        ]
        model = SubtitleTableModel(doc)

        received = []
        model.inline_edit_requested.connect(
            lambda row, col, val: received.append((row, col, val))
        )

        index = model.index(0, COL_SPEAKER)
        model.setData(index, "Bob", Qt.ItemDataRole.EditRole)

        assert len(received) == 1
        assert received[0] == (0, COL_SPEAKER, "Bob")


class TestEditSpeakerCommand:
    """Tests for the EditSpeakerCommand undo command."""

    def test_redo_changes_speaker(self):
        doc = SubtitleDocument()
        doc._entries = [
            SubtitleEntry(index=1, start_ms=0, end_ms=2000, text="Hello"),
        ]

        cmd = EditSpeakerCommand(doc, 0, "Alice")
        cmd.redo()

        assert doc.entries[0].speaker == "Alice"

    def test_undo_restores_speaker(self):
        doc = SubtitleDocument()
        doc._entries = [
            SubtitleEntry(index=1, start_ms=0, end_ms=2000, text="Hello", speaker="Bob"),
        ]

        cmd = EditSpeakerCommand(doc, 0, "Alice")
        cmd.redo()
        assert doc.entries[0].speaker == "Alice"

        cmd.undo()
        assert doc.entries[0].speaker == "Bob"

    def test_undo_restores_none_speaker(self):
        doc = SubtitleDocument()
        doc._entries = [
            SubtitleEntry(index=1, start_ms=0, end_ms=2000, text="Hello"),
        ]

        cmd = EditSpeakerCommand(doc, 0, "Alice")
        cmd.redo()
        cmd.undo()

        assert doc.entries[0].speaker is None
