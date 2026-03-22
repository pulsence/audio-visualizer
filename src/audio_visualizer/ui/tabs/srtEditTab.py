"""SRT Edit tab — waveform-backed subtitle editor.

Provides a split-pane UI with an audio waveform on top and a subtitle
table below.  Supports undo/redo, QA lint, resync tools, and automatic
correction recording for bundle-backed subtitle entries.
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from audio_visualizer.ui.tabs.baseTab import BaseTab
from audio_visualizer.ui.workspaceContext import SessionAsset
from audio_visualizer.ui.sessionFilePicker import pick_session_or_file
from audio_visualizer.ui.tabs.srtEdit.commands import (
    AddEntryCommand,
    BatchResyncCommand,
    EditSpeakerCommand,
    EditTextCommand,
    EditTimestampCommand,
    EditWordTextCommand,
    EditWordTimingCommand,
    MergeEntriesCommand,
    RemoveEntryCommand,
    SplitEntryCommand,
)
from audio_visualizer.ui.tabs.srtEdit.document import SubtitleDocument, SubtitleEntry
from audio_visualizer.ui.tabs.srtEdit.lint import (
    BUILTIN_PROFILES,
    LintIssue,
    run_lint,
)
from audio_visualizer.ui.tabs.srtEdit.parser import is_bundle_file
from audio_visualizer.ui.tabs.srtEdit.resync import (
    fps_drift_correction,
    global_shift,
    shift_from_cursor,
    silence_snap,
    two_point_stretch,
)
from audio_visualizer.ui.tabs.srtEdit.tableModel import SubtitleTableModel
from audio_visualizer.ui.tabs.srtEdit.waveformView import WaveformView

logger = logging.getLogger(__name__)

_AUDIO_FILTERS = "Audio Files (*.wav *.mp3 *.flac *.ogg *.aac *.m4a);;All Files (*)"
_SUBTITLE_FILTERS = (
    "Subtitle Files (*.srt *.ass *.vtt *.json);;JSON Bundles (*.json *.bundle.json)"
    ";;SRT Files (*.srt);;All Files (*)"
)
_BUNDLE_FILTERS = "JSON Bundles (*.json *.bundle.json);;All Files (*)"


class _WaveformLoadSignals(QObject):
    finished = Signal(object, int, int)  # (samples, sample_rate, request_id)
    failed = Signal(str, int)            # (error_message, request_id)


class _WaveformLoadWorker(QRunnable):
    """Background worker for loading waveform data."""

    def __init__(self, load_fn, path: str, request_id: int) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._load_fn = load_fn
        self._path = path
        self._request_id = request_id
        self.signals = _WaveformLoadSignals()

    def run(self) -> None:
        try:
            samples, sr = self._load_fn(self._path)
            self.signals.finished.emit(samples, sr, self._request_id)
        except Exception as exc:
            self.signals.failed.emit(str(exc), self._request_id)


class SrtEditTab(BaseTab):
    """Waveform-backed subtitle editor tab."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def tab_id(self) -> str:
        return "srt_edit"

    @property
    def tab_title(self) -> str:
        return "SRT Edit"

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_undo_stack(200)

        self._document = SubtitleDocument()
        self._table_model = SubtitleTableModel(self._document)
        self._audio_path: Optional[str] = None
        self._subtitle_path: Optional[str] = None
        self._bundle_path: Optional[str] = None  # Tracks loaded bundle file
        self._lint_profile_key: str = "pipeline_default"
        self._lint_issues: list[LintIssue] = []
        self._refreshing_asset_combos = False
        self._waveform_request_id: int = 0
        self._pending_highlight_row: int | None = None
        self._correction_db: Any = None  # Lazy CorrectionDatabase

        self._build_ui()
        self._connect_signals()
        self._setup_shortcuts()
        self._setup_playback_timer()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the full tab layout.

        Layout structure:
        - Top: source picker row (audio + subtitle combos)
        - Middle: vertical splitter (waveform on top, table+sidebar below)
          - Table view on the left
          - Right sidebar with: segment editor, playback, edit, save,
            resync, and QA/lint sections
        """
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(6, 6, 6, 6)

        # -- Source pickers row --
        picker_layout = QHBoxLayout()

        # Audio picker
        picker_layout.addWidget(QLabel("Audio:"))
        self._audio_combo = QComboBox()
        self._audio_combo.setMinimumWidth(200)
        self._audio_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        picker_layout.addWidget(self._audio_combo)
        self._browse_audio_btn = QPushButton("Browse...")
        picker_layout.addWidget(self._browse_audio_btn)

        picker_layout.addSpacing(20)

        # Subtitle picker
        picker_layout.addWidget(QLabel("Subtitle:"))
        self._subtitle_combo = QComboBox()
        self._subtitle_combo.setMinimumWidth(200)
        self._subtitle_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        picker_layout.addWidget(self._subtitle_combo)
        self._browse_subtitle_btn = QPushButton("Browse...")
        picker_layout.addWidget(self._browse_subtitle_btn)

        root_layout.addLayout(picker_layout)

        # -- Main splitter (waveform top, table + sidebar bottom) --
        self._main_splitter = QSplitter(Qt.Orientation.Vertical)

        # Waveform panel
        self._waveform_view = WaveformView()
        self._main_splitter.addWidget(self._waveform_view)

        # Bottom panel (table + right sidebar)
        bottom_widget = QWidget()
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        # Table view
        self._table_view = QTableView()
        self._table_view.setModel(self._table_model)
        self._table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._table_view.setAlternatingRowColors(True)
        self._table_view.verticalHeader().setVisible(False)
        self._table_view.setWordWrap(True)
        self._table_view.setTextElideMode(Qt.TextElideMode.ElideNone)

        header = self._table_view.horizontalHeader()
        header.setStretchLastSection(False)
        from audio_visualizer.ui.tabs.srtEdit.tableModel import (
            COL_INDEX, COL_START, COL_END, COL_DURATION, COL_TEXT, COL_SPEAKER,
            MultilineTextDelegate,
        )
        self._table_view.setItemDelegateForColumn(COL_TEXT, MultilineTextDelegate(self._table_view))
        header.setSectionResizeMode(COL_INDEX, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_START, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_END, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_DURATION, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_TEXT, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_SPEAKER, QHeaderView.ResizeMode.Interactive)
        self._table_view.setColumnWidth(COL_SPEAKER, 80)

        self._table_view.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )

        bottom_layout.addWidget(self._table_view, stretch=3)

        # -- Right sidebar --
        sidebar = self._build_sidebar()
        bottom_layout.addWidget(sidebar, stretch=1)

        bottom_widget.setLayout(bottom_layout)
        self._main_splitter.addWidget(bottom_widget)

        self._main_splitter.setSizes([300, 400])
        root_layout.addWidget(self._main_splitter, stretch=1)

        self.setLayout(root_layout)

        # -- Media player --
        self._media_player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._media_player.setAudioOutput(self._audio_output)

    # ------------------------------------------------------------------
    # Sidebar construction
    # ------------------------------------------------------------------

    def _build_sidebar(self) -> QWidget:
        """Build the right sidebar with all control sections."""
        sidebar = QWidget()
        sidebar.setMinimumWidth(250)
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 0, 0, 0)

        # --- Segment editor section ---
        editor_group = QGroupBox("Segment Text")
        editor_layout = QVBoxLayout()
        self._sidebar_editor = QPlainTextEdit()
        self._sidebar_editor.setPlaceholderText("Select a segment to edit its text here...")
        self._sidebar_editor.setMaximumHeight(120)
        from audio_visualizer.ui.tabs.srtEdit.markdownHighlighter import MarkdownHighlighter
        self._sidebar_highlighter = MarkdownHighlighter(self._sidebar_editor.document())
        editor_layout.addWidget(self._sidebar_editor)
        editor_group.setLayout(editor_layout)
        layout.addWidget(editor_group)

        # Track which entry the sidebar editor is bound to
        self._sidebar_entry_index: int = -1
        self._sidebar_updating: bool = False  # Guard against feedback loops

        # --- Playback section ---
        playback_group = QGroupBox("Playback")
        playback_layout = QHBoxLayout()
        self._play_btn = QPushButton("Play")
        self._pause_btn = QPushButton("Pause")
        self._stop_btn = QPushButton("Stop")
        playback_layout.addWidget(self._play_btn)
        playback_layout.addWidget(self._pause_btn)
        playback_layout.addWidget(self._stop_btn)
        playback_group.setLayout(playback_layout)
        layout.addWidget(playback_group)

        # --- Edit section ---
        edit_group = QGroupBox("Edit")
        edit_layout = QVBoxLayout()
        edit_row1 = QHBoxLayout()
        self._add_entry_btn = QPushButton("Add Entry")
        self._remove_entry_btn = QPushButton("Remove Entry")
        edit_row1.addWidget(self._add_entry_btn)
        edit_row1.addWidget(self._remove_entry_btn)
        edit_layout.addLayout(edit_row1)
        edit_row2 = QHBoxLayout()
        self._split_entry_btn = QPushButton("Split Entry")
        self._merge_entries_btn = QPushButton("Merge Entries")
        edit_row2.addWidget(self._split_entry_btn)
        edit_row2.addWidget(self._merge_entries_btn)
        edit_layout.addLayout(edit_row2)
        edit_group.setLayout(edit_layout)
        layout.addWidget(edit_group)

        # --- Save section ---
        save_group = QGroupBox("Save / Export")
        save_layout = QHBoxLayout()
        self._save_btn = QPushButton("Save SRT")
        self._save_bundle_btn = QPushButton("Save Bundle")
        self._export_btn = QPushButton("Export As...")
        save_layout.addWidget(self._save_btn)
        save_layout.addWidget(self._save_bundle_btn)
        save_layout.addWidget(self._export_btn)
        save_group.setLayout(save_layout)
        layout.addWidget(save_group)

        # --- Resync section ---
        resync_group = QGroupBox("Resync")
        resync_layout = QVBoxLayout()
        resync_row1 = QHBoxLayout()
        self._global_shift_btn = QPushButton("Global Shift")
        self._shift_cursor_btn = QPushButton("Shift from Cursor")
        resync_row1.addWidget(self._global_shift_btn)
        resync_row1.addWidget(self._shift_cursor_btn)
        resync_layout.addLayout(resync_row1)
        resync_row2 = QHBoxLayout()
        self._two_point_btn = QPushButton("2-Point Stretch")
        self._fps_correct_btn = QPushButton("FPS Correction")
        resync_row2.addWidget(self._two_point_btn)
        resync_row2.addWidget(self._fps_correct_btn)
        resync_layout.addLayout(resync_row2)
        self._silence_snap_btn = QPushButton("Silence Snap")
        resync_layout.addWidget(self._silence_snap_btn)
        resync_group.setLayout(resync_layout)
        layout.addWidget(resync_group)

        # --- QA/Lint section ---
        qa_group = QGroupBox("QA / Lint")
        qa_layout = QVBoxLayout()
        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel("Profile:"))
        self._lint_profile_combo = QComboBox()
        for key, profile in BUILTIN_PROFILES.items():
            self._lint_profile_combo.addItem(profile.name, key)
        profile_row.addWidget(self._lint_profile_combo)
        self._run_lint_btn = QPushButton("Run Lint")
        profile_row.addWidget(self._run_lint_btn)
        qa_layout.addLayout(profile_row)

        self._lint_list = QListWidget()
        qa_layout.addWidget(self._lint_list)
        qa_group.setLayout(qa_layout)
        layout.addWidget(qa_group)

        layout.addStretch()
        sidebar.setLayout(layout)
        return sidebar

    def _connect_signals(self) -> None:
        """Wire up all signal/slot connections."""
        self._browse_audio_btn.clicked.connect(self._on_browse_audio)
        self._browse_subtitle_btn.clicked.connect(self._on_browse_subtitle)
        self._audio_combo.currentIndexChanged.connect(self._on_audio_asset_selected)
        self._subtitle_combo.currentIndexChanged.connect(self._on_subtitle_asset_selected)

        self._play_btn.clicked.connect(self._on_play)
        self._pause_btn.clicked.connect(self._on_pause)
        self._stop_btn.clicked.connect(self._on_stop)

        self._add_entry_btn.clicked.connect(self._on_add_entry)
        self._remove_entry_btn.clicked.connect(self._on_remove_entry)
        self._split_entry_btn.clicked.connect(self._on_split_entry)
        self._merge_entries_btn.clicked.connect(self._on_merge_entries)

        self._run_lint_btn.clicked.connect(self._on_run_lint)
        self._lint_list.itemClicked.connect(self._on_lint_item_clicked)

        self._global_shift_btn.clicked.connect(self._on_global_shift)
        self._shift_cursor_btn.clicked.connect(self._on_shift_from_cursor)
        self._two_point_btn.clicked.connect(self._on_two_point_stretch)
        self._fps_correct_btn.clicked.connect(self._on_fps_correction)
        self._silence_snap_btn.clicked.connect(self._on_silence_snap)

        self._save_btn.clicked.connect(self._on_save)
        self._save_bundle_btn.clicked.connect(self._on_save_bundle)
        self._export_btn.clicked.connect(self._on_export)

        # Sidebar editor: commit edits back to the document
        self._sidebar_editor.textChanged.connect(self._on_sidebar_text_changed)

        self._waveform_view.seek_requested.connect(self._on_seek_requested)
        self._waveform_view.play_pause_requested.connect(self._on_play_pause_toggle)
        self._waveform_view.boundary_moved.connect(self._on_boundary_moved)
        self._waveform_view.word_boundary_moved.connect(self._on_word_boundary_moved)
        self._waveform_view.context_action.connect(self._on_context_action)
        self._waveform_view.drag_select_region.connect(self._on_drag_select_create)
        self._waveform_view.word_region_clicked.connect(self._on_word_region_clicked)

        self._table_view.selectionModel().selectionChanged.connect(
            self._on_table_selection_changed
        )
        self._table_view.clicked.connect(self._on_table_clicked)

        self._table_model.inline_edit_requested.connect(self._on_inline_edit)
        self._table_model.word_edit_requested.connect(self._on_word_inline_edit)
        self._table_model.dataChanged.connect(self._on_data_changed)

    def _setup_shortcuts(self) -> None:
        """Set up keyboard shortcuts."""
        undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        undo_shortcut.activated.connect(self._on_undo)
        redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self)
        redo_shortcut.activated.connect(self._on_redo)

    def _setup_playback_timer(self) -> None:
        """Timer to update playback cursor on the waveform."""
        self._playback_timer = QTimer(self)
        self._playback_timer.setInterval(50)
        self._playback_timer.timeout.connect(self._on_playback_tick)

    # ------------------------------------------------------------------
    # Audio loading
    # ------------------------------------------------------------------

    def _on_browse_audio(self) -> None:
        path = self._pick_path("audio", "Select Audio File", _AUDIO_FILTERS)
        if path is not None:
            self._load_audio(str(path))

    def _load_audio(self, path: str) -> None:
        """Load audio for waveform display and playback."""
        self._audio_path = path
        self._audio_combo.blockSignals(True)
        self._audio_combo.clear()
        self._audio_combo.addItem(os.path.basename(path), path)
        self._audio_combo.blockSignals(False)

        # Clear existing regions and pending highlight before reload
        self._pending_highlight_row = None
        self._waveform_view.clear_regions()

        # Show loading indicator and launch background waveform load
        self._waveform_request_id += 1
        request_id = self._waveform_request_id
        self._waveform_view.set_loading_message("Loading waveform...")

        worker = _WaveformLoadWorker(self._load_waveform_data, path, request_id)
        worker.signals.finished.connect(self._on_waveform_loaded)
        worker.signals.failed.connect(self._on_waveform_load_failed)
        QThreadPool.globalInstance().start(worker)

        # Set up media player (lightweight, stays synchronous)
        self._media_player.setSource(QUrl.fromLocalFile(path))
        logger.info("Audio loading started: %s", path)
        self.settings_changed.emit()

    def _on_waveform_loaded(self, samples, sr: int, request_id: int) -> None:
        """Handle completed waveform load on the UI thread."""
        if request_id != self._waveform_request_id:
            return  # Stale result — user selected a newer file
        self._waveform_view.load_waveform(samples, sr)

        # Re-apply subtitle regions if document has entries
        if self._document.entries:
            self._waveform_view.set_regions(self._document.entries)

        # Replay pending or current highlight
        if self._pending_highlight_row is not None:
            self._waveform_view.highlight_region(self._pending_highlight_row)
            self._pending_highlight_row = None
        elif self._table_view.currentIndex().isValid():
            self._waveform_view.highlight_region(self._table_view.currentIndex().row())

    def _on_waveform_load_failed(self, error_message: str, request_id: int) -> None:
        """Handle failed waveform load on the UI thread."""
        if request_id != self._waveform_request_id:
            return  # Stale result
        self._pending_highlight_row = None
        logger.error("Failed to load waveform: %s", error_message)
        self._waveform_view.set_error_message("Failed to load waveform")

    # ------------------------------------------------------------------
    # Subtitle loading
    # ------------------------------------------------------------------

    def _on_browse_subtitle(self) -> None:
        path = self._pick_path("subtitle", "Select Subtitle File", _SUBTITLE_FILTERS)
        if path is not None:
            self._load_subtitle(str(path))

    def _load_subtitle(self, path: str) -> None:
        """Load a subtitle or bundle file into the document."""
        self._subtitle_path = path
        self._subtitle_combo.blockSignals(True)
        self._subtitle_combo.clear()
        self._subtitle_combo.addItem(os.path.basename(path), path)
        self._subtitle_combo.blockSignals(False)

        try:
            if is_bundle_file(path):
                self._document.load_bundle(path)
                self._bundle_path = path
            else:
                self._bundle_path = None
                ext = Path(path).suffix.lower()
                if ext == ".ass":
                    from audio_visualizer.ui.tabs.srtEdit.parser import parse_ass_file
                    entries = parse_ass_file(path)
                    self._document._entries = entries
                    self._document._dirty = False
                elif ext == ".vtt":
                    from audio_visualizer.ui.tabs.srtEdit.parser import parse_vtt_file
                    entries = parse_vtt_file(path)
                    self._document._entries = entries
                    self._document._dirty = False
                else:
                    self._document.load_srt(path)
        except Exception:
            logger.exception("Failed to load subtitle file %s", path)
            QMessageBox.warning(self, "Load Error", f"Could not load subtitle file:\n{path}")
            return

        self._table_model.refresh()
        self._waveform_view.set_regions(self._document.entries)
        if self._table_view.currentIndex().isValid():
            self._waveform_view.highlight_region(self._table_view.currentIndex().row())
        self._clear_undo_stack()
        logger.info("Subtitle loaded: %s (%d entries)", path, len(self._document.entries))
        self.settings_changed.emit()

    # ------------------------------------------------------------------
    # Playback controls
    # ------------------------------------------------------------------

    def _on_play(self) -> None:
        self._media_player.play()
        self._playback_timer.start()

    def _on_pause(self) -> None:
        self._media_player.pause()
        self._playback_timer.stop()

    def _on_stop(self) -> None:
        self._media_player.stop()
        self._playback_timer.stop()
        self._waveform_view.set_cursor(0)

    def _on_seek_requested(self, ms: int) -> None:
        self._media_player.setPosition(ms)
        self._waveform_view.set_cursor(ms)

    def _on_play_pause_toggle(self) -> None:
        """Toggle playback start/pause."""
        from PySide6.QtMultimedia import QMediaPlayer
        if self._media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._on_pause()
        else:
            self._on_play()

    def _on_boundary_moved(self, index: int, which: str, ms: int) -> None:
        """Handle a region boundary drag from the waveform.

        Applies overlap clamping via the document model before committing.
        """
        if index < 0 or index >= len(self._document.entries):
            return
        entry = self._document.entries[index]
        new_start = ms if which == "start" else entry.start_ms
        new_end = ms if which == "end" else entry.end_ms
        new_start, new_end = self._document.clamp_segment_bounds(index, new_start, new_end)
        cmd = EditTimestampCommand(
            self._document, index, new_start_ms=new_start, new_end_ms=new_end,
        )
        self._push_command(cmd)
        self._table_model.notify_rows_changed(index, index)
        self._waveform_view.set_regions(self._document.entries)

    def _on_playback_tick(self) -> None:
        pos = self._media_player.position()
        self._waveform_view.set_cursor(pos)

    # ------------------------------------------------------------------
    # Entry editing
    # ------------------------------------------------------------------

    def _selected_row(self) -> int:
        """Return the currently selected display row, or -1."""
        indexes = self._table_view.selectionModel().selectedRows()
        if indexes:
            return indexes[0].row()
        return -1

    def _selected_entry_index(self) -> int:
        """Return the entry index for the current selection, or -1."""
        row = self._selected_row()
        if row < 0:
            return -1
        return self._table_model.entry_index_for_row(row)

    def _on_add_entry(self) -> None:
        idx = self._selected_entry_index()
        if 0 <= idx < len(self._document.entries):
            ref = self._document.entries[idx]
            start = ref.end_ms
            end = start + 2000
        elif self._document.entries:
            last = self._document.entries[-1]
            start = last.end_ms
            end = start + 2000
        else:
            start = 0
            end = 2000

        entry = SubtitleEntry(index=0, start_ms=start, end_ms=end, text="New subtitle")
        cmd = AddEntryCommand(self._document, entry)
        self._push_command(cmd)
        self._refresh_after_edit()

    def _on_remove_entry(self) -> None:
        idx = self._selected_entry_index()
        if idx < 0:
            return
        cmd = RemoveEntryCommand(self._document, idx)
        self._push_command(cmd)
        self._refresh_after_edit()

    def _on_split_entry(self, row: int | None = None) -> None:
        if row is None:
            row = self._selected_row()
        if row < 0:
            return
        entry = self._document.entries[row]
        # Use playhead position if it falls inside the segment
        playhead_ms = self._waveform_view.get_cursor_ms()
        if entry.start_ms < playhead_ms < entry.end_ms:
            split_ms = playhead_ms
        else:
            split_ms = (entry.start_ms + entry.end_ms) // 2
        if split_ms <= entry.start_ms or split_ms >= entry.end_ms:
            return
        cmd = SplitEntryCommand(self._document, row, split_ms)
        self._push_command(cmd)
        self._refresh_after_edit()

    def _on_merge_entries(self) -> None:
        idx = self._selected_entry_index()
        if idx < 0 or idx + 1 >= len(self._document.entries):
            return
        cmd = MergeEntriesCommand(self._document, idx, idx + 1)
        self._push_command(cmd)
        self._refresh_after_edit()

    def _on_undo(self) -> None:
        if self._undo_stack is not None and self._undo_stack.canUndo():
            self._undo_stack.undo()
            self._refresh_after_edit()

    def _on_redo(self) -> None:
        if self._undo_stack is not None and self._undo_stack.canRedo():
            self._undo_stack.redo()
            self._refresh_after_edit()

    def _refresh_after_edit(self) -> None:
        """Refresh the table model, waveform regions, and sidebar after an edit."""
        self._table_model.refresh()
        self._waveform_view.set_regions(self._document.entries)
        self._sync_sidebar_to_selection()
        self.settings_changed.emit()

    def _on_table_selection_changed(self) -> None:
        row = self._selected_row()
        if row < 0:
            return
        mapping = self._table_model.row_mapping(row)
        if mapping is None:
            return
        entry_idx = mapping.entry_index
        if not self._waveform_view.has_regions():
            self._pending_highlight_row = entry_idx
        if mapping.is_word_row:
            # Highlight the parent segment and also sync word selection
            if self._waveform_view.has_regions():
                self._waveform_view.highlight_region(entry_idx)
                self._waveform_view.highlight_word(entry_idx, mapping.word_index)
        else:
            if self._waveform_view.has_regions():
                self._waveform_view.highlight_region(entry_idx)
        # Sync sidebar editor to the selected segment
        self._sync_sidebar_to_selection()

    # ------------------------------------------------------------------
    # Sidebar editor synchronization
    # ------------------------------------------------------------------

    def _sync_sidebar_to_selection(self) -> None:
        """Update the sidebar editor to reflect the currently selected segment."""
        entry_idx = self._selected_entry_index()
        if entry_idx < 0 or entry_idx >= len(self._document.entries):
            if self._sidebar_entry_index >= 0:
                self._sidebar_updating = True
                self._sidebar_editor.setPlainText("")
                self._sidebar_entry_index = -1
                self._sidebar_updating = False
            return

        entry = self._document.entries[entry_idx]
        if entry_idx == self._sidebar_entry_index:
            # Same entry — only update if text actually differs (avoids cursor jump)
            if self._sidebar_editor.toPlainText() != entry.text:
                self._sidebar_updating = True
                self._sidebar_editor.setPlainText(entry.text)
                self._sidebar_updating = False
            return

        # Different entry selected — load its text
        self._sidebar_updating = True
        self._sidebar_entry_index = entry_idx
        self._sidebar_editor.setPlainText(entry.text)
        self._sidebar_updating = False

    def _on_sidebar_text_changed(self) -> None:
        """Commit sidebar text edits back to the document via the undo stack."""
        if self._sidebar_updating:
            return
        idx = self._sidebar_entry_index
        if idx < 0 or idx >= len(self._document.entries):
            return
        new_text = self._sidebar_editor.toPlainText()
        entry = self._document.entries[idx]
        if new_text == entry.text:
            return

        old_text = entry.text
        cmd = EditTextCommand(self._document, idx, new_text)
        self._push_command(cmd)
        self._table_model.notify_rows_changed(idx, idx)
        self._waveform_view.set_regions(self._document.entries)
        self._maybe_record_correction(entry, old_text, new_text)

    def _on_inline_edit(self, row: int, col: int, value: object) -> None:
        """Handle inline table edits via undoable commands.

        For text edits on bundle-backed entries, a correction is recorded
        automatically when the new text differs from original_text.
        """
        from audio_visualizer.ui.tabs.srtEdit.tableModel import (
            COL_END,
            COL_SPEAKER,
            COL_START,
            COL_TEXT,
        )

        if col == COL_START:
            cmd = EditTimestampCommand(self._document, row, new_start_ms=value)
            self._push_command(cmd)
        elif col == COL_END:
            cmd = EditTimestampCommand(self._document, row, new_end_ms=value)
            self._push_command(cmd)
        elif col == COL_TEXT:
            entry = self._document.entries[row]
            old_text = entry.text
            cmd = EditTextCommand(self._document, row, str(value))
            self._push_command(cmd)
            # Record correction for forward text edits on provenance entries
            self._maybe_record_correction(entry, old_text, str(value))
        elif col == COL_SPEAKER:
            cmd = EditSpeakerCommand(self._document, row, value)
            self._push_command(cmd)

        self._table_model.notify_rows_changed(row, row)
        self._waveform_view.set_regions(self._document.entries)
        # Keep sidebar editor in sync when text is edited in the table
        if col == COL_TEXT:
            self._sync_sidebar_to_selection()

    def _on_data_changed(self, top_left, bottom_right, roles=None) -> None:
        """Resize rows when text content changes."""
        from audio_visualizer.ui.tabs.srtEdit.tableModel import COL_TEXT

        for row in range(top_left.row(), bottom_right.row() + 1):
            if top_left.column() <= COL_TEXT <= bottom_right.column():
                self._table_view.resizeRowToContents(row)

    # ------------------------------------------------------------------
    # Word-level editing
    # ------------------------------------------------------------------

    def _on_word_inline_edit(self, entry_idx: int, word_idx: int, col: int, value: object) -> None:
        """Handle inline word row edits via undoable commands."""
        from audio_visualizer.ui.tabs.srtEdit.tableModel import COL_END, COL_START, COL_TEXT

        if col == COL_TEXT:
            cmd = EditWordTextCommand(self._document, entry_idx, word_idx, str(value))
            self._push_command(cmd)
        elif col == COL_START:
            new_start = float(value)
            new_start, _ = self._document.clamp_word_bounds(
                entry_idx, word_idx, new_start, self._document.entries[entry_idx].words[word_idx].end,
            )
            cmd = EditWordTimingCommand(self._document, entry_idx, word_idx, new_start=new_start)
            self._push_command(cmd)
        elif col == COL_END:
            new_end = float(value)
            _, new_end = self._document.clamp_word_bounds(
                entry_idx, word_idx, self._document.entries[entry_idx].words[word_idx].start, new_end,
            )
            cmd = EditWordTimingCommand(self._document, entry_idx, word_idx, new_end=new_end)
            self._push_command(cmd)
        self._table_model.notify_rows_changed(entry_idx, entry_idx)
        self._waveform_view.set_regions(self._document.entries)

    def _on_word_boundary_moved(
        self, entry_idx: int, word_idx: int, new_start: float, new_end: float
    ) -> None:
        """Handle word region drag from the waveform."""
        if entry_idx < 0 or entry_idx >= len(self._document.entries):
            return
        entry = self._document.entries[entry_idx]
        if word_idx < 0 or word_idx >= len(entry.words):
            return
        new_start, new_end = self._document.clamp_word_bounds(
            entry_idx, word_idx, new_start, new_end,
        )
        cmd = EditWordTimingCommand(
            self._document, entry_idx, word_idx, new_start=new_start, new_end=new_end,
        )
        self._push_command(cmd)
        self._table_model.notify_rows_changed(entry_idx, entry_idx)
        self._waveform_view.set_regions(self._document.entries)

    def _on_word_region_clicked(self, entry_idx: int, word_idx: int) -> None:
        """Handle word region click: sync selection to table."""
        self._table_model.word_selected.emit(entry_idx, word_idx)
        # Ensure the entry is expanded so the word row is visible
        if not self._table_model.is_expanded(entry_idx):
            self._table_model.toggle_expand(entry_idx)
        display_row = self._table_model.word_row_for(entry_idx, word_idx)
        if display_row >= 0:
            self._table_view.selectRow(display_row)

    def _on_table_clicked(self, index) -> None:
        """Handle click on a table row -- toggle expand on index column."""
        from audio_visualizer.ui.tabs.srtEdit.tableModel import COL_INDEX
        if index.column() == COL_INDEX:
            mapping = self._table_model.row_mapping(index.row())
            if mapping is not None and not mapping.is_word_row:
                entry = self._document.entries[mapping.entry_index]
                if entry.words:
                    self._table_model.toggle_expand(mapping.entry_index)

    # ------------------------------------------------------------------
    # Context menu actions (from waveform timeline)
    # ------------------------------------------------------------------

    def _on_context_action(self, action: str, entry_index: int) -> None:
        """Route context menu actions from the waveform view."""
        if entry_index < 0 or entry_index >= len(self._document.entries):
            return
        if action == "split_at_playhead":
            self._on_split_entry(row=entry_index)
        elif action == "merge_next":
            if entry_index + 1 < len(self._document.entries):
                cmd = MergeEntriesCommand(self._document, entry_index, entry_index + 1)
                self._push_command(cmd)
                self._refresh_after_edit()
        elif action == "merge_prev":
            if entry_index > 0:
                cmd = MergeEntriesCommand(self._document, entry_index - 1, entry_index)
                self._push_command(cmd)
                self._refresh_after_edit()
        elif action == "delete":
            cmd = RemoveEntryCommand(self._document, entry_index)
            self._push_command(cmd)
            self._refresh_after_edit()
        elif action == "edit_text":
            # Select the row and start editing the text column
            display_row = self._table_model.subtitle_row_for_entry(entry_index)
            if display_row >= 0:
                from audio_visualizer.ui.tabs.srtEdit.tableModel import COL_TEXT
                self._table_view.selectRow(display_row)
                text_index = self._table_model.index(display_row, COL_TEXT)
                self._table_view.edit(text_index)

    # ------------------------------------------------------------------
    # Drag-to-select creation
    # ------------------------------------------------------------------

    def _on_drag_select_create(self, start_s: float, end_s: float) -> None:
        """Create a new blank segment from a drag-selection region."""
        start_ms = max(0, int(start_s * 1000))
        end_ms = max(start_ms + 1, int(end_s * 1000))
        entry = SubtitleEntry(index=0, start_ms=start_ms, end_ms=end_ms, text="New subtitle")
        cmd = AddEntryCommand(self._document, entry)
        self._push_command(cmd)
        self._refresh_after_edit()

    # ------------------------------------------------------------------
    # Correction recording
    # ------------------------------------------------------------------

    def _get_correction_db(self):
        """Lazily create and return the CorrectionDatabase singleton."""
        if self._correction_db is None:
            try:
                from audio_visualizer.core.correctionDb import CorrectionDatabase

                self._correction_db = CorrectionDatabase()
            except Exception:
                logger.exception("Failed to initialise correction database")
                return None
        return self._correction_db

    @staticmethod
    def _entry_has_provenance(entry: SubtitleEntry) -> bool:
        """Return True if the entry has bundle-backed provenance fields.

        Provenance requires both a source media path and an original text
        snapshot.  Plain SRT imports will lack these fields.
        """
        return (
            entry.source_media_path is not None
            and entry.original_text is not None
        )

    def _maybe_record_correction(
        self,
        entry: SubtitleEntry,
        old_text: str,
        new_text: str,
    ) -> None:
        """Record a correction if the entry has provenance and text changed.

        This is the single recording path used by both table inline edits
        and any future sidebar edits.  It is only called for forward user
        actions, never for undo/redo replays.
        """
        if old_text == new_text:
            return
        if not self._entry_has_provenance(entry):
            return

        db = self._get_correction_db()
        if db is None:
            return

        try:
            db.record_correction(
                source_media_path=entry.source_media_path,  # type: ignore[arg-type]
                time_start_ms=entry.start_ms,
                time_end_ms=entry.end_ms,
                original_text=entry.original_text,  # type: ignore[arg-type]
                corrected_text=new_text,
                speaker_label=entry.speaker,
                model_name=entry.model_name,
                confidence=entry.alignment_confidence,
                bundle_entry_id=entry.id,
            )
            self._maybe_add_prompt_terms(entry.original_text or "", new_text, entry.speaker)
        except Exception:
            logger.exception("Failed to record correction for entry #%d", entry.index)

    def _maybe_add_prompt_terms(
        self,
        original_text: str,
        corrected_text: str,
        speaker_label: Optional[str],
    ) -> None:
        """Auto-populate prompt terms when a correction introduces new words.

        New words that look like domain terms or proper nouns (capitalised
        words not at sentence boundaries, or words containing digits/hyphens)
        are added as candidate prompt terms.
        """
        db = self._get_correction_db()
        if db is None:
            return

        original_words = set(original_text.split())
        corrected_words = set(corrected_text.split())
        new_words = corrected_words - original_words

        for word in new_words:
            clean = word.strip(".,!?;:\"'()[]")
            if not clean:
                continue
            # Consider a word a domain-term candidate if it is:
            #   - capitalised (but not the first word of the sentence)
            #   - contains digits or hyphens (e.g. "COVID-19", "v3")
            is_capitalised = clean[0].isupper() and len(clean) > 1
            has_special = bool(re.search(r"[\d-]", clean))
            if is_capitalised or has_special:
                try:
                    db.add_prompt_term(
                        clean,
                        category="auto",
                        speaker_label=speaker_label,
                        source="correction",
                    )
                except Exception:
                    logger.debug("Could not add prompt term '%s'", clean)

    # ------------------------------------------------------------------
    # Lint
    # ------------------------------------------------------------------

    def _on_run_lint(self) -> None:
        key = self._lint_profile_combo.currentData()
        if key and key in BUILTIN_PROFILES:
            self._lint_profile_key = key

        profile = BUILTIN_PROFILES.get(self._lint_profile_key)
        if profile is None:
            return

        self._lint_issues = run_lint(self._document, profile)
        self._lint_list.clear()
        for issue in self._lint_issues:
            icon = {"error": "X", "warning": "!", "info": "i"}.get(issue.severity, "?")
            item = QListWidgetItem(
                f"[{icon}] #{issue.entry_index + 1}: {issue.message}"
            )
            item.setData(Qt.ItemDataRole.UserRole, issue.entry_index)
            self._lint_list.addItem(item)

        logger.info("Lint found %d issues (profile: %s)", len(self._lint_issues), self._lint_profile_key)

    def _on_lint_item_clicked(self, item: QListWidgetItem) -> None:
        row = item.data(Qt.ItemDataRole.UserRole)
        if row is not None and 0 <= row < len(self._document.entries):
            self._table_view.selectRow(row)
            self._waveform_view.highlight_region(row)

    # ------------------------------------------------------------------
    # Resync operations
    # ------------------------------------------------------------------

    def _on_global_shift(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        delta, ok = QInputDialog.getInt(
            self, "Global Shift", "Shift (ms, negative for earlier):", 0, -600000, 600000
        )
        if not ok:
            return
        changes = global_shift(self._document, delta)
        if changes:
            cmd = BatchResyncCommand(self._document, changes, f"Global shift {delta:+d} ms")
            self._push_command(cmd)
            self._refresh_after_edit()

    def _on_shift_from_cursor(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        idx = self._selected_entry_index()
        if idx < 0:
            QMessageBox.information(self, "Shift from Cursor", "Select an entry first.")
            return
        delta, ok = QInputDialog.getInt(
            self, "Shift from Cursor", "Shift (ms):", 0, -600000, 600000
        )
        if not ok:
            return
        changes = shift_from_cursor(self._document, idx, delta)
        if changes:
            cmd = BatchResyncCommand(
                self._document, changes, f"Shift from #{row + 1} by {delta:+d} ms"
            )
            self._push_command(cmd)
            self._refresh_after_edit()

    def _on_two_point_stretch(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        entries = self._document.entries
        if len(entries) < 2:
            QMessageBox.information(self, "2-Point Stretch", "Need at least 2 entries.")
            return

        idx1, ok = QInputDialog.getInt(
            self, "2-Point Stretch", "First anchor entry # (1-based):", 1, 1, len(entries)
        )
        if not ok:
            return
        ms1, ok = QInputDialog.getInt(
            self, "2-Point Stretch", f"Target time for entry #{idx1} (ms):",
            entries[idx1 - 1].start_ms, 0, 86400000,
        )
        if not ok:
            return
        idx2, ok = QInputDialog.getInt(
            self, "2-Point Stretch", "Second anchor entry # (1-based):", len(entries), 1, len(entries)
        )
        if not ok:
            return
        ms2, ok = QInputDialog.getInt(
            self, "2-Point Stretch", f"Target time for entry #{idx2} (ms):",
            entries[idx2 - 1].start_ms, 0, 86400000,
        )
        if not ok:
            return

        changes = two_point_stretch(self._document, idx1 - 1, ms1, idx2 - 1, ms2)
        if changes:
            cmd = BatchResyncCommand(self._document, changes, "2-point stretch")
            self._push_command(cmd)
            self._refresh_after_edit()

    def _on_fps_correction(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        source, ok = QInputDialog.getDouble(
            self, "FPS Correction", "Source FPS:", 25.0, 1.0, 120.0, 3
        )
        if not ok:
            return
        target, ok = QInputDialog.getDouble(
            self, "FPS Correction", "Target FPS:", 23.976, 1.0, 120.0, 3
        )
        if not ok:
            return

        changes = fps_drift_correction(self._document, source, target)
        if changes:
            cmd = BatchResyncCommand(
                self._document, changes, f"FPS correction {source:.3f} -> {target:.3f}"
            )
            self._push_command(cmd)
            self._refresh_after_edit()

    def _on_silence_snap(self) -> None:
        if self._audio_path is None:
            QMessageBox.information(self, "Silence Snap", "Load an audio file first.")
            return

        try:
            from audio_visualizer.srt.io.audioHelpers import detect_silences

            silences = detect_silences(
                self._audio_path, min_silence_dur=0.2, silence_threshold_db=-35.0
            )
        except Exception:
            logger.exception("Failed to detect silences")
            QMessageBox.warning(self, "Silence Snap", "Silence detection failed.")
            return

        if not silences:
            QMessageBox.information(self, "Silence Snap", "No silences detected.")
            return

        changes = silence_snap(self._document, silences)
        if changes:
            cmd = BatchResyncCommand(self._document, changes, "Silence snap")
            self._push_command(cmd)
            self._refresh_after_edit()

    # ------------------------------------------------------------------
    # Save / export
    # ------------------------------------------------------------------

    def _on_save(self) -> None:
        if self._subtitle_path:
            path = self._subtitle_path
        else:
            from audio_visualizer.ui.sessionFilePicker import resolve_browse_directory
            start_dir = resolve_browse_directory(
                current_path=self._subtitle_path,
                workspace_context=self.workspace_context,
                selected_asset_path=self._subtitle_combo.currentData(),
            )
            path, _ = QFileDialog.getSaveFileName(
                self, "Save SRT File", start_dir, "SRT Files (*.srt);;All Files (*)"
            )
            if not path:
                return

        try:
            self._document.save_srt(path)
            self._subtitle_path = path
            asset_id = self._publish_subtitle_asset(path)
            logger.info("Saved to %s", path)
            mw = self.parent()
            if asset_id and mw and hasattr(mw, "handoff_srt_edit_to_caption_animate"):
                logger.debug("Edited subtitle published as session asset %s", asset_id)
        except Exception:
            logger.exception("Failed to save SRT")
            QMessageBox.warning(self, "Save Error", f"Could not save file:\n{path}")

    def _on_save_bundle(self) -> None:
        """Save the document as a JSON bundle preserving word timing."""
        if self._bundle_path:
            path = self._bundle_path
        else:
            from audio_visualizer.ui.sessionFilePicker import resolve_browse_directory
            start_dir = resolve_browse_directory(
                current_path=self._bundle_path or self._subtitle_path,
                workspace_context=self.workspace_context,
                selected_asset_path=self._subtitle_combo.currentData(),
            )
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Bundle File", start_dir, _BUNDLE_FILTERS,
            )
            if not path:
                return

        try:
            self._document.save_bundle(path)
            self._bundle_path = path
            self._publish_bundle_asset(path)
            logger.info("Saved bundle to %s", path)
        except Exception:
            logger.exception("Failed to save bundle")
            QMessageBox.warning(self, "Save Error", f"Could not save bundle:\n{path}")

    def _on_export(self) -> None:
        """Export SRT: plain subtitle output without bundle metadata."""
        from audio_visualizer.ui.sessionFilePicker import resolve_browse_directory
        start_dir = resolve_browse_directory(
            current_path=self._subtitle_path,
            workspace_context=self.workspace_context,
            selected_asset_path=self._subtitle_combo.currentData(),
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Subtitle File",
            start_dir,
            "SRT Files (*.srt);;ASS Files (*.ass);;VTT Files (*.vtt);;All Files (*)",
        )
        if not path:
            return
        try:
            self._document.save_srt(path)
            self._publish_subtitle_asset(path)
            logger.info("Exported to %s", path)
        except Exception:
            logger.exception("Failed to export subtitle file")
            QMessageBox.warning(self, "Export Error", f"Could not export file:\n{path}")

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------

    def validate_settings(self) -> tuple[bool, str]:
        return True, ""

    def collect_settings(self) -> dict[str, Any]:
        return {
            "audio_path": self._audio_path,
            "subtitle_path": self._subtitle_path,
            "bundle_path": self._bundle_path,
            "lint_profile": self._lint_profile_key,
        }

    def apply_settings(self, data: dict[str, Any]) -> None:
        audio_path = data.get("audio_path")
        subtitle_path = data.get("subtitle_path")
        bundle_path = data.get("bundle_path")
        lint_profile = data.get("lint_profile", "pipeline_default")

        if audio_path and os.path.isfile(audio_path):
            self._load_audio(audio_path)

        # Prefer bundle path over subtitle path when both are present
        if bundle_path and os.path.isfile(bundle_path):
            self._load_subtitle(bundle_path)
        elif subtitle_path and os.path.isfile(subtitle_path):
            self._load_subtitle(subtitle_path)

        if lint_profile in BUILTIN_PROFILES:
            self._lint_profile_key = lint_profile
            idx = self._lint_profile_combo.findData(lint_profile)
            if idx >= 0:
                self._lint_profile_combo.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    # Workspace context integration
    # ------------------------------------------------------------------

    def set_workspace_context(self, context) -> None:
        """React to workspace context injection by populating asset combos."""
        super().set_workspace_context(context)
        self._refresh_asset_combos()
        if context is not None:
            context.asset_added.connect(lambda _: self._refresh_asset_combos())
            context.asset_updated.connect(lambda _: self._refresh_asset_combos())
            context.asset_removed.connect(lambda _: self._refresh_asset_combos())

    def _refresh_asset_combos(self) -> None:
        """Populate audio and subtitle combos from session assets."""
        ctx = self.workspace_context
        if ctx is None:
            return

        self._refreshing_asset_combos = True

        # Preserve current selections
        current_audio = self._audio_combo.currentData()
        current_sub = self._subtitle_combo.currentData()

        # Audio assets
        self._audio_combo.blockSignals(True)
        self._audio_combo.clear()
        self._audio_combo.addItem("(none)", None)
        for asset in ctx.list_assets(category="audio"):
            self._audio_combo.addItem(asset.display_name, str(asset.path))
        if current_audio:
            idx = self._audio_combo.findData(current_audio)
            if idx >= 0:
                self._audio_combo.setCurrentIndex(idx)
        self._audio_combo.blockSignals(False)

        # Subtitle assets (includes both subtitle and json_bundle categories)
        self._subtitle_combo.blockSignals(True)
        self._subtitle_combo.clear()
        self._subtitle_combo.addItem("(none)", None)
        for asset in ctx.list_assets(category="subtitle"):
            self._subtitle_combo.addItem(asset.display_name, str(asset.path))
        for asset in ctx.list_assets(category="json_bundle"):
            self._subtitle_combo.addItem(f"[Bundle] {asset.display_name}", str(asset.path))
        if current_sub:
            idx = self._subtitle_combo.findData(current_sub)
            if idx >= 0:
                self._subtitle_combo.setCurrentIndex(idx)
        self._subtitle_combo.blockSignals(False)
        self._refreshing_asset_combos = False

    def _on_audio_asset_selected(self, _index: int) -> None:
        if self._refreshing_asset_combos:
            return
        path = self._audio_combo.currentData()
        if path:
            self._load_audio(str(path))

    def _on_subtitle_asset_selected(self, _index: int) -> None:
        if self._refreshing_asset_combos:
            return
        path = self._subtitle_combo.currentData()
        if path:
            self._load_subtitle(str(path))

    def _pick_path(
        self,
        category: str | None,
        title: str,
        file_filter: str,
    ) -> Path | None:
        from audio_visualizer.ui.sessionFilePicker import resolve_browse_directory

        ctx = self.workspace_context
        if ctx is None:
            start_dir = resolve_browse_directory()
            path, _ = QFileDialog.getOpenFileName(self, title, start_dir, file_filter)
            return Path(path) if path else None

        _source, path = pick_session_or_file(
            self,
            ctx,
            category,
            title=title,
            file_filter=file_filter,
        )
        return path

    def _load_waveform_data(self, path: str) -> tuple[np.ndarray, int]:
        ctx = self.workspace_context
        cache_key: tuple[str, str, str] | None = None
        if ctx is not None:
            cache_key = ctx.make_analysis_cache_key(path, "waveform", "mono@native_sr")
            cached = ctx.get_analysis(cache_key)
            if cached is not None:
                return cached

        import librosa

        samples, sr = librosa.load(path, sr=None, mono=True)
        if cache_key is not None and ctx is not None:
            ctx.store_analysis(cache_key, (samples, sr))
        return samples, sr

    def _publish_subtitle_asset(self, path: str | Path) -> str | None:
        ctx = self.workspace_context
        if ctx is None:
            return None

        subtitle_path = Path(path)
        existing = ctx.find_asset_by_path(subtitle_path)
        if existing is not None:
            ctx.update_asset(
                existing.id,
                display_name=subtitle_path.name,
                category="subtitle",
                source_tab=self.tab_id,
                role="subtitle_source",
            )
            return existing.id

        asset = SessionAsset(
            id=str(uuid.uuid4()),
            display_name=subtitle_path.name,
            path=subtitle_path,
            category="subtitle",
            source_tab=self.tab_id,
            role="subtitle_source",
        )
        self.register_output_asset(asset)
        return asset.id

    def _publish_bundle_asset(self, path: str | Path) -> str | None:
        """Register a saved bundle file as a json_bundle session asset."""
        ctx = self.workspace_context
        if ctx is None:
            return None

        bundle_path = Path(path)
        existing = ctx.find_asset_by_path(bundle_path)
        if existing is not None:
            ctx.update_asset(
                existing.id,
                display_name=bundle_path.name,
                category="json_bundle",
                source_tab=self.tab_id,
                role="bundle_source",
            )
            return existing.id

        asset = SessionAsset(
            id=str(uuid.uuid4()),
            display_name=bundle_path.name,
            path=bundle_path,
            category="json_bundle",
            source_tab=self.tab_id,
            role="bundle_source",
        )
        self.register_output_asset(asset)
        return asset.id
