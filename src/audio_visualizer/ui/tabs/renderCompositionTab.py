"""Render Composition tab — final video compositor.

Provides a layer-based composition editor with numeric positioning,
matte/key controls, layout presets, audio source selection, and
an FFmpeg-based render pipeline.  Supports full undo/redo.
"""
from __future__ import annotations

import copy
import logging
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from audio_visualizer.ui.workspaceContext import SessionAsset, WorkspaceContext
from audio_visualizer.ui.sessionFilePicker import pick_session_or_file
from audio_visualizer.ui.tabs.baseTab import BaseTab
from audio_visualizer.ui.tabs.renderComposition.commands import (
    AddAudioLayerCommand,
    AddLayerCommand,
    ApplyPresetCommand,
    ChangeAudioSourceCommand,
    ChangeSourceCommand,
    EditAudioLayerCommand,
    MoveLayerCommand,
    RemoveAudioLayerCommand,
    RemoveLayerCommand,
    ReorderLayerCommand,
    ResizeLayerCommand,
)
from audio_visualizer.ui.tabs.renderComposition.model import (
    DEFAULT_MATTE_SETTINGS,
    RESOLUTION_PRESET_LABELS,
    RESOLUTION_PRESETS,
    VALID_BEHAVIORS,
    VALID_LAYER_TYPES,
    CompositionAudioLayer,
    CompositionLayer,
    CompositionModel,
)
from audio_visualizer.ui.tabs.renderComposition.presets import (
    PRESET_NAMES,
    get_preset,
)

logger = logging.getLogger(__name__)

_VIDEO_FILTERS = (
    "Video files (*.mp4 *.mkv *.webm *.avi *.mov *.mxf);;"
    "Image files (*.png *.jpg *.jpeg *.bmp *.tiff);;"
    "All files (*)"
)

_AUDIO_FILTERS = (
    "Audio files (*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.wma);;"
    "Video files (*.mp4 *.mkv *.webm *.avi *.mov);;"
    "All files (*)"
)

_OUTPUT_FILTERS = (
    "Video files (*.mp4 *.mkv *.mov);;"
    "All files (*)"
)

_MATTE_MODES = ("none", "colorkey", "chromakey", "lumakey")


class RenderCompositionTab(BaseTab):
    """Layer-based composition editor and renderer."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def tab_id(self) -> str:
        return "render_composition"

    @property
    def tab_title(self) -> str:
        return "Render Composition"

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._main_window = parent
        self._model = CompositionModel()
        self._active_worker: Optional[Any] = None
        self._updating_ui = False  # guard against recursive signal loops

        self._init_undo_stack(100)
        self._build_ui()
        self._setup_shortcuts()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(4, 4, 4, 4)

        # Main splitter: layer list (left) + properties (right)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # -- Left: layer list panel --
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)

        layer_group = QGroupBox("Layers")
        layer_inner = QVBoxLayout()

        self._layer_list = QListWidget()
        self._layer_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._layer_list.currentRowChanged.connect(self._on_layer_selected)
        layer_inner.addWidget(self._layer_list)

        btn_row = QHBoxLayout()
        self._add_layer_btn = QPushButton("Add Layer")
        self._add_layer_btn.clicked.connect(self._on_add_layer)
        btn_row.addWidget(self._add_layer_btn)

        self._remove_layer_btn = QPushButton("Remove Layer")
        self._remove_layer_btn.clicked.connect(self._on_remove_layer)
        btn_row.addWidget(self._remove_layer_btn)

        self._move_up_btn = QPushButton("Up")
        self._move_up_btn.clicked.connect(self._on_move_up)
        btn_row.addWidget(self._move_up_btn)

        self._move_down_btn = QPushButton("Down")
        self._move_down_btn.clicked.connect(self._on_move_down)
        btn_row.addWidget(self._move_down_btn)

        layer_inner.addLayout(btn_row)
        layer_group.setLayout(layer_inner)
        left_layout.addWidget(layer_group)

        # Preset selector
        preset_group = QGroupBox("Layout Presets")
        preset_layout = QHBoxLayout()
        self._preset_combo = QComboBox()
        self._preset_combo.addItems(["(none)"] + list(PRESET_NAMES))
        preset_layout.addWidget(self._preset_combo, 1)

        self._apply_preset_btn = QPushButton("Apply")
        self._apply_preset_btn.clicked.connect(self._on_apply_preset)
        preset_layout.addWidget(self._apply_preset_btn)
        preset_group.setLayout(preset_layout)
        left_layout.addWidget(preset_group)

        left_panel.setLayout(left_layout)
        splitter.addWidget(left_panel)

        # -- Right: layer properties panel --
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)

        self._build_source_section(right_layout)
        self._build_position_section(right_layout)
        self._build_timing_section(right_layout)
        self._build_matte_section(right_layout)

        right_layout.addStretch(1)
        right_panel.setLayout(right_layout)
        splitter.addWidget(right_panel)

        splitter.setSizes([300, 500])
        content_layout.addWidget(splitter)

        # -- Timeline --
        self._build_timeline_section(content_layout)

        # -- Audio source selector --
        self._build_audio_section(content_layout)

        # -- Live preview --
        self._build_preview_section(content_layout)

        # -- Output settings --
        self._build_output_section(content_layout)

        # -- Render controls --
        self._build_render_section(content_layout)

        scroll_content.setLayout(content_layout)
        scroll.setWidget(scroll_content)
        root_layout.addWidget(scroll)
        self.setLayout(root_layout)

    def _build_source_section(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Source")
        layout = QHBoxLayout()

        self._source_combo = QComboBox()
        self._source_combo.addItem("(none)")
        self._source_combo.currentIndexChanged.connect(self._on_source_changed)
        layout.addWidget(self._source_combo, 1)

        self._browse_source_btn = QPushButton("Browse...")
        self._browse_source_btn.clicked.connect(self._on_browse_source)
        layout.addWidget(self._browse_source_btn)

        self._layer_type_combo = QComboBox()
        self._layer_type_combo.addItems(list(VALID_LAYER_TYPES))
        self._layer_type_combo.currentTextChanged.connect(self._on_layer_type_changed)
        layout.addWidget(self._layer_type_combo)

        self._layer_enabled_cb = QCheckBox("Enabled")
        self._layer_enabled_cb.setChecked(True)
        self._layer_enabled_cb.toggled.connect(self._on_layer_enabled_changed)
        layout.addWidget(self._layer_enabled_cb)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _build_position_section(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Position && Size")
        layout = QHBoxLayout()

        layout.addWidget(QLabel("X:"))
        self._x_spin = QSpinBox()
        self._x_spin.setRange(-9999, 9999)
        self._x_spin.editingFinished.connect(self._on_position_changed)
        layout.addWidget(self._x_spin)

        layout.addWidget(QLabel("Y:"))
        self._y_spin = QSpinBox()
        self._y_spin.setRange(-9999, 9999)
        self._y_spin.editingFinished.connect(self._on_position_changed)
        layout.addWidget(self._y_spin)

        layout.addWidget(QLabel("W:"))
        self._w_spin = QSpinBox()
        self._w_spin.setRange(1, 9999)
        self._w_spin.setValue(1920)
        self._w_spin.editingFinished.connect(self._on_size_changed)
        layout.addWidget(self._w_spin)

        layout.addWidget(QLabel("H:"))
        self._h_spin = QSpinBox()
        self._h_spin.setRange(1, 9999)
        self._h_spin.setValue(1080)
        self._h_spin.editingFinished.connect(self._on_size_changed)
        layout.addWidget(self._h_spin)

        layout.addWidget(QLabel("Z:"))
        self._z_spin = QSpinBox()
        self._z_spin.setRange(0, 999)
        self._z_spin.editingFinished.connect(self._on_z_order_changed)
        layout.addWidget(self._z_spin)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _build_timing_section(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Timing")
        layout = QHBoxLayout()

        layout.addWidget(QLabel("Start (ms):"))
        self._start_ms_spin = QSpinBox()
        self._start_ms_spin.setRange(0, 999999999)
        self._start_ms_spin.editingFinished.connect(self._on_timing_changed)
        layout.addWidget(self._start_ms_spin)

        layout.addWidget(QLabel("End (ms):"))
        self._end_ms_spin = QSpinBox()
        self._end_ms_spin.setRange(0, 999999999)
        self._end_ms_spin.editingFinished.connect(self._on_timing_changed)
        layout.addWidget(self._end_ms_spin)

        layout.addWidget(QLabel("After End:"))
        self._behavior_combo = QComboBox()
        self._behavior_combo.addItems(list(VALID_BEHAVIORS))
        self._behavior_combo.currentTextChanged.connect(self._on_behavior_changed)
        layout.addWidget(self._behavior_combo)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _build_matte_section(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Matte / Key")
        layout = QVBoxLayout()

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Mode:"))
        self._matte_mode_combo = QComboBox()
        self._matte_mode_combo.addItems(list(_MATTE_MODES))
        self._matte_mode_combo.currentTextChanged.connect(self._on_matte_changed)
        row1.addWidget(self._matte_mode_combo)

        row1.addWidget(QLabel("Key Color:"))
        self._key_color_edit = QLineEdit("#00FF00")
        self._key_color_edit.setMaximumWidth(80)
        self._key_color_edit.editingFinished.connect(self._on_matte_changed)
        row1.addWidget(self._key_color_edit)

        self._key_color_btn = QPushButton("Pick")
        self._key_color_btn.setMaximumWidth(40)
        self._key_color_btn.clicked.connect(self._on_pick_key_color)
        row1.addWidget(self._key_color_btn)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Threshold:"))
        self._threshold_spin = QDoubleSpinBox()
        self._threshold_spin.setRange(0.0, 1.0)
        self._threshold_spin.setSingleStep(0.01)
        self._threshold_spin.setValue(0.1)
        self._threshold_spin.editingFinished.connect(self._on_matte_changed)
        row2.addWidget(self._threshold_spin)

        row2.addWidget(QLabel("Similarity:"))
        self._similarity_spin = QDoubleSpinBox()
        self._similarity_spin.setRange(0.0, 1.0)
        self._similarity_spin.setSingleStep(0.01)
        self._similarity_spin.setValue(0.1)
        self._similarity_spin.editingFinished.connect(self._on_matte_changed)
        row2.addWidget(self._similarity_spin)

        row2.addWidget(QLabel("Blend:"))
        self._blend_spin = QDoubleSpinBox()
        self._blend_spin.setRange(0.0, 1.0)
        self._blend_spin.setSingleStep(0.01)
        self._blend_spin.editingFinished.connect(self._on_matte_changed)
        row2.addWidget(self._blend_spin)

        row2.addWidget(QLabel("Softness:"))
        self._softness_spin = QDoubleSpinBox()
        self._softness_spin.setRange(0.0, 1.0)
        self._softness_spin.setSingleStep(0.01)
        self._softness_spin.editingFinished.connect(self._on_matte_changed)
        row2.addWidget(self._softness_spin)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Erode:"))
        self._erode_spin = QSpinBox()
        self._erode_spin.setRange(0, 20)
        self._erode_spin.editingFinished.connect(self._on_matte_changed)
        row3.addWidget(self._erode_spin)

        row3.addWidget(QLabel("Dilate:"))
        self._dilate_spin = QSpinBox()
        self._dilate_spin.setRange(0, 20)
        self._dilate_spin.editingFinished.connect(self._on_matte_changed)
        row3.addWidget(self._dilate_spin)

        row3.addWidget(QLabel("Feather:"))
        self._feather_spin = QSpinBox()
        self._feather_spin.setRange(0, 20)
        self._feather_spin.editingFinished.connect(self._on_matte_changed)
        row3.addWidget(self._feather_spin)

        self._despill_cb = QCheckBox("Despill")
        self._despill_cb.toggled.connect(self._on_matte_changed)
        row3.addWidget(self._despill_cb)

        self._invert_cb = QCheckBox("Invert")
        self._invert_cb.toggled.connect(self._on_matte_changed)
        row3.addWidget(self._invert_cb)
        layout.addLayout(row3)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _build_audio_section(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Audio Sources")
        layout = QVBoxLayout()

        # Keep legacy combo hidden but present for backward compat in tests
        self._audio_combo = QComboBox()
        self._audio_combo.addItem("(none)")
        self._audio_combo.currentIndexChanged.connect(self._on_audio_source_changed)
        self._audio_combo.hide()
        layout.addWidget(self._audio_combo)

        self._audio_layer_list = QListWidget()
        self._audio_layer_list.currentRowChanged.connect(self._on_audio_layer_selected)
        layout.addWidget(self._audio_layer_list)

        btn_row = QHBoxLayout()
        self._add_audio_btn = QPushButton("Add Audio")
        self._add_audio_btn.clicked.connect(self._on_add_audio_layer)
        btn_row.addWidget(self._add_audio_btn)

        self._remove_audio_btn = QPushButton("Remove")
        self._remove_audio_btn.clicked.connect(self._on_remove_audio_layer)
        btn_row.addWidget(self._remove_audio_btn)

        self._browse_audio_btn = QPushButton("Browse...")
        self._browse_audio_btn.clicked.connect(self._on_browse_audio)
        btn_row.addWidget(self._browse_audio_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Audio layer editor (shown for selected audio layer)
        editor_row = QHBoxLayout()
        editor_row.addWidget(QLabel("Start (ms):"))
        self._audio_start_spin = QSpinBox()
        self._audio_start_spin.setRange(0, 999999999)
        self._audio_start_spin.editingFinished.connect(self._on_audio_layer_edited)
        editor_row.addWidget(self._audio_start_spin)

        editor_row.addWidget(QLabel("Duration (ms):"))
        self._audio_duration_spin = QSpinBox()
        self._audio_duration_spin.setRange(0, 999999999)
        self._audio_duration_spin.editingFinished.connect(self._on_audio_layer_edited)
        editor_row.addWidget(self._audio_duration_spin)

        self._audio_full_length_cb = QCheckBox("Full Length")
        self._audio_full_length_cb.setChecked(True)
        self._audio_full_length_cb.toggled.connect(self._on_audio_layer_edited)
        editor_row.addWidget(self._audio_full_length_cb)
        layout.addLayout(editor_row)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _build_preview_section(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Live Preview")
        layout = QVBoxLayout()

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Timestamp (ms):"))
        self._preview_time_spin = QSpinBox()
        self._preview_time_spin.setRange(0, 999999999)
        self._preview_time_spin.setValue(0)
        controls.addWidget(self._preview_time_spin)

        self._preview_refresh_btn = QPushButton("Refresh Preview")
        self._preview_refresh_btn.clicked.connect(self._on_refresh_preview)
        controls.addWidget(self._preview_refresh_btn)

        self._preview_status_label = QLabel("")
        controls.addWidget(self._preview_status_label)
        controls.addStretch()
        layout.addLayout(controls)

        self._preview_label = QLabel()
        self._preview_label.setMinimumHeight(200)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet("background: #1a1a1a; border: 1px solid #333;")
        self._preview_label.setText("Click 'Refresh Preview' to generate a frame")
        layout.addWidget(self._preview_label)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _build_output_section(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Output Settings")
        layout = QHBoxLayout()

        layout.addWidget(QLabel("Resolution:"))
        self._resolution_preset_combo = QComboBox()
        for key, label in RESOLUTION_PRESET_LABELS:
            self._resolution_preset_combo.addItem(label, key)
        self._resolution_preset_combo.currentIndexChanged.connect(
            self._on_resolution_preset_changed,
        )
        layout.addWidget(self._resolution_preset_combo)

        layout.addWidget(QLabel("Width:"))
        self._out_width_spin = QSpinBox()
        self._out_width_spin.setRange(128, 7680)
        self._out_width_spin.setValue(1920)
        self._out_width_spin.editingFinished.connect(self._on_output_settings_changed)
        layout.addWidget(self._out_width_spin)

        layout.addWidget(QLabel("Height:"))
        self._out_height_spin = QSpinBox()
        self._out_height_spin.setRange(128, 4320)
        self._out_height_spin.setValue(1080)
        self._out_height_spin.editingFinished.connect(self._on_output_settings_changed)
        layout.addWidget(self._out_height_spin)

        layout.addWidget(QLabel("FPS:"))
        self._out_fps_spin = QDoubleSpinBox()
        self._out_fps_spin.setRange(1.0, 120.0)
        self._out_fps_spin.setValue(30.0)
        self._out_fps_spin.setSingleStep(0.001)
        self._out_fps_spin.setDecimals(3)
        self._out_fps_spin.editingFinished.connect(self._on_output_settings_changed)
        layout.addWidget(self._out_fps_spin)

        layout.addWidget(QLabel("Output:"))
        self._output_path_edit = QLineEdit()
        self._output_path_edit.setPlaceholderText("output.mp4")
        layout.addWidget(self._output_path_edit, 1)

        self._browse_output_btn = QPushButton("Browse...")
        self._browse_output_btn.clicked.connect(self._on_browse_output)
        layout.addWidget(self._browse_output_btn)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _build_render_section(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Render")
        layout = QVBoxLayout()

        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("Start Render")
        self._start_btn.clicked.connect(self._on_start_render)
        btn_row.addWidget(self._start_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._on_cancel_render)
        btn_row.addWidget(self._cancel_btn)
        layout.addLayout(btn_row)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("Ready")
        layout.addWidget(self._status_label)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _build_timeline_section(self, parent_layout: QVBoxLayout) -> None:
        from audio_visualizer.ui.tabs.renderComposition.timelineWidget import TimelineWidget

        group = QGroupBox("Timeline")
        layout = QVBoxLayout()

        self._timeline = TimelineWidget()
        self._timeline.item_selected.connect(self._on_timeline_item_selected)
        self._timeline.item_moved.connect(self._on_timeline_item_moved)
        self._timeline.item_trimmed.connect(self._on_timeline_item_trimmed)
        layout.addWidget(self._timeline)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _refresh_timeline(self) -> None:
        """Rebuild timeline items from model."""
        from audio_visualizer.ui.tabs.renderComposition.timelineWidget import TimelineItem

        items: list[TimelineItem] = []
        for layer in self._model.layers:
            items.append(TimelineItem(
                item_id=layer.id,
                display_name=layer.display_name,
                start_ms=layer.start_ms,
                end_ms=layer.end_ms,
                track_type="visual",
                enabled=layer.enabled,
            ))
        for al in getattr(self._model, "audio_layers", []):
            items.append(TimelineItem(
                item_id=al.id,
                display_name=al.display_name,
                start_ms=al.start_ms,
                end_ms=al.start_ms + (
                    al.duration_ms
                    if not al.use_full_length and al.duration_ms > 0
                    else 5000
                ),
                track_type="audio",
                enabled=al.enabled,
            ))
        if hasattr(self, "_timeline"):
            self._timeline.set_items(items)

    def _on_timeline_item_selected(self, item_id: str) -> None:
        """Sync timeline selection with layer list."""
        if not item_id:
            return
        for i, layer in enumerate(self._model.layers):
            if layer.id == item_id:
                self._layer_list.setCurrentRow(i)
                return
        for i, al in enumerate(self._model.audio_layers):
            if al.id == item_id:
                self._audio_layer_list.setCurrentRow(i)
                return

    def _on_timeline_item_moved(self, item_id: str, new_start: int, new_end: int) -> None:
        """Handle timeline item drag."""
        layer = self._model.get_layer(item_id)
        if layer:
            layer.start_ms = new_start
            layer.end_ms = new_end
            self._refresh_layer_list()
            self._load_layer_properties(layer)
            self.settings_changed.emit()
            return
        al = self._model.get_audio_layer(item_id)
        if al:
            duration = new_end - new_start
            al.start_ms = new_start
            if not al.use_full_length:
                al.duration_ms = duration
            self._refresh_audio_layer_list()
            self._on_audio_layer_selected(self._audio_layer_list.currentRow())
            self.settings_changed.emit()

    def _on_timeline_item_trimmed(self, item_id: str, which: str, ms: int) -> None:
        """Handle timeline trim."""
        layer = self._model.get_layer(item_id)
        if layer:
            if which == "start":
                layer.start_ms = ms
            else:
                layer.end_ms = ms
            self._refresh_layer_list()
            self._load_layer_properties(layer)
            self.settings_changed.emit()
            return
        al = self._model.get_audio_layer(item_id)
        if al:
            if which == "start":
                al.start_ms = ms
            else:
                new_duration = max(0, ms - al.start_ms)
                al.duration_ms = new_duration
                al.use_full_length = False
            self._refresh_audio_layer_list()
            self._on_audio_layer_selected(self._audio_layer_list.currentRow())
            self.settings_changed.emit()

    # ------------------------------------------------------------------
    # Session context
    # ------------------------------------------------------------------

    def set_workspace_context(self, context: WorkspaceContext) -> None:
        super().set_workspace_context(context)
        context.asset_added.connect(self._refresh_asset_combos)
        context.asset_updated.connect(self._refresh_asset_combos)
        context.asset_removed.connect(self._refresh_asset_combos)
        self._refresh_asset_combos()

    def _refresh_asset_combos(self, _asset_id: str | None = None) -> None:
        """Rebuild source and audio combo boxes from session context."""
        self._updating_ui = True
        try:
            # Source combo (video/image assets)
            current_source = self._source_combo.currentText()
            self._source_combo.clear()
            self._source_combo.addItem("(none)")
            if self._workspace_context is not None:
                for asset in self._workspace_context.list_assets():
                    if asset.category in ("video", "image"):
                        self._source_combo.addItem(
                            f"{asset.display_name} [{asset.id[:8]}]",
                            asset.id,
                        )
            # Add direct-file entries for layers that use asset_path without asset_id
            seen_paths: set[str] = set()
            for layer in self._model.layers:
                if layer.asset_path and not layer.asset_id:
                    path_str = str(layer.asset_path)
                    if path_str not in seen_paths:
                        seen_paths.add(path_str)
                        self._source_combo.addItem(
                            f"File: {layer.asset_path.name}",
                            f"file:{path_str}",
                        )
            # Restore selection if still available
            idx = self._source_combo.findText(current_source)
            if idx >= 0:
                self._source_combo.setCurrentIndex(idx)

            # Audio combo
            current_audio = self._audio_combo.currentText()
            self._audio_combo.clear()
            self._audio_combo.addItem("(none)")
            if self._workspace_context is not None:
                for asset in self._workspace_context.list_assets():
                    if asset.category in ("audio", "video"):
                        label = f"{asset.display_name} [{asset.id[:8]}]"
                        self._audio_combo.addItem(label, asset.id)
            # Add direct-file entry for audio if set
            if self._model.audio_source_path and not self._model.audio_source_asset_id:
                file_data = f"file:{self._model.audio_source_path}"
                self._audio_combo.addItem(
                    f"File: {self._model.audio_source_path.name}",
                    file_data,
                )
            idx = self._audio_combo.findText(current_audio)
            if idx >= 0:
                self._audio_combo.setCurrentIndex(idx)
        finally:
            self._updating_ui = False

        # Refresh the audio layer list
        self._refresh_audio_layer_list()

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def _setup_shortcuts(self) -> None:
        """Set up keyboard shortcuts for undo/redo."""
        undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        undo_shortcut.activated.connect(self._on_undo)
        redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self)
        redo_shortcut.activated.connect(self._on_redo)

    def _on_undo(self) -> None:
        if self._undo_stack is not None and self._undo_stack.canUndo():
            self._undo_stack.undo()
            self._refresh_layer_list()
            self._refresh_audio_layer_list()
            layer = self._selected_layer()
            if layer is not None:
                self._load_layer_properties(layer)

    def _on_redo(self) -> None:
        if self._undo_stack is not None and self._undo_stack.canRedo():
            self._undo_stack.redo()
            self._refresh_layer_list()
            self._refresh_audio_layer_list()
            layer = self._selected_layer()
            if layer is not None:
                self._load_layer_properties(layer)

    # ------------------------------------------------------------------
    # Layer list management
    # ------------------------------------------------------------------

    def _refresh_layer_list(self) -> None:
        """Rebuild the layer list widget from the model."""
        self._updating_ui = True
        try:
            current_row = self._layer_list.currentRow()
            self._layer_list.clear()
            for layer in self._model.layers:
                prefix = "[x]" if layer.enabled else "[ ]"
                item = QListWidgetItem(f"{prefix} {layer.display_name} (z={layer.z_order})")
                item.setData(Qt.ItemDataRole.UserRole, layer.id)
                self._layer_list.addItem(item)
            if 0 <= current_row < self._layer_list.count():
                self._layer_list.setCurrentRow(current_row)
            elif self._layer_list.count() > 0:
                self._layer_list.setCurrentRow(0)
        finally:
            self._updating_ui = False
        self._refresh_timeline()

    def _selected_layer(self) -> CompositionLayer | None:
        """Return the currently selected layer, or None."""
        row = self._layer_list.currentRow()
        if row < 0 or row >= len(self._model.layers):
            return None
        return self._model.layers[row]

    def _on_layer_selected(self, row: int) -> None:
        """Update property panels when a layer is selected."""
        if self._updating_ui:
            return
        layer = self._selected_layer()
        if layer is None:
            return
        self._load_layer_properties(layer)

    def _load_layer_properties(self, layer: CompositionLayer) -> None:
        """Populate the right panel with *layer*'s properties."""
        self._updating_ui = True
        try:
            # Source
            if layer.asset_id:
                idx = self._source_combo.findData(layer.asset_id)
                if idx >= 0:
                    self._source_combo.setCurrentIndex(idx)
                else:
                    self._source_combo.setCurrentIndex(0)
            elif layer.asset_path:
                # Direct file-backed layer — find or add a combo entry
                file_data = f"file:{layer.asset_path}"
                idx = self._source_combo.findData(file_data)
                if idx < 0:
                    self._source_combo.addItem(
                        f"File: {layer.asset_path.name}", file_data
                    )
                    idx = self._source_combo.count() - 1
                self._source_combo.setCurrentIndex(idx)
            else:
                self._source_combo.setCurrentIndex(0)

            # Layer type
            idx = self._layer_type_combo.findText(layer.layer_type)
            if idx >= 0:
                self._layer_type_combo.setCurrentIndex(idx)

            # Enabled
            self._layer_enabled_cb.setChecked(layer.enabled)

            # Position & size
            self._x_spin.setValue(layer.x)
            self._y_spin.setValue(layer.y)
            self._w_spin.setValue(layer.width)
            self._h_spin.setValue(layer.height)
            self._z_spin.setValue(layer.z_order)

            # Timing
            self._start_ms_spin.setValue(layer.start_ms)
            self._end_ms_spin.setValue(layer.end_ms)
            idx = self._behavior_combo.findText(layer.behavior_after_end)
            if idx >= 0:
                self._behavior_combo.setCurrentIndex(idx)

            # Matte
            ms = layer.matte_settings
            idx = self._matte_mode_combo.findText(ms.get("mode", "none"))
            if idx >= 0:
                self._matte_mode_combo.setCurrentIndex(idx)
            self._key_color_edit.setText(ms.get("key_target", "#00FF00"))
            self._threshold_spin.setValue(ms.get("threshold", 0.1))
            self._similarity_spin.setValue(ms.get("similarity", 0.1))
            self._blend_spin.setValue(ms.get("blend", 0.0))
            self._softness_spin.setValue(ms.get("softness", 0.0))
            self._erode_spin.setValue(ms.get("erode", 0))
            self._dilate_spin.setValue(ms.get("dilate", 0))
            self._feather_spin.setValue(ms.get("feather", 0))
            self._despill_cb.setChecked(ms.get("despill", False))
            self._invert_cb.setChecked(ms.get("invert", False))
        finally:
            self._updating_ui = False

    # ------------------------------------------------------------------
    # Layer actions
    # ------------------------------------------------------------------

    def _on_add_layer(self) -> None:
        layer = CompositionLayer(
            display_name=f"Layer {len(self._model.layers) + 1}",
            layer_type="custom",
            width=self._model.output_width,
            height=self._model.output_height,
            z_order=len(self._model.layers),
        )
        cmd = AddLayerCommand(self._model, layer)
        self._push_command(cmd)
        self._refresh_layer_list()
        self._layer_list.setCurrentRow(self._layer_list.count() - 1)
        self.settings_changed.emit()

    def _on_remove_layer(self) -> None:
        layer = self._selected_layer()
        if layer is None:
            return
        cmd = RemoveLayerCommand(self._model, layer.id)
        self._push_command(cmd)
        self._refresh_layer_list()
        self.settings_changed.emit()

    def _on_move_up(self) -> None:
        layer = self._selected_layer()
        if layer is None:
            return
        new_z = max(0, layer.z_order - 1)
        if new_z != layer.z_order:
            cmd = ReorderLayerCommand(self._model, layer.id, new_z)
            self._push_command(cmd)
            self._refresh_layer_list()
            self.settings_changed.emit()

    def _on_move_down(self) -> None:
        layer = self._selected_layer()
        if layer is None:
            return
        new_z = layer.z_order + 1
        cmd = ReorderLayerCommand(self._model, layer.id, new_z)
        self._push_command(cmd)
        self._refresh_layer_list()
        self.settings_changed.emit()

    # ------------------------------------------------------------------
    # Source / type changes
    # ------------------------------------------------------------------

    def _on_source_changed(self, index: int) -> None:
        if self._updating_ui:
            return
        layer = self._selected_layer()
        if layer is None:
            return

        data = self._source_combo.currentData()
        asset_id: str | None = None
        asset_path: Path | None = None

        if data and isinstance(data, str):
            if data.startswith("file:"):
                asset_path = Path(data[5:])
            elif self._workspace_context:
                asset_id = data
                asset = self._workspace_context.get_asset(asset_id)
                if asset:
                    asset_path = asset.path

        cmd = ChangeSourceCommand(self._model, layer.id, asset_id, asset_path)
        self._push_command(cmd)
        self.settings_changed.emit()

    def _on_browse_source(self) -> None:
        layer = self._selected_layer()
        if layer is None:
            return
        path = self._pick_session_or_file(None, "Select Source", _VIDEO_FILTERS)
        if path is not None:
            cmd = ChangeSourceCommand(self._model, layer.id, None, path)
            self._push_command(cmd)
            # Refresh to show the direct file in the source combo
            self._load_layer_properties(layer)
            self.settings_changed.emit()

    def _on_layer_type_changed(self, text: str) -> None:
        if self._updating_ui:
            return
        layer = self._selected_layer()
        if layer is None:
            return
        layer.layer_type = text
        self.settings_changed.emit()

    def _on_layer_enabled_changed(self, checked: bool) -> None:
        if self._updating_ui:
            return
        layer = self._selected_layer()
        if layer is None:
            return
        layer.enabled = checked
        self._refresh_layer_list()
        self.settings_changed.emit()

    # ------------------------------------------------------------------
    # Position / size / z-order changes
    # ------------------------------------------------------------------

    def _on_position_changed(self) -> None:
        if self._updating_ui:
            return
        layer = self._selected_layer()
        if layer is None:
            return
        new_x = self._x_spin.value()
        new_y = self._y_spin.value()
        if new_x != layer.x or new_y != layer.y:
            cmd = MoveLayerCommand(self._model, layer.id, new_x, new_y)
            self._push_command(cmd)
            self.settings_changed.emit()

    def _on_size_changed(self) -> None:
        if self._updating_ui:
            return
        layer = self._selected_layer()
        if layer is None:
            return
        new_w = self._w_spin.value()
        new_h = self._h_spin.value()
        if new_w != layer.width or new_h != layer.height:
            cmd = ResizeLayerCommand(self._model, layer.id, new_w, new_h)
            self._push_command(cmd)
            self.settings_changed.emit()

    def _on_z_order_changed(self) -> None:
        if self._updating_ui:
            return
        layer = self._selected_layer()
        if layer is None:
            return
        new_z = self._z_spin.value()
        if new_z != layer.z_order:
            cmd = ReorderLayerCommand(self._model, layer.id, new_z)
            self._push_command(cmd)
            self._refresh_layer_list()
            self.settings_changed.emit()

    # ------------------------------------------------------------------
    # Timing changes
    # ------------------------------------------------------------------

    def _on_timing_changed(self) -> None:
        if self._updating_ui:
            return
        layer = self._selected_layer()
        if layer is None:
            return
        layer.start_ms = self._start_ms_spin.value()
        layer.end_ms = self._end_ms_spin.value()
        self._refresh_timeline()
        self.settings_changed.emit()

    def _on_behavior_changed(self, text: str) -> None:
        if self._updating_ui:
            return
        layer = self._selected_layer()
        if layer is None:
            return
        layer.behavior_after_end = text
        self.settings_changed.emit()

    # ------------------------------------------------------------------
    # Matte changes
    # ------------------------------------------------------------------

    def _on_matte_changed(self, *_args: Any) -> None:
        if self._updating_ui:
            return
        layer = self._selected_layer()
        if layer is None:
            return
        layer.matte_settings = {
            "mode": self._matte_mode_combo.currentText(),
            "key_target": self._key_color_edit.text(),
            "threshold": self._threshold_spin.value(),
            "similarity": self._similarity_spin.value(),
            "blend": self._blend_spin.value(),
            "softness": self._softness_spin.value(),
            "erode": self._erode_spin.value(),
            "dilate": self._dilate_spin.value(),
            "feather": self._feather_spin.value(),
            "despill": self._despill_cb.isChecked(),
            "invert": self._invert_cb.isChecked(),
        }
        self.settings_changed.emit()

    def _on_pick_key_color(self) -> None:
        from PySide6.QtGui import QColor
        current = QColor(self._key_color_edit.text())
        color = QColorDialog.getColor(current, self, "Select Key Color")
        if color.isValid():
            self._key_color_edit.setText(color.name())
            self._on_matte_changed()

    # ------------------------------------------------------------------
    # Audio source (legacy combo — kept for backward compat)
    # ------------------------------------------------------------------

    def _on_audio_source_changed(self, index: int) -> None:
        if self._updating_ui:
            return
        data = self._audio_combo.currentData()
        asset_id: str | None = None
        audio_path: Path | None = None

        if data and isinstance(data, str):
            if data.startswith("file:"):
                audio_path = Path(data[5:])
            elif self._workspace_context:
                asset_id = data
                asset = self._workspace_context.get_asset(asset_id)
                if asset:
                    audio_path = asset.path

        cmd = ChangeAudioSourceCommand(self._model, asset_id, audio_path)
        self._push_command(cmd)
        self.settings_changed.emit()

    # ------------------------------------------------------------------
    # Audio layer management
    # ------------------------------------------------------------------

    def _refresh_audio_layer_list(self) -> None:
        """Rebuild the audio layer list widget from the model."""
        self._updating_ui = True
        try:
            current_row = self._audio_layer_list.currentRow()
            self._audio_layer_list.clear()
            for al in self._model.audio_layers:
                prefix = "[x]" if al.enabled else "[ ]"
                item = QListWidgetItem(f"{prefix} {al.display_name}")
                item.setData(Qt.ItemDataRole.UserRole, al.id)
                self._audio_layer_list.addItem(item)
            if 0 <= current_row < self._audio_layer_list.count():
                self._audio_layer_list.setCurrentRow(current_row)
            elif self._audio_layer_list.count() > 0:
                self._audio_layer_list.setCurrentRow(0)
        finally:
            self._updating_ui = False
        self._refresh_timeline()

    def _selected_audio_layer(self) -> CompositionAudioLayer | None:
        """Return the currently selected audio layer, or None."""
        row = self._audio_layer_list.currentRow()
        if row < 0 or row >= len(self._model.audio_layers):
            return None
        return self._model.audio_layers[row]

    def _on_audio_layer_selected(self, row: int) -> None:
        """Update editor controls when an audio layer is selected."""
        if self._updating_ui:
            return
        al = self._selected_audio_layer()
        if al is None:
            return
        self._load_audio_layer_properties(al)

    def _load_audio_layer_properties(self, al: CompositionAudioLayer) -> None:
        """Populate audio layer editor controls."""
        self._updating_ui = True
        try:
            self._audio_start_spin.setValue(al.start_ms)
            self._audio_duration_spin.setValue(al.duration_ms)
            self._audio_full_length_cb.setChecked(al.use_full_length)
        finally:
            self._updating_ui = False

    def _on_add_audio_layer(self) -> None:
        """Add a new empty audio layer."""
        al = CompositionAudioLayer(
            display_name=f"Audio {len(self._model.audio_layers) + 1}",
        )
        cmd = AddAudioLayerCommand(self._model, al)
        self._push_command(cmd)
        self._refresh_audio_layer_list()
        self._audio_layer_list.setCurrentRow(self._audio_layer_list.count() - 1)
        self.settings_changed.emit()

    def _on_remove_audio_layer(self) -> None:
        """Remove the selected audio layer."""
        al = self._selected_audio_layer()
        if al is None:
            return
        cmd = RemoveAudioLayerCommand(self._model, al.id)
        self._push_command(cmd)
        self._refresh_audio_layer_list()
        self.settings_changed.emit()

    def _on_audio_layer_edited(self, *_args: Any) -> None:
        """Apply edits from the audio layer editor to the selected layer."""
        if self._updating_ui:
            return
        al = self._selected_audio_layer()
        if al is None:
            return
        cmd = EditAudioLayerCommand(
            self._model,
            al.id,
            start_ms=self._audio_start_spin.value(),
            duration_ms=self._audio_duration_spin.value(),
            use_full_length=self._audio_full_length_cb.isChecked(),
        )
        self._push_command(cmd)
        self.settings_changed.emit()

    def _on_browse_audio(self) -> None:
        path = self._pick_session_or_file(None, "Select Audio Source", _AUDIO_FILTERS)
        if path is not None:
            # If an audio layer is selected, update it; otherwise add a new one
            al = self._selected_audio_layer()
            if al is not None:
                cmd = EditAudioLayerCommand(
                    self._model,
                    al.id,
                    asset_path=path,
                    display_name=path.name,
                )
                self._push_command(cmd)
                self._refresh_audio_layer_list()
            else:
                new_al = CompositionAudioLayer(
                    display_name=path.name,
                    asset_path=path,
                )
                cmd_add = AddAudioLayerCommand(self._model, new_al)
                self._push_command(cmd_add)
                self._refresh_audio_layer_list()
                self._audio_layer_list.setCurrentRow(
                    self._audio_layer_list.count() - 1
                )
            # Also update legacy fields for backward compat
            self._model.audio_source_path = path
            self._model.audio_source_asset_id = None
            # Update hidden legacy combo
            self._updating_ui = True
            try:
                file_data = f"file:{path}"
                idx = self._audio_combo.findData(file_data)
                if idx < 0:
                    self._audio_combo.addItem(f"File: {path.name}", file_data)
                    idx = self._audio_combo.count() - 1
                self._audio_combo.setCurrentIndex(idx)
            finally:
                self._updating_ui = False
            self.settings_changed.emit()

    def _pick_session_or_file(
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

    # ------------------------------------------------------------------
    # Output settings
    # ------------------------------------------------------------------

    def _on_output_settings_changed(self) -> None:
        if self._updating_ui:
            return
        self._model.output_width = self._out_width_spin.value()
        self._model.output_height = self._out_height_spin.value()
        self._model.output_fps = self._out_fps_spin.value()
        # Check if current values match any preset
        matched = False
        for key, (pw, ph) in RESOLUTION_PRESETS.items():
            if self._model.output_width == pw and self._model.output_height == ph:
                self._updating_ui = True
                idx = self._resolution_preset_combo.findData(key)
                if idx >= 0:
                    self._resolution_preset_combo.setCurrentIndex(idx)
                self._model.resolution_preset = key
                self._updating_ui = False
                matched = True
                break
        if not matched:
            self._updating_ui = True
            idx = self._resolution_preset_combo.findData("custom")
            if idx >= 0:
                self._resolution_preset_combo.setCurrentIndex(idx)
            self._model.resolution_preset = "custom"
            self._updating_ui = False
        self.settings_changed.emit()

    def _on_resolution_preset_changed(self, index: int) -> None:
        if self._updating_ui:
            return
        key = self._resolution_preset_combo.currentData()
        if key and key != "custom" and key in RESOLUTION_PRESETS:
            w, h = RESOLUTION_PRESETS[key]
            self._updating_ui = True
            self._out_width_spin.setValue(w)
            self._out_height_spin.setValue(h)
            self._model.output_width = w
            self._model.output_height = h
            self._model.resolution_preset = key
            self._updating_ui = False
            self.settings_changed.emit()
        elif key == "custom":
            self._model.resolution_preset = "custom"

    def _on_browse_output(self) -> None:
        from audio_visualizer.ui.sessionFilePicker import resolve_browse_directory
        start_dir = resolve_browse_directory(
            self._output_path_edit.text(), self.workspace_context
        )
        path, _ = QFileDialog.getSaveFileName(self, "Save Output", start_dir, _OUTPUT_FILTERS)
        if path:
            self._output_path_edit.setText(path)

    # ------------------------------------------------------------------
    # Live preview
    # ------------------------------------------------------------------

    def _on_refresh_preview(self) -> None:
        """Generate a single-frame preview at the selected timestamp."""
        valid, msg = self.validate_settings()
        if not valid:
            self._preview_status_label.setText(f"Cannot preview: {msg}")
            return

        self._preview_refresh_btn.setEnabled(False)
        self._preview_status_label.setText("Generating preview...")

        timestamp_ms = self._preview_time_spin.value()
        timestamp_s = timestamp_ms / 1000.0

        worker = _PreviewWorker(copy.deepcopy(self._model), timestamp_s)
        worker.signals.finished.connect(self._on_preview_finished)
        worker.signals.failed.connect(self._on_preview_failed)

        mw = self._main_window
        if mw and hasattr(mw, "render_thread_pool"):
            mw.render_thread_pool.start(worker)
        else:
            QThreadPool.globalInstance().start(worker)

    def _on_preview_finished(self, image_path: str) -> None:
        """Display the generated preview frame."""
        self._preview_refresh_btn.setEnabled(True)
        self._preview_status_label.setText("")

        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self._preview_status_label.setText("Failed to load preview image")
            return

        # Scale to fit the label while preserving aspect ratio
        scaled = pixmap.scaled(
            self._preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview_label.setPixmap(scaled)

    def _on_preview_failed(self, error: str) -> None:
        """Handle preview generation failure."""
        self._preview_refresh_btn.setEnabled(True)
        self._preview_status_label.setText(f"Preview failed: {error}")

    # ------------------------------------------------------------------
    # Presets
    # ------------------------------------------------------------------

    def _on_apply_preset(self) -> None:
        name = self._preset_combo.currentText()
        if name == "(none)":
            return
        try:
            layers = get_preset(name, self._model.output_width, self._model.output_height)
        except ValueError as exc:
            logger.warning("Failed to load preset: %s", exc)
            return
        cmd = ApplyPresetCommand(self._model, layers, name)
        self._push_command(cmd)
        self._refresh_layer_list()
        self.settings_changed.emit()

    # ------------------------------------------------------------------
    # Render lifecycle
    # ------------------------------------------------------------------

    def _on_start_render(self) -> None:
        valid, msg = self.validate_settings()
        if not valid:
            QMessageBox.warning(self, "Validation Error", msg)
            return

        mw = self._main_window
        if mw and hasattr(mw, "try_start_job"):
            if not mw.try_start_job(self.tab_id):
                return

        output_path = self._output_path_edit.text().strip()
        if not output_path:
            from audio_visualizer.ui.sessionFilePicker import resolve_output_directory

            default_parent = resolve_output_directory(
                workspace_context=self.workspace_context,
            )
            output_path = str(default_parent / "composition_output.mp4")
        elif not Path(output_path).suffix:
            output_path = output_path + ".mp4"

        self._start_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self._progress_bar.setValue(0)
        self._status_label.setText("Starting render...")

        from audio_visualizer.ui.workers.compositionWorker import CompositionWorker

        worker = CompositionWorker(self._model, output_path)
        worker.signals.progress.connect(self._on_render_progress)
        worker.signals.completed.connect(self._on_render_completed)
        worker.signals.failed.connect(self._on_render_failed)
        worker.signals.canceled.connect(self._on_render_canceled)
        self._active_worker = worker

        if mw and hasattr(mw, "render_thread_pool"):
            mw.render_thread_pool.start(worker)
        else:
            pool = QThreadPool.globalInstance()
            pool.start(worker)

        if mw and hasattr(mw, "show_job_status"):
            mw.show_job_status("composition", self.tab_id, "Rendering composition...")

    def _on_cancel_render(self) -> None:
        if self._active_worker and hasattr(self._active_worker, "cancel"):
            self._active_worker.cancel()

    def cancel_job(self) -> None:
        """Called by MainWindow when cancel is requested from job status."""
        self._on_cancel_render()

    def _on_render_progress(self, percent: float, message: str, data: dict) -> None:
        if percent >= 0:
            self._progress_bar.setValue(int(percent))
        self._status_label.setText(message or f"Rendering... {percent:.0f}%")

        mw = self._main_window
        if mw and hasattr(mw, "update_job_progress"):
            mw.update_job_progress(percent, message)

    def _on_render_completed(self, data: dict) -> None:
        self._start_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._progress_bar.setValue(100)

        output_path = data.get("output_path", "")
        self._status_label.setText(f"Render complete: {output_path}")

        # Register as session asset
        if output_path and self._workspace_context:
            asset = SessionAsset(
                id=str(uuid.uuid4()),
                display_name="Composition Output",
                path=Path(output_path),
                category="video",
                source_tab=self.tab_id,
                role="final_render",
                width=self._model.output_width,
                height=self._model.output_height,
                fps=self._model.output_fps,
                duration_ms=self._model.get_duration_ms(),
                has_audio=(
                    self._model.audio_source_path is not None
                    or any(al.enabled and al.asset_path for al in self._model.audio_layers)
                ),
                metadata={
                    "audio_source_asset_id": self._model.audio_source_asset_id,
                    "layer_count": len(self._model.layers),
                    "audio_layer_count": len(self._model.audio_layers),
                    "export_profile": "ffmpeg_filter_complex",
                },
            )
            self.register_output_asset(asset)

        mw = self._main_window
        if mw and hasattr(mw, "show_job_completed"):
            mw.show_job_completed(
                "Composition render complete.",
                output_path,
                self.tab_id,
            )
        self._active_worker = None

    def _on_render_failed(self, error: str, data: dict) -> None:
        self._start_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._status_label.setText(f"Render failed: {error}")

        mw = self._main_window
        if mw and hasattr(mw, "show_job_failed"):
            mw.show_job_failed(error, self.tab_id)
        self._active_worker = None

    def _on_render_canceled(self, message: str) -> None:
        self._start_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._status_label.setText("Render canceled.")
        self._progress_bar.setValue(0)

        mw = self._main_window
        if mw and hasattr(mw, "show_job_canceled"):
            mw.show_job_canceled("Composition render canceled.", self.tab_id)
        self._active_worker = None

    # ------------------------------------------------------------------
    # Global busy state
    # ------------------------------------------------------------------

    def set_global_busy(self, is_busy: bool, owner_tab_id: str | None = None) -> None:
        if is_busy and owner_tab_id != self.tab_id:
            self._start_btn.setEnabled(False)
        elif not is_busy:
            self._start_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # Settings contract
    # ------------------------------------------------------------------

    def validate_settings(self) -> tuple[bool, str]:
        enabled_layers = [l for l in self._model.layers if l.enabled]
        if not enabled_layers:
            return False, "No enabled layers in the composition."

        # Check that at least one layer has a source
        has_source = any(
            l.asset_path is not None or l.asset_id is not None
            for l in enabled_layers
        )
        if not has_source:
            return False, "No layers have a source assigned."

        return True, ""

    def collect_settings(self) -> dict[str, Any]:
        return {
            "model": self._model.to_dict(),
            "output_path": self._output_path_edit.text(),
            "preset": self._preset_combo.currentText(),
        }

    def apply_settings(self, data: dict[str, Any]) -> None:
        model_data = data.get("model")
        if model_data:
            self._model = CompositionModel.from_dict(model_data)
            self._refresh_layer_list()
            self._refresh_asset_combos()
            self._sync_output_ui()
            self._refresh_timeline()
            current_layer = self._selected_layer()
            if current_layer is not None:
                self._load_layer_properties(current_layer)

        output_path = data.get("output_path", "")
        if output_path:
            self._output_path_edit.setText(output_path)

        preset = data.get("preset", "(none)")
        idx = self._preset_combo.findText(preset)
        if idx >= 0:
            self._preset_combo.setCurrentIndex(idx)

    def _sync_output_ui(self) -> None:
        """Synchronize output spinboxes with the model."""
        self._updating_ui = True
        try:
            self._out_width_spin.setValue(self._model.output_width)
            self._out_height_spin.setValue(self._model.output_height)
            self._out_fps_spin.setValue(self._model.output_fps)
            if hasattr(self, "_resolution_preset_combo"):
                idx = self._resolution_preset_combo.findData(
                    self._model.resolution_preset,
                )
                if idx >= 0:
                    self._resolution_preset_combo.setCurrentIndex(idx)
        finally:
            self._updating_ui = False


# ----------------------------------------------------------------------
# Preview worker
# ----------------------------------------------------------------------

class _PreviewSignals(QObject):
    """Signals for the preview worker."""

    finished = Signal(str)   # image path
    failed = Signal(str)     # error message


class _PreviewWorker(QRunnable):
    """QRunnable that extracts a single preview frame via FFmpeg."""

    def __init__(self, model: CompositionModel, timestamp_s: float) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._model = model
        self._timestamp_s = timestamp_s
        self.signals = _PreviewSignals()

    def run(self) -> None:
        try:
            import shutil

            if shutil.which("ffmpeg") is None:
                self.signals.failed.emit("FFmpeg not found on PATH.")
                return

            from audio_visualizer.ui.tabs.renderComposition.filterGraph import (
                build_preview_command,
            )

            # Use a temp file for the preview image
            tmp = tempfile.NamedTemporaryFile(
                suffix=".png", prefix="comp_preview_", delete=False
            )
            tmp.close()

            cmd = build_preview_command(self._model, self._timestamp_s, tmp.name)
            logger.debug("Preview command: %s", " ".join(cmd))

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                stderr = result.stderr[-500:] if result.stderr else ""
                self.signals.failed.emit(
                    f"FFmpeg exited with code {result.returncode}: {stderr}"
                )
                return

            if not Path(tmp.name).exists() or Path(tmp.name).stat().st_size == 0:
                self.signals.failed.emit("Preview frame was not generated.")
                return

            self.signals.finished.emit(tmp.name)

        except subprocess.TimeoutExpired:
            self.signals.failed.emit("Preview generation timed out.")
        except Exception as exc:
            self.signals.failed.emit(str(exc))
