"""Widget-level tests for SrtEditTab session integration and undo scoping."""

from __future__ import annotations

import json
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
    EditWordTextCommand,
    EditWordTimingCommand,
)
from audio_visualizer.ui.tabs.srtEdit.document import SubtitleDocument, SubtitleEntry
from audio_visualizer.ui.tabs.srtEdit.tableModel import (
    COL_END,
    COL_INDEX,
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

    def test_save_bundle_registers_bundle_asset(self, tmp_path):
        tab = SrtEditTab()
        ctx = WorkspaceContext()
        tab.set_workspace_context(ctx)

        output_path = tmp_path / "edited.bundle.json"
        tab._bundle_path = str(output_path)
        tab._document._entries = [
            SubtitleEntry(index=1, start_ms=0, end_ms=1000, text="Hello world", id="s1")
        ]

        tab._on_save_bundle()

        assets = ctx.list_assets(category="json_bundle")
        assert len(assets) == 1
        assert assets[0].path == output_path
        assert assets[0].source_tab == "srt_edit"
        assert assets[0].role == "bundle_source"

    def test_load_bundle_file(self, tmp_path):
        """Loading a .json bundle populates words and provenance."""
        bundle = {
            "bundle_version": 2,
            "subtitles": [
                {
                    "id": "sub1",
                    "start": 1.0,
                    "end": 3.0,
                    "text": "Hello world",
                    "original_text": "Hello world",
                    "words": [
                        {"id": "w1", "subtitle_id": "sub1", "text": "Hello", "start": 1.0, "end": 2.0},
                        {"id": "w2", "subtitle_id": "sub1", "text": "world", "start": 2.0, "end": 3.0},
                    ],
                    "source_media_path": "test.wav",
                    "model_name": "tiny",
                },
            ],
            "words": [],
        }
        path = tmp_path / "test.bundle.json"
        path.write_text(json.dumps(bundle), encoding="utf-8")

        tab = SrtEditTab()
        tab._load_subtitle(str(path))

        assert len(tab._document.entries) == 1
        assert tab._document.entries[0].id == "sub1"
        assert len(tab._document.entries[0].words) == 2
        assert tab._bundle_path == str(path)

    def test_bundle_assets_appear_in_subtitle_combo(self):
        """json_bundle assets should appear in the subtitle combo."""
        tab = SrtEditTab()
        ctx = WorkspaceContext()
        tab.set_workspace_context(ctx)

        ctx.register_asset(
            SessionAsset(
                id="bundle1",
                display_name="My Bundle",
                path=Path("/tmp/test.bundle.json"),
                category="json_bundle",
            )
        )

        # Check combo has the bundle item
        combo_texts = [tab._subtitle_combo.itemText(i) for i in range(tab._subtitle_combo.count())]
        assert any("Bundle" in t for t in combo_texts)


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


class TestWaveformBackgroundLoading:
    def test_load_audio_launches_worker(self, monkeypatch):
        """_load_audio should increment request id and show loading message."""
        tab = SrtEditTab()
        monkeypatch.setattr(
            tab,
            "_load_waveform_data",
            lambda path: (np.array([0.0, 0.5, 0.0]), 44100),
        )
        assert tab._waveform_request_id == 0
        tab._load_audio("/tmp/test.wav")
        assert tab._waveform_request_id == 1

    def test_stale_waveform_completion_ignored(self):
        """Stale waveform completions (old request_id) should be ignored."""
        tab = SrtEditTab()
        # Manually set request_id to 2 (simulating two rapid loads)
        tab._waveform_request_id = 2
        tab._waveform_view.set_loading_message("Loading waveform...")

        load_calls = []
        original_load = tab._waveform_view.load_waveform
        tab._waveform_view.load_waveform = lambda s, sr: load_calls.append((s, sr))

        # Simulate stale completion from request 1 — should be ignored
        tab._on_waveform_loaded(np.array([0.0]), 44100, 1)
        assert len(load_calls) == 0

        # Now complete with the current request — should load
        tab._on_waveform_loaded(np.array([0.0, 0.5]), 44100, 2)
        assert len(load_calls) == 1

    def test_waveform_mutation_on_ui_thread(self, monkeypatch):
        """load_waveform must be called from _on_waveform_loaded, not the worker."""
        tab = SrtEditTab()
        monkeypatch.setattr(
            tab,
            "_load_waveform_data",
            lambda path: (np.array([0.0, 0.5, 0.0]), 44100),
        )
        tab._load_audio("/tmp/test.wav")

        load_calls = []
        original_load = tab._waveform_view.load_waveform
        tab._waveform_view.load_waveform = lambda s, sr: load_calls.append((s, sr))

        tab._on_waveform_loaded(np.array([0.0, 0.5]), 44100, tab._waveform_request_id)
        assert len(load_calls) == 1


class TestTableModelRowMapping:
    """Test the row mapping for expand/collapse word rows."""

    def _make_model_with_words(self):
        from audio_visualizer.srt.models import WordItem
        doc = SubtitleDocument()
        words = [
            WordItem(start=1.0, end=1.5, text="Hello", id="w1", subtitle_id="s1"),
            WordItem(start=1.5, end=2.0, text="world", id="w2", subtitle_id="s1"),
        ]
        doc._entries = [
            SubtitleEntry(
                index=1, start_ms=1000, end_ms=3000, text="Hello world",
                id="s1", words=words,
            ),
            SubtitleEntry(
                index=2, start_ms=4000, end_ms=6000, text="Second entry",
            ),
        ]
        model = SubtitleTableModel(doc)
        return model, doc

    def test_collapsed_row_count(self):
        model, doc = self._make_model_with_words()
        assert model.rowCount() == 2

    def test_expanded_row_count(self):
        model, doc = self._make_model_with_words()
        model.toggle_expand(0)
        # 1 subtitle + 2 words + 1 subtitle = 4
        assert model.rowCount() == 4

    def test_collapse_reduces_row_count(self):
        model, doc = self._make_model_with_words()
        model.toggle_expand(0)
        assert model.rowCount() == 4
        model.toggle_expand(0)
        assert model.rowCount() == 2

    def test_word_row_data(self):
        model, doc = self._make_model_with_words()
        model.toggle_expand(0)

        # Row 0: subtitle entry
        idx = model.index(0, COL_TEXT)
        assert "Hello world" in str(model.data(idx))

        # Row 1: first word
        idx = model.index(1, COL_TEXT)
        text = model.data(idx)
        assert "Hello" in text

        # Row 2: second word
        idx = model.index(2, COL_TEXT)
        text = model.data(idx)
        assert "world" in text

    def test_entry_index_for_row(self):
        model, doc = self._make_model_with_words()
        model.toggle_expand(0)

        assert model.entry_index_for_row(0) == 0  # subtitle
        assert model.entry_index_for_row(1) == 0  # word of entry 0
        assert model.entry_index_for_row(2) == 0  # word of entry 0
        assert model.entry_index_for_row(3) == 1  # second subtitle

    def test_word_row_for(self):
        model, doc = self._make_model_with_words()
        model.toggle_expand(0)

        assert model.word_row_for(0, 0) == 1
        assert model.word_row_for(0, 1) == 2
        assert model.word_row_for(0, 2) == -1  # doesn't exist

    def test_subtitle_row_for_entry(self):
        model, doc = self._make_model_with_words()
        model.toggle_expand(0)

        assert model.subtitle_row_for_entry(0) == 0
        assert model.subtitle_row_for_entry(1) == 3

    def test_expand_entry_without_words_is_noop(self):
        model, doc = self._make_model_with_words()
        model.toggle_expand(1)  # Second entry has no words
        assert model.rowCount() == 2  # No change

    def test_index_column_shows_expand_indicator(self):
        model, doc = self._make_model_with_words()

        # Collapsed: should show +
        idx = model.index(0, COL_INDEX)
        text = str(model.data(idx))
        assert "+" in text

        model.toggle_expand(0)
        # Expanded: should show -
        idx = model.index(0, COL_INDEX)
        text = str(model.data(idx))
        assert "-" in text

    def test_word_row_setdata_emits_word_edit_signal(self):
        model, doc = self._make_model_with_words()
        model.toggle_expand(0)

        received = []
        model.word_edit_requested.connect(
            lambda ei, wi, col, val: received.append((ei, wi, col, val))
        )

        # Edit word text (row 1 = first word)
        idx = model.index(1, COL_TEXT)
        result = model.setData(idx, "Hi", Qt.ItemDataRole.EditRole)

        assert result is True
        assert len(received) == 1
        assert received[0][0] == 0  # entry_index
        assert received[0][1] == 0  # word_index
        assert received[0][2] == COL_TEXT
        assert received[0][3] == "Hi"


class TestWordEditCommands:
    """Test word-level undo commands."""

    def _make_doc_with_words(self):
        from audio_visualizer.srt.models import WordItem
        doc = SubtitleDocument()
        words = [
            WordItem(start=1.0, end=1.5, text="Hello", id="w1", subtitle_id="s1"),
            WordItem(start=1.5, end=2.0, text="world", id="w2", subtitle_id="s1"),
        ]
        doc._entries = [
            SubtitleEntry(
                index=1, start_ms=1000, end_ms=3000, text="Hello world",
                id="s1", words=words,
            ),
        ]
        return doc

    def test_edit_word_text_undo_redo(self):
        doc = self._make_doc_with_words()
        cmd = EditWordTextCommand(doc, 0, 0, "Hi")
        cmd.redo()
        assert doc.entries[0].words[0].text == "Hi"
        cmd.undo()
        assert doc.entries[0].words[0].text == "Hello"
        cmd.redo()
        assert doc.entries[0].words[0].text == "Hi"

    def test_edit_word_timing_undo_redo(self):
        doc = self._make_doc_with_words()
        cmd = EditWordTimingCommand(doc, 0, 0, new_start=1.1, new_end=1.4)
        cmd.redo()
        assert doc.entries[0].words[0].start == 1.1
        assert doc.entries[0].words[0].end == 1.4
        cmd.undo()
        assert doc.entries[0].words[0].start == 1.0
        assert doc.entries[0].words[0].end == 1.5

    def test_word_edit_through_tab(self):
        """Word inline edits go through the undo stack."""
        from audio_visualizer.srt.models import WordItem
        tab = SrtEditTab()
        words = [
            WordItem(start=1.0, end=1.5, text="Hello", id="w1", subtitle_id="s1"),
        ]
        tab._document._entries = [
            SubtitleEntry(
                index=1, start_ms=1000, end_ms=3000, text="Hello",
                id="s1", words=words,
            ),
        ]
        tab._table_model.refresh()

        tab._on_word_inline_edit(0, 0, COL_TEXT, "Hi")

        assert tab._document.entries[0].words[0].text == "Hi"
        assert tab._undo_stack.count() == 1

        tab._undo_stack.undo()
        assert tab._document.entries[0].words[0].text == "Hello"


class TestContextActions:
    """Test context menu action routing."""

    def _make_tab(self):
        tab = SrtEditTab()
        tab._document._entries = [
            SubtitleEntry(index=1, start_ms=0, end_ms=2000, text="Hello"),
            SubtitleEntry(index=2, start_ms=3000, end_ms=5000, text="World"),
            SubtitleEntry(index=3, start_ms=6000, end_ms=8000, text="Test"),
        ]
        tab._table_model.refresh()
        return tab

    def test_context_delete(self):
        tab = self._make_tab()
        tab._on_context_action("delete", 1)
        assert len(tab._document.entries) == 2
        assert tab._undo_stack.count() == 1

    def test_context_merge_next(self):
        tab = self._make_tab()
        tab._on_context_action("merge_next", 0)
        assert len(tab._document.entries) == 2
        assert "Hello World" in tab._document.entries[0].text or \
               "Hello" in tab._document.entries[0].text

    def test_context_merge_prev(self):
        tab = self._make_tab()
        tab._on_context_action("merge_prev", 1)
        assert len(tab._document.entries) == 2

    def test_context_split_at_playhead_uses_midpoint(self):
        tab = self._make_tab()
        tab._on_context_action("split_at_playhead", 0)
        assert len(tab._document.entries) == 4

    def test_drag_select_create(self):
        tab = self._make_tab()
        original_count = len(tab._document.entries)
        tab._on_drag_select_create(9.0, 10.0)
        assert len(tab._document.entries) == original_count + 1
        # New entry should be sorted into position
        new_entry = tab._document.entries[-1]
        assert new_entry.start_ms == 9000
        assert new_entry.end_ms == 10000


class TestParserBundleDetection:
    """Test bundle file detection in parser module."""

    def test_json_extension_detected(self):
        from audio_visualizer.ui.tabs.srtEdit.parser import is_bundle_file
        assert is_bundle_file("/path/to/file.json") is True

    def test_bundle_json_extension_detected(self):
        from audio_visualizer.ui.tabs.srtEdit.parser import is_bundle_file
        assert is_bundle_file("/path/to/file.bundle.json") is True

    def test_srt_not_detected(self):
        from audio_visualizer.ui.tabs.srtEdit.parser import is_bundle_file
        assert is_bundle_file("/path/to/file.srt") is False

    def test_ass_not_detected(self):
        from audio_visualizer.ui.tabs.srtEdit.parser import is_bundle_file
        assert is_bundle_file("/path/to/file.ass") is False


class TestMarkdownHighlighter:
    """Tests for the MarkdownHighlighter syntax highlighter."""

    def _highlight(self, text: str):
        """Return a list of (start, length, format_name) tuples applied to *text*."""
        from PySide6.QtGui import QTextDocument
        from audio_visualizer.ui.tabs.srtEdit.markdownHighlighter import MarkdownHighlighter

        doc = QTextDocument()
        doc.setPlainText(text)
        highlighter = MarkdownHighlighter(doc)
        # Force re-highlight
        highlighter.rehighlight()
        return highlighter

    def test_bold_is_highlighted(self):
        from PySide6.QtGui import QFont, QTextDocument
        from audio_visualizer.ui.tabs.srtEdit.markdownHighlighter import MarkdownHighlighter

        doc = QTextDocument()
        doc.setPlainText("hello **bold** world")
        hl = MarkdownHighlighter(doc)
        hl.rehighlight()

        block = doc.firstBlock()
        layout = block.layout()
        formats = layout.formats()
        # Should have formatting applied (delimiter + content spans)
        assert len(formats) > 0
        # Verify bold content has bold weight
        bold_found = False
        for fmt_range in formats:
            if fmt_range.format.fontWeight() == QFont.Weight.Bold:
                bold_found = True
                break
        assert bold_found, "Expected bold formatting to be applied"

    def test_italic_is_highlighted(self):
        from PySide6.QtGui import QTextDocument
        from audio_visualizer.ui.tabs.srtEdit.markdownHighlighter import MarkdownHighlighter

        doc = QTextDocument()
        doc.setPlainText("hello *italic* world")
        hl = MarkdownHighlighter(doc)
        hl.rehighlight()

        block = doc.firstBlock()
        formats = block.layout().formats()
        assert len(formats) > 0
        italic_found = any(fr.format.fontItalic() for fr in formats)
        assert italic_found, "Expected italic formatting to be applied"

    def test_highlight_marker_is_highlighted(self):
        from PySide6.QtGui import QTextDocument
        from audio_visualizer.ui.tabs.srtEdit.markdownHighlighter import MarkdownHighlighter

        doc = QTextDocument()
        doc.setPlainText("hello ==highlight== world")
        hl = MarkdownHighlighter(doc)
        hl.rehighlight()

        block = doc.firstBlock()
        formats = block.layout().formats()
        assert len(formats) > 0
        # The highlight format uses a background colour
        bg_found = any(fr.format.background().color().alpha() > 0 for fr in formats)
        assert bg_found, "Expected highlight background to be applied"

    def test_no_markdown_produces_no_formats(self):
        from PySide6.QtGui import QTextDocument
        from audio_visualizer.ui.tabs.srtEdit.markdownHighlighter import MarkdownHighlighter

        doc = QTextDocument()
        doc.setPlainText("plain text without markdown")
        hl = MarkdownHighlighter(doc)
        hl.rehighlight()

        block = doc.firstBlock()
        formats = block.layout().formats()
        assert len(formats) == 0

    def test_bold_does_not_trigger_italic(self):
        """Bold delimiters (**) should not be interpreted as two italics."""
        from PySide6.QtGui import QFont, QTextDocument
        from audio_visualizer.ui.tabs.srtEdit.markdownHighlighter import MarkdownHighlighter

        doc = QTextDocument()
        doc.setPlainText("**only bold**")
        hl = MarkdownHighlighter(doc)
        hl.rehighlight()

        block = doc.firstBlock()
        formats = block.layout().formats()
        italic_found = any(
            fr.format.fontItalic() and fr.format.fontWeight() != QFont.Weight.Bold
            for fr in formats
        )
        assert not italic_found, "Bold-only text should not trigger italic"

    def test_mixed_bold_and_italic(self):
        from PySide6.QtGui import QFont, QTextDocument
        from audio_visualizer.ui.tabs.srtEdit.markdownHighlighter import MarkdownHighlighter

        doc = QTextDocument()
        doc.setPlainText("**bold** and *italic*")
        hl = MarkdownHighlighter(doc)
        hl.rehighlight()

        block = doc.firstBlock()
        formats = block.layout().formats()
        bold_found = any(fr.format.fontWeight() == QFont.Weight.Bold for fr in formats)
        italic_found = any(fr.format.fontItalic() for fr in formats)
        assert bold_found
        assert italic_found

    def test_multiline_text_delegate_attaches_highlighter(self):
        """MultilineTextDelegate.createEditor should attach a MarkdownHighlighter."""
        from audio_visualizer.ui.tabs.srtEdit.tableModel import MultilineTextDelegate
        from audio_visualizer.ui.tabs.srtEdit.markdownHighlighter import MarkdownHighlighter
        from PySide6.QtWidgets import QWidget, QStyleOptionViewItem
        from PySide6.QtCore import QModelIndex

        delegate = MultilineTextDelegate()
        parent = QWidget()
        option = QStyleOptionViewItem()
        index = QModelIndex()
        editor = delegate.createEditor(parent, option, index)

        # The editor's document should have a MarkdownHighlighter child
        found = False
        for child in editor.document().children():
            if isinstance(child, MarkdownHighlighter):
                found = True
                break
        assert found, "Expected MarkdownHighlighter attached to editor document"


class TestSidebarEditorSync:
    """Tests for the sidebar segment text editor synchronization."""

    def _make_tab_with_entries(self):
        """Create an SrtEditTab with two subtitle entries."""
        tab = SrtEditTab()
        tab._document._entries = [
            SubtitleEntry(index=1, start_ms=0, end_ms=2000, text="Hello"),
            SubtitleEntry(index=2, start_ms=3000, end_ms=5000, text="World"),
        ]
        tab._table_model.refresh()
        return tab

    def test_sidebar_editor_exists(self):
        """The sidebar should contain a QPlainTextEdit for segment editing."""
        tab = SrtEditTab()
        assert hasattr(tab, "_sidebar_editor")
        from PySide6.QtWidgets import QPlainTextEdit
        assert isinstance(tab._sidebar_editor, QPlainTextEdit)

    def test_sidebar_has_markdown_highlighter(self):
        """The sidebar editor should have a MarkdownHighlighter attached."""
        from audio_visualizer.ui.tabs.srtEdit.markdownHighlighter import MarkdownHighlighter
        tab = SrtEditTab()
        assert hasattr(tab, "_sidebar_highlighter")
        assert isinstance(tab._sidebar_highlighter, MarkdownHighlighter)

    def test_sidebar_shows_selected_entry_text(self):
        """Selecting a table row should populate the sidebar editor."""
        tab = self._make_tab_with_entries()
        tab._table_view.selectRow(0)
        assert tab._sidebar_editor.toPlainText() == "Hello"

    def test_sidebar_follows_selection_change(self):
        """Switching selection should update the sidebar text."""
        tab = self._make_tab_with_entries()
        tab._table_view.selectRow(0)
        assert tab._sidebar_editor.toPlainText() == "Hello"
        tab._table_view.selectRow(1)
        assert tab._sidebar_editor.toPlainText() == "World"

    def test_sidebar_edit_pushes_undo_command(self):
        """Editing text in the sidebar should push an undo command."""
        tab = self._make_tab_with_entries()
        tab._table_view.selectRow(0)
        assert tab._undo_stack.count() == 0

        tab._sidebar_editor.setPlainText("Changed via sidebar")

        assert tab._document.entries[0].text == "Changed via sidebar"
        assert tab._undo_stack.count() == 1

    def test_sidebar_edit_undo(self):
        """Undoing a sidebar edit should restore the original text."""
        tab = self._make_tab_with_entries()
        tab._table_view.selectRow(0)
        tab._sidebar_editor.setPlainText("Changed")

        tab._undo_stack.undo()
        assert tab._document.entries[0].text == "Hello"

    def test_no_controls_in_old_toolbar_locations(self):
        """Bottom toolbars should be removed — all controls are in the sidebar."""
        tab = SrtEditTab()
        # _resync_toolbar should no longer exist
        assert not hasattr(tab, "_resync_toolbar")

    def test_sidebar_controls_grouped(self):
        """Verify the sidebar has QGroupBox sections for organized controls."""
        from PySide6.QtWidgets import QGroupBox
        tab = SrtEditTab()
        # Find group boxes in the sidebar area — look through all children
        groups = tab.findChildren(QGroupBox)
        group_titles = {g.title() for g in groups}
        expected = {"Segment Text", "Playback", "Edit", "Save / Export", "Resync", "QA / Lint"}
        assert expected.issubset(group_titles), f"Missing groups: {expected - group_titles}"

    def test_inline_text_edit_syncs_sidebar(self):
        """An inline table text edit should update the sidebar editor."""
        tab = self._make_tab_with_entries()
        tab._table_view.selectRow(0)
        assert tab._sidebar_editor.toPlainText() == "Hello"

        tab._on_inline_edit(0, COL_TEXT, "Inline change")
        assert tab._sidebar_editor.toPlainText() == "Inline change"
