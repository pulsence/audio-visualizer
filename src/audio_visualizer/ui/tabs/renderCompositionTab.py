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

from PySide6.QtCore import QEvent, QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QCursor, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollBar,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
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
    CompositionAudioLayer,
    CompositionLayer,
    CompositionModel,
)
from audio_visualizer.ui.tabs.renderComposition.presets import (
    get_preset,
    list_presets,
    save_preset,
)

logger = logging.getLogger(__name__)

_ASSET_FILTERS = (
    "All media (*.mp4 *.mkv *.webm *.avi *.mov *.mxf *.png *.jpg *.jpeg *.bmp *.tiff "
    "*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.wma);;"
    "Video files (*.mp4 *.mkv *.webm *.avi *.mov *.mxf);;"
    "Image files (*.png *.jpg *.jpeg *.bmp *.tiff);;"
    "Audio files (*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.wma);;"
    "All files (*)"
)

_AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma"}
_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".mxf"}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}

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
        self._picking_key_color = False

        self._init_undo_stack(100)
        self._build_ui()
        self._setup_shortcuts()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(8, 8, 8, 8)

        # ── Upper splitter: left column + live preview ──
        upper_splitter = QSplitter(Qt.Orientation.Horizontal)

        # -- Left column --
        left_column = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)

        # "Loaded Assets" group
        asset_group = QGroupBox("Loaded Assets")
        asset_inner = QVBoxLayout()

        self._layer_list = QListWidget()
        self._layer_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._layer_list.currentRowChanged.connect(self._on_layer_selected)
        self._layer_list.model().rowsMoved.connect(self._on_layer_list_reordered)
        asset_inner.addWidget(self._layer_list)

        btn_row = QHBoxLayout()
        self._add_asset_btn = QPushButton("Add Asset")
        self._add_asset_btn.clicked.connect(self._on_add_asset)
        btn_row.addWidget(self._add_asset_btn)

        self._remove_layer_btn = QPushButton("Remove")
        self._remove_layer_btn.clicked.connect(self._on_remove_layer)
        btn_row.addWidget(self._remove_layer_btn)

        asset_inner.addLayout(btn_row)

        # Preset selector inside loaded-assets group
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))
        self._preset_combo = QComboBox()
        self._refresh_preset_combo()
        preset_row.addWidget(self._preset_combo, 1)

        self._apply_preset_btn = QPushButton("Apply")
        self._apply_preset_btn.clicked.connect(self._on_apply_preset)
        preset_row.addWidget(self._apply_preset_btn)

        self._save_preset_btn = QPushButton("Save Preset")
        self._save_preset_btn.clicked.connect(self._on_save_preset)
        preset_row.addWidget(self._save_preset_btn)
        asset_inner.addLayout(preset_row)

        asset_group.setLayout(asset_inner)
        left_layout.addWidget(asset_group)

        # "Layer Settings" group with QStackedWidget
        settings_group = QGroupBox("Layer Settings")
        settings_inner = QVBoxLayout()

        self._settings_stack = QStackedWidget()

        # Page 0: visual settings
        visual_page = QWidget()
        visual_layout = QVBoxLayout()
        visual_layout.setContentsMargins(0, 0, 0, 0)
        self._build_source_section(visual_layout)
        self._build_position_section(visual_layout)
        self._build_timing_section(visual_layout)
        self._build_matte_section(visual_layout)
        visual_layout.addStretch(1)
        visual_page.setLayout(visual_layout)
        self._settings_stack.addWidget(visual_page)  # index 0

        # Page 1: audio settings
        audio_page = QWidget()
        audio_layout = QVBoxLayout()
        audio_layout.setContentsMargins(0, 0, 0, 0)
        self._build_audio_settings_page(audio_layout)
        audio_layout.addStretch(1)
        audio_page.setLayout(audio_layout)
        self._settings_stack.addWidget(audio_page)  # index 1

        settings_inner.addWidget(self._settings_stack)
        settings_group.setLayout(settings_inner)
        left_layout.addWidget(settings_group)

        left_column.setLayout(left_layout)
        upper_splitter.addWidget(left_column)

        # -- Right column: Live Preview --
        preview_group = QGroupBox("Live Preview")
        preview_layout = QVBoxLayout()

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
        preview_layout.addLayout(controls)

        self._preview_time_spin.valueChanged.connect(self._on_preview_time_changed)

        # Preview tabs: Timeline and Layer
        self._preview_tabs = QTabWidget()

        self._timeline_preview_label = QLabel()
        self._timeline_preview_label.setMinimumSize(400, 300)
        self._timeline_preview_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding,
        )
        self._timeline_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._timeline_preview_label.setStyleSheet("background: #1a1a1a; border: 1px solid #333;")
        self._timeline_preview_label.setText("Click 'Refresh Preview' to generate a frame")
        self._preview_tabs.addTab(self._timeline_preview_label, "Timeline")

        self._layer_preview_label = QLabel()
        self._layer_preview_label.setMinimumSize(400, 300)
        self._layer_preview_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding,
        )
        self._layer_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layer_preview_label.setStyleSheet("background: #1a1a1a; border: 1px solid #333;")
        self._layer_preview_label.setText("Select a visual layer to preview.")
        self._preview_tabs.addTab(self._layer_preview_label, "Layer")

        # For backward compat with pick-from-preview, point _preview_label at timeline tab
        self._preview_label = self._timeline_preview_label
        self._preview_label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        preview_layout.addWidget(self._preview_tabs)

        preview_group.setLayout(preview_layout)
        upper_splitter.addWidget(preview_group)

        upper_splitter.setSizes([400, 500])
        root_layout.addWidget(upper_splitter, 0)

        # ── Timeline (full width, expands) ──
        self._build_timeline_section(root_layout)

        # ── Render (compact, full width) ──
        self._build_render_section(root_layout)

        self.setLayout(root_layout)

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _build_source_section(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Source")
        layout = QVBoxLayout()

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Name:"))
        self._layer_name_edit = QLineEdit()
        self._layer_name_edit.editingFinished.connect(self._on_layer_name_changed)
        row1.addWidget(self._layer_name_edit, 1)

        self._layer_enabled_cb = QCheckBox("Enabled")
        self._layer_enabled_cb.setChecked(True)
        self._layer_enabled_cb.toggled.connect(self._on_layer_enabled_changed)
        row1.addWidget(self._layer_enabled_cb)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        self._source_combo = QComboBox()
        self._source_combo.addItem("(none)")
        self._source_combo.currentIndexChanged.connect(self._on_source_changed)
        row2.addWidget(self._source_combo, 1)

        self._browse_source_btn = QPushButton("Browse...")
        self._browse_source_btn.clicked.connect(self._on_browse_source)
        row2.addWidget(self._browse_source_btn)
        layout.addLayout(row2)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _build_position_section(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Position && Size")
        grid = QGridLayout()

        # Row 0: X, Y
        grid.addWidget(QLabel("X:"), 0, 0)
        self._x_spin = QSpinBox()
        self._x_spin.setRange(-9999, 9999)
        self._x_spin.editingFinished.connect(self._on_position_changed)
        grid.addWidget(self._x_spin, 0, 1)

        grid.addWidget(QLabel("Y:"), 0, 2)
        self._y_spin = QSpinBox()
        self._y_spin.setRange(-9999, 9999)
        self._y_spin.editingFinished.connect(self._on_position_changed)
        grid.addWidget(self._y_spin, 0, 3)

        # Row 1: W, H, Lock Ratio
        grid.addWidget(QLabel("W:"), 1, 0)
        self._w_spin = QSpinBox()
        self._w_spin.setRange(1, 9999)
        self._w_spin.setValue(1920)
        self._w_spin.editingFinished.connect(self._on_size_changed)
        grid.addWidget(self._w_spin, 1, 1)

        grid.addWidget(QLabel("H:"), 1, 2)
        self._h_spin = QSpinBox()
        self._h_spin.setRange(1, 9999)
        self._h_spin.setValue(1080)
        self._h_spin.editingFinished.connect(self._on_size_changed)
        grid.addWidget(self._h_spin, 1, 3)

        self._lock_ratio_cb = QCheckBox("Lock Ratio")
        self._lock_ratio_cb.setChecked(True)
        grid.addWidget(self._lock_ratio_cb, 1, 4)

        # Row 2: Z, Original Size, Fit to Output
        grid.addWidget(QLabel("Z:"), 2, 0)
        self._z_spin = QSpinBox()
        self._z_spin.setRange(0, 999)
        self._z_spin.editingFinished.connect(self._on_z_order_changed)
        grid.addWidget(self._z_spin, 2, 1)

        self._original_size_btn = QPushButton("Original Size")
        self._original_size_btn.clicked.connect(self._on_original_size)
        grid.addWidget(self._original_size_btn, 2, 2)

        self._fit_to_output_btn = QPushButton("Fit to Output")
        self._fit_to_output_btn.clicked.connect(self._on_fit_to_output)
        grid.addWidget(self._fit_to_output_btn, 2, 3)

        group.setLayout(grid)
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

        self._visual_full_length_cb = QCheckBox("Full Length")
        self._visual_full_length_cb.setVisible(False)  # shown only for video layers
        self._visual_full_length_cb.toggled.connect(self._on_visual_full_length_toggled)
        layout.addWidget(self._visual_full_length_cb)

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

        self._pick_from_preview_btn = QPushButton("Pick from Preview")
        self._pick_from_preview_btn.clicked.connect(self._on_pick_key_from_preview)
        row1.addWidget(self._pick_from_preview_btn)

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

    def _build_audio_settings_page(self, parent_layout: QVBoxLayout) -> None:
        """Build the audio settings controls for page 1 of the stacked widget."""
        group = QGroupBox("Audio Layer Settings")
        form = QFormLayout()

        # Name
        self._audio_name_edit = QLineEdit()
        self._audio_name_edit.editingFinished.connect(self._on_audio_name_changed)
        form.addRow("Name:", self._audio_name_edit)

        # Source
        source_row = QHBoxLayout()
        self._audio_source_label = QLabel("(none)")
        source_row.addWidget(self._audio_source_label, 1)
        self._browse_audio_btn = QPushButton("Browse...")
        self._browse_audio_btn.clicked.connect(self._on_browse_audio)
        source_row.addWidget(self._browse_audio_btn)
        form.addRow("Source:", source_row)

        # Start
        self._audio_start_spin = QSpinBox()
        self._audio_start_spin.setRange(0, 999999999)
        self._audio_start_spin.editingFinished.connect(self._on_audio_layer_edited)
        form.addRow("Start (ms):", self._audio_start_spin)

        # Duration + Full Length
        dur_row = QHBoxLayout()
        self._audio_duration_spin = QSpinBox()
        self._audio_duration_spin.setRange(0, 999999999)
        self._audio_duration_spin.editingFinished.connect(self._on_audio_layer_edited)
        dur_row.addWidget(self._audio_duration_spin)
        self._audio_full_length_cb = QCheckBox("Full Length")
        self._audio_full_length_cb.setChecked(True)
        self._audio_full_length_cb.toggled.connect(self._on_audio_full_length_toggled)
        dur_row.addWidget(self._audio_full_length_cb)
        form.addRow("Duration (ms):", dur_row)

        # Volume
        vol_row = QHBoxLayout()
        self._audio_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._audio_volume_slider.setRange(0, 200)
        self._audio_volume_slider.setValue(100)
        self._audio_volume_slider.setTickInterval(10)
        self._audio_volume_slider.valueChanged.connect(self._on_audio_volume_changed)
        vol_row.addWidget(self._audio_volume_slider, 1)
        self._audio_volume_label = QLabel("100%")
        self._audio_volume_label.setMinimumWidth(40)
        vol_row.addWidget(self._audio_volume_label)
        form.addRow("Volume:", vol_row)

        # Mute
        self._audio_mute_cb = QCheckBox("Mute")
        self._audio_mute_cb.toggled.connect(self._on_audio_mute_toggled)
        form.addRow("", self._audio_mute_cb)

        group.setLayout(form)
        parent_layout.addWidget(group)

    def _build_timeline_section(self, parent_layout: QVBoxLayout) -> None:
        from audio_visualizer.ui.tabs.renderComposition.timelineWidget import TimelineWidget

        group = QGroupBox("Timeline")
        layout = QVBoxLayout()

        self._timeline = TimelineWidget()
        self._timeline.item_selected.connect(self._on_timeline_item_selected)
        self._timeline.item_moved.connect(self._on_timeline_item_moved)
        self._timeline.item_trimmed.connect(self._on_timeline_item_trimmed)
        self._timeline.item_reordered.connect(self._on_timeline_item_reordered)
        self._timeline.playhead_changed.connect(self._on_playhead_changed)
        layout.addWidget(self._timeline)

        self._timeline_scrollbar = QScrollBar(Qt.Orientation.Horizontal)
        self._timeline_scrollbar.valueChanged.connect(self._on_timeline_scroll)
        self._timeline.scroll_state_changed.connect(self._on_timeline_scroll_state)
        layout.addWidget(self._timeline_scrollbar)

        group.setLayout(layout)
        parent_layout.addWidget(group, 1)

    def _build_render_section(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Render")
        layout = QVBoxLayout()

        # Row 1: Resolution, W, H, FPS, Output path, Browse
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Resolution:"))
        self._resolution_preset_combo = QComboBox()
        for key, label in RESOLUTION_PRESET_LABELS:
            self._resolution_preset_combo.addItem(label, key)
        self._resolution_preset_combo.currentIndexChanged.connect(
            self._on_resolution_preset_changed,
        )
        row1.addWidget(self._resolution_preset_combo)

        row1.addWidget(QLabel("W:"))
        self._out_width_spin = QSpinBox()
        self._out_width_spin.setRange(128, 7680)
        self._out_width_spin.setValue(1920)
        self._out_width_spin.editingFinished.connect(self._on_output_settings_changed)
        row1.addWidget(self._out_width_spin)

        row1.addWidget(QLabel("H:"))
        self._out_height_spin = QSpinBox()
        self._out_height_spin.setRange(128, 4320)
        self._out_height_spin.setValue(1080)
        self._out_height_spin.editingFinished.connect(self._on_output_settings_changed)
        row1.addWidget(self._out_height_spin)

        row1.addWidget(QLabel("FPS:"))
        self._out_fps_spin = QDoubleSpinBox()
        self._out_fps_spin.setRange(1.0, 120.0)
        self._out_fps_spin.setValue(30.0)
        self._out_fps_spin.setSingleStep(0.001)
        self._out_fps_spin.setDecimals(3)
        self._out_fps_spin.editingFinished.connect(self._on_output_settings_changed)
        row1.addWidget(self._out_fps_spin)

        row1.addWidget(QLabel("Output:"))
        self._output_path_edit = QLineEdit()
        self._output_path_edit.setPlaceholderText("output.mp4")
        row1.addWidget(self._output_path_edit, 1)

        self._browse_output_btn = QPushButton("Browse...")
        self._browse_output_btn.clicked.connect(self._on_browse_output)
        row1.addWidget(self._browse_output_btn)
        layout.addLayout(row1)

        # Row 2: Start Render + progress + status
        row2 = QHBoxLayout()
        self._start_btn = QPushButton("Start Render")
        self._start_btn.clicked.connect(self._on_start_render)
        row2.addWidget(self._start_btn)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        row2.addWidget(self._progress_bar, 1)

        self._status_label = QLabel("Ready")
        row2.addWidget(self._status_label)
        layout.addLayout(row2)

        group.setLayout(layout)
        group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        parent_layout.addWidget(group)

    # ------------------------------------------------------------------
    # Timeline helpers
    # ------------------------------------------------------------------

    def _refresh_timeline(self) -> None:
        """Rebuild timeline items from model."""
        from audio_visualizer.ui.tabs.renderComposition.timelineWidget import TimelineItem

        items: list[TimelineItem] = []
        for layer in self._model.get_layers_sorted():
            items.append(TimelineItem(
                item_id=layer.id,
                display_name=layer.display_name,
                start_ms=layer.start_ms,
                end_ms=layer.start_ms + layer.effective_duration_ms(),
                track_type="visual",
                enabled=layer.enabled,
                source_duration_ms=layer.source_duration_ms,
                z_order=layer.z_order,
            ))
        for al in self._model.audio_layers:
            items.append(TimelineItem(
                item_id=al.id,
                display_name=al.display_name,
                start_ms=al.start_ms,
                end_ms=al.effective_end_ms(),
                track_type="audio",
                enabled=al.enabled,
                source_duration_ms=al.source_duration_ms,
                muted=al.muted,
            ))
        if hasattr(self, "_timeline"):
            self._timeline.set_items(items)

    def _on_timeline_item_selected(self, item_id: str) -> None:
        """Sync timeline selection with unified layer list."""
        if not item_id:
            return
        # Find the row in the unified list that has this item_id
        for row in range(self._layer_list.count()):
            row_type, row_id = self._unified_row_type(row)
            if row_id == item_id:
                self._layer_list.setCurrentRow(row)
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
            self._refresh_layer_list()
            self._load_audio_layer_properties(al)
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
            self._refresh_layer_list()
            self._load_audio_layer_properties(al)
            self.settings_changed.emit()

    def _on_timeline_item_reordered(self, item_id: str, new_visual_index: int) -> None:
        """Handle visual layer reorder from timeline drag."""
        layer = self._model.get_layer(item_id)
        if layer is None:
            return
        # Rebuild z-order based on the new visual index order from the timeline
        visual_items = [i for i in self._model.layers]
        dragged = None
        for i, l in enumerate(visual_items):
            if l.id == item_id:
                dragged = visual_items.pop(i)
                break
        if dragged is not None:
            new_visual_index = max(0, min(new_visual_index, len(visual_items)))
            visual_items.insert(new_visual_index, dragged)
            for z, l in enumerate(visual_items):
                l.z_order = z
            self._model.layers = visual_items
        self._refresh_layer_list()
        self.settings_changed.emit()

    def _on_timeline_scroll(self, value: int) -> None:
        self._timeline.set_scroll_offset(value)

    def _on_timeline_scroll_state(self, minimum: int, maximum: int, page_step: int, value: int) -> None:
        self._timeline_scrollbar.blockSignals(True)
        self._timeline_scrollbar.setMinimum(minimum)
        self._timeline_scrollbar.setMaximum(maximum)
        self._timeline_scrollbar.setPageStep(page_step)
        self._timeline_scrollbar.setValue(value)
        self._timeline_scrollbar.blockSignals(False)

    def _on_playhead_changed(self, ms: int) -> None:
        """Sync playhead with preview timestamp spin."""
        self._updating_ui = True
        self._preview_time_spin.setValue(ms)
        self._updating_ui = False

    def _on_preview_time_changed(self, ms: int) -> None:
        """Sync preview spin with timeline playhead."""
        if self._updating_ui:
            return
        if hasattr(self, '_timeline'):
            self._timeline.set_playhead_ms(ms)

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
        """Rebuild source combo box from session context."""
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
        finally:
            self._updating_ui = False

        # Refresh the unified layer list
        self._refresh_layer_list()

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
            row_type, row_id = self._unified_row_type(self._layer_list.currentRow())
            if row_type == "visual":
                layer = self._model.get_layer(row_id)
                if layer is not None:
                    self._load_layer_properties(layer)
            elif row_type == "audio":
                al = self._model.get_audio_layer(row_id)
                if al is not None:
                    self._load_audio_layer_properties(al)

    def _on_redo(self) -> None:
        if self._undo_stack is not None and self._undo_stack.canRedo():
            self._undo_stack.redo()
            self._refresh_layer_list()
            row_type, row_id = self._unified_row_type(self._layer_list.currentRow())
            if row_type == "visual":
                layer = self._model.get_layer(row_id)
                if layer is not None:
                    self._load_layer_properties(layer)
            elif row_type == "audio":
                al = self._model.get_audio_layer(row_id)
                if al is not None:
                    self._load_audio_layer_properties(al)

    # ------------------------------------------------------------------
    # Unified layer list management
    # ------------------------------------------------------------------

    def _refresh_layer_list(self) -> None:
        """Rebuild the unified layer list widget from both visual and audio layers."""
        self._updating_ui = True
        try:
            selected_type, selected_id = self._unified_row_type(self._layer_list.currentRow())
            self._layer_list.clear()

            # Visual layers (draggable)
            for layer in self._model.get_layers_sorted():
                prefix = "[V]" if layer.enabled else "[V][ ]"
                text = f"{prefix} {layer.display_name} (z={layer.z_order})"
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, ("visual", layer.id))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled)
                self._layer_list.addItem(item)

            # Audio layers (not draggable)
            for al in self._model.audio_layers:
                prefix = "[A]" if al.enabled else "[A][ ]"
                text = f"{prefix} {al.display_name}"
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, ("audio", al.id))
                # Clear drag flags for audio items
                item.setFlags(
                    item.flags()
                    & ~Qt.ItemFlag.ItemIsDragEnabled
                    & ~Qt.ItemFlag.ItemIsDropEnabled
                )
                self._layer_list.addItem(item)

            restored = False
            if selected_id:
                for row in range(self._layer_list.count()):
                    row_type, row_id = self._unified_row_type(row)
                    if row_type == selected_type and row_id == selected_id:
                        self._layer_list.setCurrentRow(row)
                        restored = True
                        break
            if not restored and self._layer_list.count() > 0:
                self._layer_list.setCurrentRow(0)
        finally:
            self._updating_ui = False
        self._refresh_timeline()

    def _on_layer_list_reordered(self) -> None:
        """Recalculate z_order from the visual row order after drag-drop."""
        z = 0
        for row in range(self._layer_list.count()):
            row_type, row_id = self._unified_row_type(row)
            if row_type == "visual" and row_id:
                layer = self._model.get_layer(row_id)
                if layer is not None:
                    layer.z_order = z
                    z += 1
        self._refresh_layer_list()
        self._refresh_timeline()
        self.settings_changed.emit()

    def _unified_row_type(self, row: int) -> tuple[str | None, str | None]:
        """Return (type, layer_id) for the given unified list row.

        Returns ``("visual", layer_id)``, ``("audio", layer_id)``,
        or ``(None, None)`` if the row is invalid.
        """
        if row < 0 or row >= self._layer_list.count():
            return (None, None)
        item = self._layer_list.item(row)
        if item is None:
            return (None, None)
        data = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(data, (tuple, list)) and len(data) == 2:
            return (data[0], data[1])
        return (None, None)

    def _selected_layer(self) -> CompositionLayer | None:
        """Return the currently selected visual layer, or None."""
        row_type, row_id = self._unified_row_type(self._layer_list.currentRow())
        if row_type == "visual" and row_id:
            return self._model.get_layer(row_id)
        return None

    def _selected_audio_layer(self) -> CompositionAudioLayer | None:
        """Return the currently selected audio layer, or None."""
        row_type, row_id = self._unified_row_type(self._layer_list.currentRow())
        if row_type == "audio" and row_id:
            return self._model.get_audio_layer(row_id)
        return None

    def _on_layer_selected(self, row: int) -> None:
        """Update property panels when a layer is selected in the unified list."""
        if self._updating_ui:
            return
        row_type, row_id = self._unified_row_type(row)
        if row_type == "visual":
            layer = self._model.get_layer(row_id)
            if layer is not None:
                self._settings_stack.setCurrentIndex(0)
                self._load_layer_properties(layer)
        elif row_type == "audio":
            al = self._model.get_audio_layer(row_id)
            if al is not None:
                self._settings_stack.setCurrentIndex(1)
                self._load_audio_layer_properties(al)

    def _load_layer_properties(self, layer: CompositionLayer) -> None:
        """Populate the visual settings page with *layer*'s properties."""
        self._updating_ui = True
        try:
            # Name
            self._layer_name_edit.setText(layer.display_name)

            # Source
            if layer.asset_id:
                idx = self._source_combo.findData(layer.asset_id)
                if idx >= 0:
                    self._source_combo.setCurrentIndex(idx)
                else:
                    self._source_combo.setCurrentIndex(0)
            elif layer.asset_path:
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

            # Enabled
            self._layer_enabled_cb.setChecked(layer.enabled)

            # Position & size (center-origin)
            self._x_spin.setValue(layer.center_x)
            self._y_spin.setValue(layer.center_y)
            self._w_spin.setValue(layer.width)
            self._h_spin.setValue(layer.height)
            self._z_spin.setValue(layer.z_order)

            # Timing
            self._start_ms_spin.setValue(layer.start_ms)
            self._end_ms_spin.setValue(layer.end_ms)
            idx = self._behavior_combo.findText(layer.behavior_after_end)
            if idx >= 0:
                self._behavior_combo.setCurrentIndex(idx)

            # Visual full-length checkbox (only for video layers)
            if layer.source_kind == "video" and layer.source_duration_ms > 0:
                self._visual_full_length_cb.setVisible(True)
                is_full = (layer.end_ms == layer.start_ms + layer.source_duration_ms)
                self._visual_full_length_cb.setChecked(is_full)
                self._end_ms_spin.setEnabled(not is_full)
            else:
                self._visual_full_length_cb.setVisible(False)
                self._visual_full_length_cb.setChecked(False)
                self._end_ms_spin.setEnabled(True)

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

    def _load_audio_layer_properties(self, al: CompositionAudioLayer) -> None:
        """Populate audio layer editor controls."""
        self._updating_ui = True
        try:
            # Name
            self._audio_name_edit.setText(al.display_name)

            # Update source label
            if al.asset_path:
                self._audio_source_label.setText(str(al.asset_path.name))
            elif al.asset_id:
                self._audio_source_label.setText(f"Asset: {al.asset_id[:8]}")
            else:
                self._audio_source_label.setText("(none)")

            self._audio_start_spin.setValue(al.start_ms)
            self._audio_full_length_cb.setChecked(al.use_full_length)

            # When full length, show source duration and disable editing
            if al.use_full_length:
                self._audio_duration_spin.setValue(al.source_duration_ms)
                self._audio_duration_spin.setEnabled(False)
            else:
                self._audio_duration_spin.setValue(al.duration_ms)
                self._audio_duration_spin.setEnabled(True)

            # Volume and mute
            self._audio_volume_slider.setValue(int(al.volume * 100))
            self._audio_volume_label.setText(f"{int(al.volume * 100)}%")
            self._audio_mute_cb.setChecked(al.muted)
        finally:
            self._updating_ui = False

    # ------------------------------------------------------------------
    # Layer actions
    # ------------------------------------------------------------------

    def _on_add_asset(self) -> None:
        """Add a new asset (visual or audio) via unified file picker."""
        path = self._pick_session_or_file(None, "Add Asset", _ASSET_FILTERS)
        if path is None:
            return

        suffix = path.suffix.lower()

        if suffix in _AUDIO_EXTENSIONS:
            source_duration_ms = self._resolve_audio_source_duration(path)
            if source_duration_ms is None:
                return
            al = CompositionAudioLayer(
                display_name=path.name,
                asset_path=path,
                start_ms=0,
                duration_ms=0,
                use_full_length=True,
                source_duration_ms=source_duration_ms,
                enabled=True,
            )
            cmd = AddAudioLayerCommand(self._model, al)
            self._push_command(cmd)
            self._refresh_layer_list()
            new_row = len(self._model.layers) + len(self._model.audio_layers) - 1
            self._layer_list.setCurrentRow(new_row)
        elif suffix in _VIDEO_EXTENSIONS:
            resolved = self._resolve_visual_source_metadata(path)
            if resolved is None:
                return
            source_kind, source_duration_ms = resolved
            # Use native video dimensions centered in output
            native_w, native_h = self._probe_media_dimensions(path)
            layer = CompositionLayer(
                display_name=path.name,
                asset_path=path,
                source_kind=source_kind,
                source_duration_ms=source_duration_ms,
                start_ms=0,
                end_ms=source_duration_ms,
                center_x=0, center_y=0,
                width=native_w,
                height=native_h,
                z_order=len(self._model.layers),
                enabled=True,
            )
            # Check for audio streams and create linked audio layer
            has_audio = self._probe_has_audio(path)
            if has_audio:
                audio_dur = source_duration_ms or self._probe_media_duration(path)
                audio_layer = CompositionAudioLayer(
                    display_name=f"{path.name} (Audio)",
                    asset_path=path,
                    start_ms=0,
                    duration_ms=0,
                    use_full_length=True,
                    source_duration_ms=audio_dur,
                    enabled=True,
                    linked_layer_id=layer.id,
                )
                layer.linked_layer_id = audio_layer.id
                # Use a parent command so both add+audio are one undo step
                from PySide6.QtGui import QUndoCommand as _QUC
                parent_cmd = _QUC()
                parent_cmd.setText(f"Add video+audio '{path.name}'")
                AddLayerCommand(self._model, layer, parent=parent_cmd)
                AddAudioLayerCommand(self._model, audio_layer, parent=parent_cmd)
                self._push_command(parent_cmd)
            else:
                cmd = AddLayerCommand(self._model, layer)
                self._push_command(cmd)
            self._refresh_layer_list()
            new_row = len(self._model.layers) - 1
            self._layer_list.setCurrentRow(new_row)
        elif suffix in _IMAGE_EXTENSIONS:
            resolved = self._resolve_visual_source_metadata(path)
            if resolved is None:
                return
            source_kind, source_duration_ms = resolved
            layer = CompositionLayer(
                display_name=path.name,
                asset_path=path,
                source_kind=source_kind,
                source_duration_ms=source_duration_ms,
                start_ms=0,
                end_ms=5000,
                center_x=0, center_y=0,
                width=self._model.output_width,
                height=self._model.output_height,
                z_order=len(self._model.layers),
                enabled=True,
            )
            cmd = AddLayerCommand(self._model, layer)
            self._push_command(cmd)
            self._refresh_layer_list()
            new_row = len(self._model.layers) - 1
            self._layer_list.setCurrentRow(new_row)
        else:
            QMessageBox.warning(self, "Unknown File Type", f"Cannot determine type for:\n{path}")
            return
        self.settings_changed.emit()

    def _on_remove_layer(self) -> None:
        """Remove the selected item (visual or audio) from the unified list.

        When the layer has a linked counterpart, show a three-way dialog:
        Delete both / Delete only this / Cancel.
        """
        row_type, row_id = self._unified_row_type(self._layer_list.currentRow())
        if row_type == "visual" and row_id:
            layer = self._model.get_layer(row_id)
            linked_id = layer.linked_layer_id if layer else None
            if linked_id and self._model.get_audio_layer(linked_id):
                action = self._linked_delete_dialog("visual")
                if action == "cancel":
                    return
                if action == "both":
                    from PySide6.QtGui import QUndoCommand as _QUC
                    parent_cmd = _QUC()
                    parent_cmd.setText("Remove linked video+audio")
                    RemoveLayerCommand(self._model, row_id, parent=parent_cmd)
                    RemoveAudioLayerCommand(self._model, linked_id, parent=parent_cmd)
                    self._push_command(parent_cmd)
                else:
                    # Only this
                    cmd = RemoveLayerCommand(self._model, row_id)
                    self._push_command(cmd)
            else:
                cmd = RemoveLayerCommand(self._model, row_id)
                self._push_command(cmd)
            self._refresh_layer_list()
            self.settings_changed.emit()
        elif row_type == "audio" and row_id:
            al = self._model.get_audio_layer(row_id)
            linked_id = al.linked_layer_id if al else None
            if linked_id and self._model.get_layer(linked_id):
                action = self._linked_delete_dialog("audio")
                if action == "cancel":
                    return
                if action == "both":
                    from PySide6.QtGui import QUndoCommand as _QUC
                    parent_cmd = _QUC()
                    parent_cmd.setText("Remove linked video+audio")
                    RemoveAudioLayerCommand(self._model, row_id, parent=parent_cmd)
                    RemoveLayerCommand(self._model, linked_id, parent=parent_cmd)
                    self._push_command(parent_cmd)
                else:
                    cmd = RemoveAudioLayerCommand(self._model, row_id)
                    self._push_command(cmd)
            else:
                cmd = RemoveAudioLayerCommand(self._model, row_id)
                self._push_command(cmd)
            self._refresh_layer_list()
            self.settings_changed.emit()

    def _linked_delete_dialog(self, current_type: str) -> str:
        """Show a 3-way dialog for linked layer deletion.

        Returns ``"both"``, ``"only"``, or ``"cancel"``.
        """
        other = "audio" if current_type == "visual" else "visual"
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Delete Linked Layer")
        msg_box.setText(
            f"This {current_type} layer has a linked {other} layer.\n"
            "What would you like to do?"
        )
        delete_both = msg_box.addButton("Delete Both", QMessageBox.ButtonRole.AcceptRole)
        delete_only = msg_box.addButton("Delete Only This", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = msg_box.addButton(QMessageBox.StandardButton.Cancel)
        msg_box.setDefaultButton(cancel_btn)
        msg_box.exec()
        clicked = msg_box.clickedButton()
        if clicked == delete_both:
            return "both"
        elif clicked == delete_only:
            return "only"
        return "cancel"

    def _probe_media_duration(self, path: Path) -> int:
        """Probe media file and return duration in milliseconds, or 0 on failure."""
        try:
            from audio_visualizer.ui.mediaProbe import probe_media
            info = probe_media(str(path))
            if info and info.get("duration_ms"):
                return int(info["duration_ms"])
        except Exception:
            logger.debug("Media probe failed for %s", path, exc_info=True)
        return 0

    def _probe_has_audio(self, path: Path) -> bool:
        """Return True if *path* contains at least one audio stream."""
        try:
            from audio_visualizer.ui.mediaProbe import probe_media
            info = probe_media(str(path))
            if info and info.get("has_audio"):
                return True
            # Fallback: check if 'audio_streams' count > 0
            if info and info.get("audio_streams", 0) > 0:
                return True
        except Exception:
            logger.debug("Audio stream probe failed for %s", path, exc_info=True)
        return False

    def _probe_media_dimensions(self, path: Path) -> tuple[int, int]:
        """Probe media file and return (width, height), falling back to output dimensions."""
        try:
            from audio_visualizer.ui.mediaProbe import probe_media
            info = probe_media(str(path))
            if info and info.get("width") and info.get("height"):
                return (int(info["width"]), int(info["height"]))
        except Exception:
            logger.debug("Media dimension probe failed for %s", path, exc_info=True)
        return (self._model.output_width, self._model.output_height)

    def _resolve_visual_source_metadata(
        self,
        path: Path,
        *,
        asset_id: str | None = None,
        preferred_kind: str = "",
        preferred_duration_ms: int = 0,
        show_warning: bool = True,
    ) -> tuple[str, int] | None:
        """Resolve visual source kind and duration, aborting on unknown video duration."""
        source_kind = preferred_kind
        if source_kind not in {"image", "video"}:
            suffix = path.suffix.lower()
            if suffix in _IMAGE_EXTENSIONS:
                source_kind = "image"
            elif suffix in _VIDEO_EXTENSIONS:
                source_kind = "video"

        if source_kind == "image":
            return ("image", 0)

        if source_kind != "video":
            if show_warning:
                QMessageBox.warning(self, "Cannot Use Source", f"Unsupported visual source:\n{path}")
            return None

        duration_ms = preferred_duration_ms or self._probe_media_duration(path)
        if duration_ms <= 0:
            if show_warning:
                QMessageBox.warning(
                    self,
                    "Cannot Use Source",
                    f"Could not determine video duration for:\n{path}",
                )
            return None

        if asset_id and self._workspace_context is not None:
            asset = self._workspace_context.get_asset(asset_id)
            if asset is not None and asset.duration_ms != duration_ms:
                self._workspace_context.update_asset(asset_id, duration_ms=duration_ms)

        return ("video", duration_ms)

    def _resolve_audio_source_duration(
        self,
        path: Path,
        *,
        asset_id: str | None = None,
        preferred_duration_ms: int = 0,
        show_warning: bool = True,
    ) -> int | None:
        """Resolve audio duration, aborting when media metadata is incomplete."""
        duration_ms = preferred_duration_ms or self._probe_media_duration(path)
        if duration_ms <= 0:
            if show_warning:
                QMessageBox.warning(
                    self,
                    "Cannot Use Source",
                    f"Could not determine audio duration for:\n{path}",
                )
            return None

        if asset_id and self._workspace_context is not None:
            asset = self._workspace_context.get_asset(asset_id)
            if asset is not None and asset.duration_ms != duration_ms:
                self._workspace_context.update_asset(asset_id, duration_ms=duration_ms)

        return duration_ms

    # ------------------------------------------------------------------
    # Source / type changes
    # ------------------------------------------------------------------

    def _on_layer_name_changed(self) -> None:
        if self._updating_ui:
            return
        layer = self._selected_layer()
        if layer is None:
            return
        new_name = self._layer_name_edit.text().strip()
        if new_name and new_name != layer.display_name:
            layer.display_name = new_name
            self._refresh_layer_list()
            self._refresh_timeline()
            self.settings_changed.emit()

    def _on_audio_name_changed(self) -> None:
        if self._updating_ui:
            return
        al = self._selected_audio_layer()
        if al is None:
            return
        new_name = self._audio_name_edit.text().strip()
        if new_name and new_name != al.display_name:
            al.display_name = new_name
            self._refresh_layer_list()
            self._refresh_timeline()
            self.settings_changed.emit()

    def _on_source_changed(self, index: int) -> None:
        if self._updating_ui:
            return
        layer = self._selected_layer()
        if layer is None:
            return

        data = self._source_combo.currentData()
        asset_id: str | None = None
        asset_path: Path | None = None
        display_name: str | None = None
        source_kind = ""
        source_duration_ms = 0

        if data and isinstance(data, str):
            if data.startswith("file:"):
                asset_path = Path(data[5:])
                display_name = asset_path.name
            elif self._workspace_context:
                asset_id = data
                asset = self._workspace_context.get_asset(asset_id)
                if asset:
                    asset_path = asset.path
                    display_name = asset.display_name
                    if asset.category in ("video", "image"):
                        resolved = self._resolve_visual_source_metadata(
                            asset.path,
                            asset_id=asset.id,
                            preferred_kind=asset.category,
                            preferred_duration_ms=asset.duration_ms or 0,
                        )
                        if resolved is None:
                            return
                        source_kind, source_duration_ms = resolved

        if asset_path:
            resolved = self._resolve_visual_source_metadata(
                asset_path,
                asset_id=asset_id,
                preferred_kind=source_kind,
                preferred_duration_ms=source_duration_ms,
            )
            if resolved is None:
                return
            source_kind, source_duration_ms = resolved

        cmd = ChangeSourceCommand(
            self._model, layer.id, asset_id, asset_path,
            display_name=display_name,
            source_kind=source_kind,
            source_duration_ms=source_duration_ms,
        )
        self._push_command(cmd)
        # Update dimensions for video sources to native size, centered
        if source_kind == "video" and asset_path:
            native_w, native_h = self._probe_media_dimensions(asset_path)
            layer.width = native_w
            layer.height = native_h
            layer.center_x = 0
            layer.center_y = 0
            if source_duration_ms > 0:
                layer.end_ms = layer.start_ms + source_duration_ms
        self._refresh_layer_list()
        self.settings_changed.emit()

    def _on_browse_source(self) -> None:
        layer = self._selected_layer()
        if layer is None:
            return
        path = self._pick_session_or_file(None, "Select Source", _ASSET_FILTERS)
        if path is not None:
            resolved = self._resolve_visual_source_metadata(path)
            if resolved is None:
                return
            source_kind, source_duration_ms = resolved

            display_name = path.name

            cmd = ChangeSourceCommand(
                self._model, layer.id, None, path,
                display_name=display_name,
                source_kind=source_kind,
                source_duration_ms=source_duration_ms,
            )
            self._push_command(cmd)

            # Update dimensions for video sources to native size, centered
            if source_kind == "video":
                native_w, native_h = self._probe_media_dimensions(path)
                layer.width = native_w
                layer.height = native_h
                layer.center_x = 0
                layer.center_y = 0
                layer.end_ms = layer.start_ms + source_duration_ms

            self._load_layer_properties(layer)
            self._refresh_layer_list()
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
        if new_x != layer.center_x or new_y != layer.center_y:
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
        # Apply ratio lock
        if self._lock_ratio_cb.isChecked() and layer.width > 0 and layer.height > 0:
            aspect = layer.width / layer.height
            if new_w != layer.width:
                new_h = max(1, int(new_w / aspect))
            elif new_h != layer.height:
                new_w = max(1, int(new_h * aspect))
            self._updating_ui = True
            self._w_spin.setValue(new_w)
            self._h_spin.setValue(new_h)
            self._updating_ui = False
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

    def _on_original_size(self) -> None:
        """Restore the selected layer to its source media dimensions."""
        layer = self._selected_layer()
        if layer is None or not layer.asset_path:
            return
        native_w, native_h = self._probe_media_dimensions(layer.asset_path)
        if native_w != layer.width or native_h != layer.height:
            cmd = ResizeLayerCommand(self._model, layer.id, native_w, native_h)
            self._push_command(cmd)
            self._updating_ui = True
            self._w_spin.setValue(native_w)
            self._h_spin.setValue(native_h)
            self._updating_ui = False
            self.settings_changed.emit()

    def _on_fit_to_output(self) -> None:
        """Scale the selected layer to fill the output resolution, respecting ratio lock."""
        layer = self._selected_layer()
        if layer is None:
            return
        out_w = self._model.output_width
        out_h = self._model.output_height
        if self._lock_ratio_cb.isChecked() and layer.width > 0 and layer.height > 0:
            aspect = layer.width / layer.height
            # Fit inside output while keeping aspect ratio
            if out_w / out_h > aspect:
                new_h = out_h
                new_w = max(1, int(new_h * aspect))
            else:
                new_w = out_w
                new_h = max(1, int(new_w / aspect))
        else:
            new_w = out_w
            new_h = out_h
        if new_w != layer.width or new_h != layer.height:
            cmd = ResizeLayerCommand(self._model, layer.id, new_w, new_h)
            self._push_command(cmd)
            self._updating_ui = True
            self._w_spin.setValue(new_w)
            self._h_spin.setValue(new_h)
            self._updating_ui = False
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

    def _on_visual_full_length_toggled(self, checked: bool) -> None:
        """Handle Full Length checkbox for video layers."""
        if self._updating_ui:
            return
        layer = self._selected_layer()
        if layer is None or layer.source_kind != "video":
            return
        # Re-probe if source duration is unknown
        if layer.source_duration_ms <= 0 and layer.asset_path:
            probed = self._probe_media_duration(layer.asset_path)
            if probed > 0:
                layer.source_duration_ms = probed
        if layer.source_duration_ms <= 0:
            return
        if checked:
            layer.end_ms = layer.start_ms + layer.source_duration_ms
            self._updating_ui = True
            self._end_ms_spin.setValue(layer.end_ms)
            self._end_ms_spin.setEnabled(False)
            self._updating_ui = False
        else:
            self._end_ms_spin.setEnabled(True)
            if layer.end_ms <= layer.start_ms:
                layer.end_ms = layer.start_ms + layer.source_duration_ms
                self._updating_ui = True
                self._end_ms_spin.setValue(layer.end_ms)
                self._updating_ui = False
        self._refresh_timeline()
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

    def _on_pick_key_from_preview(self) -> None:
        """Start pick-from-preview mode for key color."""
        pixmap = self._preview_label.pixmap()
        if pixmap is None or pixmap.isNull():
            QMessageBox.information(
                self,
                "No Preview",
                "Generate a preview frame first using 'Refresh Preview'.",
            )
            return
        self._picking_key_color = True
        self._preview_label.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        self._preview_label.setFocus(Qt.FocusReason.OtherFocusReason)
        self._preview_label.installEventFilter(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Handle pick-from-preview mouse events."""
        if obj is self._preview_label and self._picking_key_color:
            if event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.RightButton:
                    self._cancel_pick_mode()
                    return True
                if event.button() == Qt.MouseButton.LeftButton:
                    self._sample_preview_color(event.position().toPoint())
                    return True
                return True
            if event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Escape:
                    self._cancel_pick_mode()
                    return True
        return super().eventFilter(obj, event)

    def _sample_preview_color(self, click_pos) -> None:
        """Sample color at *click_pos* from the preview pixmap."""
        pixmap = self._preview_label.pixmap()
        if pixmap is None or pixmap.isNull():
            self._cancel_pick_mode()
            return

        # Account for aspect-ratio scaling with AlignCenter
        label_w = self._preview_label.width()
        label_h = self._preview_label.height()
        pm_w = pixmap.width()
        pm_h = pixmap.height()

        # The displayed pixmap is scaled to fit the label keeping aspect ratio
        scale = min(label_w / pm_w, label_h / pm_h)
        displayed_w = pm_w * scale
        displayed_h = pm_h * scale
        offset_x = (label_w - displayed_w) / 2.0
        offset_y = (label_h - displayed_h) / 2.0

        # Map click coordinates to pixmap coordinates
        px_x = int((click_pos.x() - offset_x) / scale)
        px_y = int((click_pos.y() - offset_y) / scale)

        if 0 <= px_x < pm_w and 0 <= px_y < pm_h:
            image = pixmap.toImage()
            color = image.pixelColor(px_x, px_y)
            self._key_color_edit.setText(color.name())
            self._on_matte_changed()

        self._cancel_pick_mode()

    def _cancel_pick_mode(self) -> None:
        """Exit pick-from-preview mode."""
        self._picking_key_color = False
        self._preview_label.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self._preview_label.removeEventFilter(self)

    # ------------------------------------------------------------------
    # Audio layer management
    # ------------------------------------------------------------------

    def _on_audio_layer_edited(self, *_args: Any) -> None:
        """Apply edits from the audio layer editor to the selected layer."""
        if self._updating_ui:
            return
        al = self._selected_audio_layer()
        if al is None:
            return
        use_full_length = self._audio_full_length_cb.isChecked()
        duration_ms = 0 if use_full_length else self._audio_duration_spin.value()
        cmd = EditAudioLayerCommand(
            self._model,
            al.id,
            start_ms=self._audio_start_spin.value(),
            duration_ms=duration_ms,
            use_full_length=use_full_length,
        )
        self._push_command(cmd)
        self._refresh_timeline()
        self.settings_changed.emit()

    def _on_audio_full_length_toggled(self, checked: bool) -> None:
        """Handle Full Length checkbox toggle for audio layers."""
        if self._updating_ui:
            return
        al = self._selected_audio_layer()
        if al is None:
            return
        if checked:
            # If source_duration_ms is unknown, try to probe it now
            if al.source_duration_ms <= 0 and al.asset_path:
                probed = self._probe_media_duration(al.asset_path)
                if probed > 0:
                    al.source_duration_ms = probed
            cmd = EditAudioLayerCommand(
                self._model,
                al.id,
                duration_ms=0,
                use_full_length=True,
                source_duration_ms=al.source_duration_ms,
            )
            self._push_command(cmd)
        else:
            duration_ms = self._audio_duration_spin.value()
            if duration_ms <= 0 and al.source_duration_ms > 0:
                duration_ms = al.source_duration_ms
            cmd = EditAudioLayerCommand(
                self._model,
                al.id,
                duration_ms=duration_ms,
                use_full_length=False,
            )
            self._push_command(cmd)
        self._load_audio_layer_properties(al)
        self._refresh_timeline()
        self.settings_changed.emit()

    def _on_audio_volume_changed(self, value: int) -> None:
        """Handle volume slider change for audio layers."""
        if self._updating_ui:
            return
        al = self._selected_audio_layer()
        if al is None:
            return
        volume = value / 100.0
        self._audio_volume_label.setText(f"{value}%")
        if abs(volume - al.volume) > 0.001:
            cmd = EditAudioLayerCommand(self._model, al.id, volume=volume)
            self._push_command(cmd)
            self.settings_changed.emit()

    def _on_audio_mute_toggled(self, checked: bool) -> None:
        """Handle mute checkbox toggle for audio layers."""
        if self._updating_ui:
            return
        al = self._selected_audio_layer()
        if al is None:
            return
        if checked != al.muted:
            cmd = EditAudioLayerCommand(self._model, al.id, muted=checked)
            self._push_command(cmd)
            self._refresh_timeline()
            self.settings_changed.emit()

    def _on_browse_audio(self) -> None:
        from audio_visualizer.ui.sessionFilePicker import resolve_browse_directory
        start_dir = resolve_browse_directory(workspace_context=self.workspace_context)
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Audio Source", start_dir,
            "Audio files (*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.wma);;All files (*)",
        )
        if not path:
            return
        path = Path(path)
        source_duration_ms = self._resolve_audio_source_duration(path)
        if source_duration_ms is None:
            return

        al = self._selected_audio_layer()
        if al is not None:
            cmd = EditAudioLayerCommand(
                self._model,
                al.id,
                asset_id=None,
                asset_path=path,
                display_name=path.name,
                source_duration_ms=source_duration_ms,
            )
            self._push_command(cmd)
            self._refresh_layer_list()
            self._load_audio_layer_properties(al)
        else:
            new_al = CompositionAudioLayer(
                display_name=path.name,
                asset_path=path,
                source_duration_ms=source_duration_ms,
            )
            cmd_add = AddAudioLayerCommand(self._model, new_al)
            self._push_command(cmd_add)
            self._refresh_layer_list()
            new_row = len(self._model.layers) + len(self._model.audio_layers) - 1
            self._layer_list.setCurrentRow(new_row)
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
        if self._picking_key_color:
            self._cancel_pick_mode()
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
        if self._picking_key_color:
            self._cancel_pick_mode()
        self._preview_refresh_btn.setEnabled(True)
        self._preview_status_label.setText("")

        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self._preview_status_label.setText("Failed to load preview image")
            return

        # Timeline preview
        scaled = pixmap.scaled(
            self._timeline_preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._timeline_preview_label.setPixmap(scaled)

        # Update layer preview based on selection
        self._update_layer_preview()

    def _on_preview_failed(self, error: str) -> None:
        """Handle preview generation failure."""
        if self._picking_key_color:
            self._cancel_pick_mode()
        self._preview_refresh_btn.setEnabled(True)
        self._preview_status_label.setText(f"Preview failed: {error}")

    def _update_layer_preview(self) -> None:
        """Update the Layer preview tab based on current selection."""
        row_type, row_id = self._unified_row_type(self._layer_list.currentRow())
        if row_type == "audio":
            self._layer_preview_label.setPixmap(QPixmap())
            self._layer_preview_label.setText("Audio layers do not have a layer preview.")
        elif row_type == "visual" and row_id:
            layer = self._model.get_layer(row_id)
            if layer and layer.asset_path:
                self._layer_preview_label.setText("Generating layer preview...")
                timestamp_ms = self._preview_time_spin.value()
                timestamp_s = timestamp_ms / 1000.0
                worker = _LayerPreviewWorker(copy.deepcopy(self._model), layer, timestamp_s)
                worker.signals.finished.connect(self._on_layer_preview_finished)
                worker.signals.failed.connect(self._on_layer_preview_failed)
                mw = self._main_window
                if mw and hasattr(mw, "render_thread_pool"):
                    mw.render_thread_pool.start(worker)
                else:
                    QThreadPool.globalInstance().start(worker)
                return
            self._layer_preview_label.setPixmap(QPixmap())
            self._layer_preview_label.setText("Select a visual layer to preview.")
        else:
            self._layer_preview_label.setPixmap(QPixmap())
            self._layer_preview_label.setText("Select a visual layer to preview.")

    def _on_layer_preview_finished(self, image_path: str) -> None:
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self._layer_preview_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._layer_preview_label.setPixmap(scaled)
        else:
            self._layer_preview_label.setText("Failed to load layer preview.")

    def _on_layer_preview_failed(self, error: str) -> None:
        self._layer_preview_label.setText(f"Layer preview failed: {error}")

    # ------------------------------------------------------------------
    # Presets
    # ------------------------------------------------------------------

    def _refresh_preset_combo(self) -> None:
        """Rebuild preset combo from built-in + user presets."""
        self._preset_combo.clear()
        self._preset_combo.addItem("(none)")
        for name in list_presets():
            self._preset_combo.addItem(name)

    def _on_save_preset(self) -> None:
        """Save current visual layers as a user preset."""
        if not self._model.layers:
            QMessageBox.information(self, "No Layers", "Add visual layers before saving a preset.")
            return
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        # Check for overwrite
        existing = list_presets()
        if name in existing:
            answer = QMessageBox.question(
                self, "Overwrite Preset",
                f"A preset named '{name}' already exists. Overwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            save_preset(name, self._model.layers)
            self._refresh_preset_combo()
        except Exception as exc:
            QMessageBox.warning(self, "Save Failed", str(exc))

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
                has_audio=any(al.enabled and al.asset_path for al in self._model.audio_layers),
                metadata={
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
        self._status_label.setText(f"Render failed: {error}")

        mw = self._main_window
        if mw and hasattr(mw, "show_job_failed"):
            mw.show_job_failed(error, self.tab_id)
        self._active_worker = None

    def _on_render_canceled(self, message: str) -> None:
        self._start_btn.setEnabled(True)
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
            current_row_type, current_row_id = self._unified_row_type(
                self._layer_list.currentRow()
            )
            if current_row_type == "visual":
                layer = self._model.get_layer(current_row_id)
                if layer is not None:
                    self._load_layer_properties(layer)
            elif current_row_type == "audio":
                al = self._model.get_audio_layer(current_row_id)
                if al is not None:
                    self._load_audio_layer_properties(al)

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


class _LayerPreviewWorker(QRunnable):
    """QRunnable that extracts a single layer preview frame via FFmpeg."""

    def __init__(self, model: CompositionModel, layer: CompositionLayer, timestamp_s: float) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._model = model
        self._layer = copy.deepcopy(layer)
        self._timestamp_s = timestamp_s
        self.signals = _PreviewSignals()

    def run(self) -> None:
        try:
            import shutil

            if shutil.which("ffmpeg") is None:
                self.signals.failed.emit("FFmpeg not found on PATH.")
                return

            from audio_visualizer.ui.tabs.renderComposition.filterGraph import (
                build_single_layer_preview_command,
            )

            tmp = tempfile.NamedTemporaryFile(
                suffix=".png", prefix="layer_preview_", delete=False
            )
            tmp.close()

            cmd = build_single_layer_preview_command(
                self._model, self._layer, self._timestamp_s, tmp.name
            )
            logger.debug("Layer preview command: %s", " ".join(cmd))

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
            )

            if result.returncode != 0:
                stderr = result.stderr[-500:] if result.stderr else ""
                self.signals.failed.emit(
                    f"FFmpeg exited with code {result.returncode}: {stderr}"
                )
                return

            if not Path(tmp.name).exists() or Path(tmp.name).stat().st_size == 0:
                self.signals.failed.emit("Layer preview frame was not generated.")
                return

            self.signals.finished.emit(tmp.name)

        except subprocess.TimeoutExpired:
            self.signals.failed.emit("Layer preview generation timed out.")
        except Exception as exc:
            self.signals.failed.emit(str(exc))
