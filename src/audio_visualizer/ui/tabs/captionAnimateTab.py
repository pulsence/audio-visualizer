"""Caption Animate tab — subtitle overlay rendering.

Provides a full settings surface for the caption package including
preset management (built-in, file, app-data library), full PresetConfig
style editing, animation selection, audio-reactive support, and a
cancellable FFmpeg-based render worker.
"""
from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from audio_visualizer.events import AppEventEmitter
from audio_visualizer.caption.captionApi import RenderConfig
from audio_visualizer.caption.core.config import AnimationConfig, PresetConfig
from audio_visualizer.caption.presets.defaults import list_builtin_presets
from audio_visualizer.caption.presets.loader import (
    PresetLoader,
    ensure_example_presets,
    get_caption_preset_dir,
)
from audio_visualizer.caption.animations import AnimationRegistry
from audio_visualizer.ui.sessionContext import SessionAsset, SessionContext
from audio_visualizer.ui.sessionFilePicker import pick_session_or_file
from audio_visualizer.ui.tabs.baseTab import BaseTab
from audio_visualizer.ui.workers.captionRenderWorker import (
    CaptionRenderJobSpec,
    CaptionRenderWorker,
)

logger = logging.getLogger(__name__)

_SUBTITLE_FILTERS = (
    "Subtitle files (*.srt *.ass);;"
    "SRT files (*.srt);;"
    "ASS files (*.ass);;"
    "All files (*)"
)

_AUDIO_FILTERS = (
    "Audio files (*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.wma);;"
    "All files (*)"
)

_FPS_OPTIONS = ["24", "25", "29.97", "30", "60"]

_QUALITY_OPTIONS = [
    ("small", "Small — H.264 with alpha (smallest files)"),
    ("medium", "Medium — ProRes 422 HQ (no alpha)"),
    ("large", "Large — ProRes 4444 (best quality, alpha)"),
]

_ALIGNMENT_OPTIONS = [
    (1, "1 — Bottom-left"),
    (2, "2 — Bottom-center"),
    (3, "3 — Bottom-right"),
    (4, "4 — Middle-left"),
    (5, "5 — Middle-center"),
    (6, "6 — Middle-right"),
    (7, "7 — Top-left"),
    (8, "8 — Top-center"),
    (9, "9 — Top-right"),
]

_WRAP_STYLE_OPTIONS = [
    (0, "0 — Smart wrap (even lines)"),
    (1, "1 — End-of-line wrap"),
    (2, "2 — No wrap"),
    (3, "3 — Smart wrap (bottom wider)"),
]

_PRESET_SOURCES = ["Built-in", "File", "App-data library"]


class CaptionAnimateTab(BaseTab):
    """Full-surface Caption Animate tab with preset management and rendering."""

    # ------------------------------------------------------------------
    # BaseTab identity
    # ------------------------------------------------------------------

    @property
    def tab_id(self) -> str:
        return "caption_animate"

    @property
    def tab_title(self) -> str:
        return "Caption Animate"

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._main_window = parent
        self._active_worker: Optional[CaptionRenderWorker] = None
        self._thread_pool = QThreadPool()
        self._thread_pool.setMaxThreadCount(1)
        self._example_presets_seeded = False
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(8)

        # Sections
        layout.addWidget(self._build_input_section())
        layout.addWidget(self._build_render_settings_section())
        layout.addWidget(self._build_preset_management_section())
        layout.addWidget(self._build_font_group())
        layout.addWidget(self._build_colors_group())
        layout.addWidget(self._build_styling_group())
        layout.addWidget(self._build_layout_group())
        layout.addWidget(self._build_animation_section())
        layout.addWidget(self._build_audio_reactive_section())
        layout.addWidget(self._build_preview_section())
        layout.addWidget(self._build_render_controls())

        layout.addStretch()
        content.setLayout(layout)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.setLayout(outer)

    # -- Input section -------------------------------------------------

    def _build_input_section(self) -> QGroupBox:
        group = QGroupBox("Input / Output")
        layout = QVBoxLayout()

        # Subtitle input
        sub_row = QHBoxLayout()
        sub_row.addWidget(QLabel("Subtitle file:"))
        self._subtitle_edit = QLineEdit()
        self._subtitle_edit.setPlaceholderText("Select a .srt or .ass file")
        sub_row.addWidget(self._subtitle_edit)
        self._subtitle_browse_btn = QPushButton("Browse...")
        self._subtitle_browse_btn.clicked.connect(self._browse_subtitle)
        sub_row.addWidget(self._subtitle_browse_btn)
        layout.addLayout(sub_row)

        # Session subtitle assets combo
        session_sub_row = QHBoxLayout()
        session_sub_row.addWidget(QLabel("Session asset:"))
        self._session_subtitle_combo = QComboBox()
        self._session_subtitle_combo.addItem("(none)")
        self._session_subtitle_combo.currentIndexChanged.connect(
            self._on_session_subtitle_changed
        )
        session_sub_row.addWidget(self._session_subtitle_combo)
        layout.addLayout(session_sub_row)

        # Output directory
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Output directory:"))
        self._output_dir_edit = QLineEdit()
        self._output_dir_edit.setPlaceholderText("Defaults to subtitle file directory")
        out_row.addWidget(self._output_dir_edit)
        self._output_browse_btn = QPushButton("Browse...")
        self._output_browse_btn.clicked.connect(self._browse_output_dir)
        out_row.addWidget(self._output_browse_btn)
        layout.addLayout(out_row)

        group.setLayout(layout)
        return group

    # -- Render settings -----------------------------------------------

    def _build_render_settings_section(self) -> QGroupBox:
        group = QGroupBox("Render Settings")
        layout = QHBoxLayout()

        layout.addWidget(QLabel("FPS:"))
        self._fps_combo = QComboBox()
        self._fps_combo.addItems(_FPS_OPTIONS)
        self._fps_combo.setCurrentText("30")
        layout.addWidget(self._fps_combo)

        layout.addWidget(QLabel("Quality:"))
        self._quality_combo = QComboBox()
        for value, label in _QUALITY_OPTIONS:
            self._quality_combo.addItem(label, value)
        layout.addWidget(self._quality_combo)

        layout.addWidget(QLabel("Safety scale:"))
        self._safety_scale_spin = QDoubleSpinBox()
        self._safety_scale_spin.setRange(1.0, 2.0)
        self._safety_scale_spin.setSingleStep(0.01)
        self._safety_scale_spin.setValue(1.12)
        self._safety_scale_spin.setDecimals(2)
        layout.addWidget(self._safety_scale_spin)

        self._reskin_cb = QCheckBox("Reskin ASS files")
        self._reskin_cb.setToolTip(
            "When enabled, ASS files will have the preset style applied "
            "instead of keeping their original styling."
        )
        layout.addWidget(self._reskin_cb)

        group.setLayout(layout)
        return group

    # -- Preset management ---------------------------------------------

    def _build_preset_management_section(self) -> QGroupBox:
        group = QGroupBox("Preset")
        layout = QVBoxLayout()

        # Preset source
        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Source:"))
        self._preset_source_combo = QComboBox()
        self._preset_source_combo.addItems(_PRESET_SOURCES)
        self._preset_source_combo.currentIndexChanged.connect(
            self._on_preset_source_changed
        )
        source_row.addWidget(self._preset_source_combo)
        layout.addLayout(source_row)

        # Built-in preset dropdown
        builtin_row = QHBoxLayout()
        builtin_row.addWidget(QLabel("Built-in preset:"))
        self._builtin_preset_combo = QComboBox()
        for name in list_builtin_presets():
            self._builtin_preset_combo.addItem(name)
        self._builtin_preset_combo.currentIndexChanged.connect(
            self._on_builtin_preset_changed
        )
        builtin_row.addWidget(self._builtin_preset_combo)
        self._load_preset_btn = QPushButton("Load")
        self._load_preset_btn.clicked.connect(self._load_selected_preset)
        builtin_row.addWidget(self._load_preset_btn)
        layout.addLayout(builtin_row)

        # File preset browse
        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("Preset file:"))
        self._preset_file_edit = QLineEdit()
        self._preset_file_edit.setPlaceholderText("Select a .json or .yaml preset")
        file_row.addWidget(self._preset_file_edit)
        self._preset_file_browse_btn = QPushButton("Browse...")
        self._preset_file_browse_btn.clicked.connect(self._browse_preset_file)
        file_row.addWidget(self._preset_file_browse_btn)
        self._preset_file_load_btn = QPushButton("Load")
        self._preset_file_load_btn.clicked.connect(self._load_preset_from_file)
        file_row.addWidget(self._preset_file_load_btn)
        layout.addLayout(file_row)

        # App-data library
        lib_row = QHBoxLayout()
        lib_row.addWidget(QLabel("Library preset:"))
        self._library_combo = QComboBox()
        lib_row.addWidget(self._library_combo)
        self._library_load_btn = QPushButton("Load")
        self._library_load_btn.clicked.connect(self._load_library_preset)
        lib_row.addWidget(self._library_load_btn)
        self._library_refresh_btn = QPushButton("Refresh")
        self._library_refresh_btn.clicked.connect(self._refresh_library)
        lib_row.addWidget(self._library_refresh_btn)
        layout.addLayout(lib_row)

        # Library actions
        lib_actions = QHBoxLayout()
        self._import_preset_btn = QPushButton("Import Preset...")
        self._import_preset_btn.clicked.connect(self._import_preset)
        lib_actions.addWidget(self._import_preset_btn)

        self._export_preset_btn = QPushButton("Export Current...")
        self._export_preset_btn.clicked.connect(self._export_preset)
        lib_actions.addWidget(self._export_preset_btn)

        self._open_folder_btn = QPushButton("Open Preset Folder")
        self._open_folder_btn.clicked.connect(self._open_preset_folder)
        lib_actions.addWidget(self._open_folder_btn)
        layout.addLayout(lib_actions)

        # Apply initial visibility
        self._on_preset_source_changed(0)

        group.setLayout(layout)
        return group

    # -- Font group ----------------------------------------------------

    def _build_font_group(self) -> QGroupBox:
        group = QGroupBox("Font")
        group.setCheckable(True)
        group.setChecked(False)
        layout = QVBoxLayout()

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Font name:"))
        self._font_name_edit = QLineEdit("Arial")
        row1.addWidget(self._font_name_edit)
        row1.addWidget(QLabel("Size:"))
        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(8, 200)
        self._font_size_spin.setValue(64)
        row1.addWidget(self._font_size_spin)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        self._bold_cb = QCheckBox("Bold")
        row2.addWidget(self._bold_cb)
        self._italic_cb = QCheckBox("Italic")
        row2.addWidget(self._italic_cb)
        row2.addWidget(QLabel("Font file:"))
        self._font_file_edit = QLineEdit()
        self._font_file_edit.setPlaceholderText("Optional — uses system font if empty")
        row2.addWidget(self._font_file_edit)
        self._font_file_browse_btn = QPushButton("Browse...")
        self._font_file_browse_btn.clicked.connect(self._browse_font_file)
        row2.addWidget(self._font_file_browse_btn)
        layout.addLayout(row2)

        group.setLayout(layout)
        return group

    # -- Colors group --------------------------------------------------

    def _build_colors_group(self) -> QGroupBox:
        group = QGroupBox("Colors")
        group.setCheckable(True)
        group.setChecked(False)
        layout = QHBoxLayout()

        layout.addWidget(QLabel("Primary:"))
        self._primary_color_edit = QLineEdit("#FFFFFF")
        self._primary_color_edit.setMaximumWidth(90)
        layout.addWidget(self._primary_color_edit)

        layout.addWidget(QLabel("Outline:"))
        self._outline_color_edit = QLineEdit("#000000")
        self._outline_color_edit.setMaximumWidth(90)
        layout.addWidget(self._outline_color_edit)

        layout.addWidget(QLabel("Shadow:"))
        self._shadow_color_edit = QLineEdit("#000000")
        self._shadow_color_edit.setMaximumWidth(90)
        layout.addWidget(self._shadow_color_edit)

        group.setLayout(layout)
        return group

    # -- Styling group -------------------------------------------------

    def _build_styling_group(self) -> QGroupBox:
        group = QGroupBox("Styling")
        group.setCheckable(True)
        group.setChecked(False)
        layout = QHBoxLayout()

        layout.addWidget(QLabel("Outline (px):"))
        self._outline_px_spin = QDoubleSpinBox()
        self._outline_px_spin.setRange(0, 20)
        self._outline_px_spin.setSingleStep(0.5)
        self._outline_px_spin.setValue(4.0)
        layout.addWidget(self._outline_px_spin)

        layout.addWidget(QLabel("Shadow (px):"))
        self._shadow_px_spin = QDoubleSpinBox()
        self._shadow_px_spin.setRange(0, 20)
        self._shadow_px_spin.setSingleStep(0.5)
        self._shadow_px_spin.setValue(2.0)
        layout.addWidget(self._shadow_px_spin)

        layout.addWidget(QLabel("Blur (px):"))
        self._blur_px_spin = QDoubleSpinBox()
        self._blur_px_spin.setRange(0, 20)
        self._blur_px_spin.setSingleStep(0.5)
        self._blur_px_spin.setValue(0.0)
        layout.addWidget(self._blur_px_spin)

        group.setLayout(layout)
        return group

    # -- Layout group --------------------------------------------------

    def _build_layout_group(self) -> QGroupBox:
        group = QGroupBox("Layout")
        group.setCheckable(True)
        group.setChecked(False)
        layout = QVBoxLayout()

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Line spacing:"))
        self._line_spacing_spin = QSpinBox()
        self._line_spacing_spin.setRange(0, 100)
        self._line_spacing_spin.setValue(8)
        row1.addWidget(self._line_spacing_spin)

        row1.addWidget(QLabel("Max width (px):"))
        self._max_width_spin = QSpinBox()
        self._max_width_spin.setRange(100, 4000)
        self._max_width_spin.setValue(1200)
        row1.addWidget(self._max_width_spin)
        layout.addLayout(row1)

        # Padding
        pad_row = QHBoxLayout()
        pad_row.addWidget(QLabel("Padding (T/R/B/L):"))
        self._pad_top_spin = QSpinBox()
        self._pad_top_spin.setRange(0, 200)
        self._pad_top_spin.setValue(40)
        pad_row.addWidget(self._pad_top_spin)
        self._pad_right_spin = QSpinBox()
        self._pad_right_spin.setRange(0, 200)
        self._pad_right_spin.setValue(60)
        pad_row.addWidget(self._pad_right_spin)
        self._pad_bottom_spin = QSpinBox()
        self._pad_bottom_spin.setRange(0, 200)
        self._pad_bottom_spin.setValue(50)
        pad_row.addWidget(self._pad_bottom_spin)
        self._pad_left_spin = QSpinBox()
        self._pad_left_spin.setRange(0, 200)
        self._pad_left_spin.setValue(60)
        pad_row.addWidget(self._pad_left_spin)
        layout.addLayout(pad_row)

        # Alignment, margins, wrap
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Alignment:"))
        self._alignment_combo = QComboBox()
        for val, label in _ALIGNMENT_OPTIONS:
            self._alignment_combo.addItem(label, val)
        self._alignment_combo.setCurrentIndex(1)  # 2 — Bottom-center
        row3.addWidget(self._alignment_combo)

        row3.addWidget(QLabel("Wrap:"))
        self._wrap_style_combo = QComboBox()
        for val, label in _WRAP_STYLE_OPTIONS:
            self._wrap_style_combo.addItem(label, val)
        self._wrap_style_combo.setCurrentIndex(2)  # wrap_style=2
        row3.addWidget(self._wrap_style_combo)
        layout.addLayout(row3)

        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Margin L:"))
        self._margin_l_spin = QSpinBox()
        self._margin_l_spin.setRange(0, 500)
        self._margin_l_spin.setValue(0)
        row4.addWidget(self._margin_l_spin)
        row4.addWidget(QLabel("R:"))
        self._margin_r_spin = QSpinBox()
        self._margin_r_spin.setRange(0, 500)
        self._margin_r_spin.setValue(0)
        row4.addWidget(self._margin_r_spin)
        row4.addWidget(QLabel("V:"))
        self._margin_v_spin = QSpinBox()
        self._margin_v_spin.setRange(0, 500)
        self._margin_v_spin.setValue(0)
        row4.addWidget(self._margin_v_spin)
        layout.addLayout(row4)

        group.setLayout(layout)
        return group

    # -- Animation section ---------------------------------------------

    def _build_animation_section(self) -> QGroupBox:
        group = QGroupBox("Animation")
        layout = QVBoxLayout()

        row1 = QHBoxLayout()
        self._apply_animation_cb = QCheckBox("Apply animation")
        self._apply_animation_cb.setChecked(True)
        row1.addWidget(self._apply_animation_cb)

        row1.addWidget(QLabel("Type:"))
        self._animation_type_combo = QComboBox()
        self._animation_type_combo.addItem("(none)")
        for atype in AnimationRegistry.list_types():
            self._animation_type_combo.addItem(atype)
        self._animation_type_combo.setCurrentText("fade")
        self._animation_type_combo.currentTextChanged.connect(
            self._on_animation_type_changed
        )
        row1.addWidget(self._animation_type_combo)
        layout.addLayout(row1)

        # Dynamic parameter container
        self._anim_params_widget = QWidget()
        self._anim_params_layout = QHBoxLayout()
        self._anim_params_layout.setContentsMargins(0, 0, 0, 0)
        self._anim_params_widget.setLayout(self._anim_params_layout)
        layout.addWidget(self._anim_params_widget)

        # Dictionary tracking dynamic param spin boxes
        self._anim_param_spins: Dict[str, QDoubleSpinBox] = {}

        # Populate initial params
        self._on_animation_type_changed(self._animation_type_combo.currentText())

        group.setLayout(layout)
        return group

    # -- Audio-reactive section ----------------------------------------

    def _build_audio_reactive_section(self) -> QGroupBox:
        group = QGroupBox("Audio-Reactive (optional)")
        group.setCheckable(True)
        group.setChecked(False)
        self._audio_reactive_group = group
        layout = QVBoxLayout()

        audio_row = QHBoxLayout()
        audio_row.addWidget(QLabel("Audio file:"))
        self._audio_file_edit = QLineEdit()
        self._audio_file_edit.setPlaceholderText("Select audio for reactive analysis")
        audio_row.addWidget(self._audio_file_edit)
        self._audio_browse_btn = QPushButton("Browse...")
        self._audio_browse_btn.clicked.connect(self._browse_audio_file)
        audio_row.addWidget(self._audio_browse_btn)
        layout.addLayout(audio_row)

        # Session audio assets
        session_audio_row = QHBoxLayout()
        session_audio_row.addWidget(QLabel("Session audio:"))
        self._session_audio_combo = QComboBox()
        self._session_audio_combo.addItem("(none)")
        self._session_audio_combo.currentIndexChanged.connect(
            self._on_session_audio_changed
        )
        session_audio_row.addWidget(self._session_audio_combo)
        layout.addLayout(session_audio_row)

        group.setLayout(layout)
        return group

    # -- Preview section -----------------------------------------------

    def _build_preview_section(self) -> QGroupBox:
        group = QGroupBox("Style Preview")
        layout = QVBoxLayout()

        self._preview_label = QLabel("The quick brown fox jumps over the lazy dog.")
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setWordWrap(True)
        self._preview_label.setMinimumHeight(60)
        self._update_preview_style()
        layout.addWidget(self._preview_label)

        refresh_btn = QPushButton("Refresh Preview")
        refresh_btn.clicked.connect(self._update_preview_style)
        layout.addWidget(refresh_btn)

        group.setLayout(layout)
        return group

    # -- Render controls -----------------------------------------------

    def _build_render_controls(self) -> QGroupBox:
        group = QGroupBox("Render")
        layout = QVBoxLayout()

        options_row = QHBoxLayout()
        self._mux_audio_cb = QCheckBox("Mux audio into output")
        self._mux_audio_cb.setChecked(False)
        options_row.addWidget(self._mux_audio_cb)
        options_row.addStretch()
        layout.addLayout(options_row)

        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("Start Render")
        self._start_btn.clicked.connect(self._start_render)
        btn_row.addWidget(self._start_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self.cancel_job)
        btn_row.addWidget(self._cancel_btn)
        layout.addLayout(btn_row)

        self._progress_bar = QProgressBar()
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("Ready")
        layout.addWidget(self._status_label)

        group.setLayout(layout)
        return group

    # ------------------------------------------------------------------
    # Preset management handlers
    # ------------------------------------------------------------------

    def _on_preset_source_changed(self, index: int) -> None:
        """Show/hide controls based on the selected preset source."""
        is_builtin = index == 0
        is_file = index == 1
        is_library = index == 2

        self._builtin_preset_combo.setVisible(is_builtin)
        self._load_preset_btn.setVisible(is_builtin)
        self._preset_file_edit.setVisible(is_file)
        self._preset_file_browse_btn.setVisible(is_file)
        self._preset_file_load_btn.setVisible(is_file)
        self._library_combo.setVisible(is_library)
        self._library_load_btn.setVisible(is_library)
        self._library_refresh_btn.setVisible(is_library)
        self._import_preset_btn.setVisible(is_library)
        self._export_preset_btn.setVisible(is_library)
        self._open_folder_btn.setVisible(is_library)

        if is_library:
            self._ensure_example_presets()
            self._refresh_library()

    def _ensure_example_presets(self) -> None:
        """Seed example presets on first access."""
        if not self._example_presets_seeded:
            try:
                ensure_example_presets()
                self._example_presets_seeded = True
            except Exception as exc:
                logger.warning("Failed to seed example presets: %s", exc)

    def _on_builtin_preset_changed(self, index: int) -> None:
        pass  # Load happens on explicit button click

    def _load_selected_preset(self) -> None:
        name = self._builtin_preset_combo.currentText()
        if not name:
            return
        try:
            loader = PresetLoader()
            preset = loader.load(name)
            self._apply_preset_to_ui(preset)
            self._status_label.setText(f"Loaded built-in preset: {name}")
        except Exception as exc:
            QMessageBox.warning(self, "Preset Error", str(exc))

    def _browse_preset_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Preset File", "",
            "Preset files (*.json *.yaml *.yml);;All files (*)",
        )
        if path:
            self._preset_file_edit.setText(path)

    def _load_preset_from_file(self) -> None:
        path = self._preset_file_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "No File", "Enter a preset file path first.")
            return
        try:
            loader = PresetLoader()
            preset = loader.load(path)
            self._apply_preset_to_ui(preset)
            self._status_label.setText(f"Loaded preset from: {Path(path).name}")
        except Exception as exc:
            QMessageBox.warning(self, "Preset Error", str(exc))

    def _refresh_library(self) -> None:
        """Refresh the app-data library combo."""
        self._library_combo.clear()
        try:
            preset_dir = get_caption_preset_dir()
            for p in sorted(preset_dir.iterdir()):
                if p.is_file() and p.suffix.lower() in (".json", ".yaml", ".yml"):
                    self._library_combo.addItem(p.name, str(p))
        except Exception as exc:
            logger.warning("Failed to list library presets: %s", exc)

    def _load_library_preset(self) -> None:
        path = self._library_combo.currentData()
        if not path:
            return
        try:
            loader = PresetLoader()
            preset = loader.load(path)
            self._apply_preset_to_ui(preset)
            self._status_label.setText(
                f"Loaded library preset: {self._library_combo.currentText()}"
            )
        except Exception as exc:
            QMessageBox.warning(self, "Preset Error", str(exc))

    def _import_preset(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Preset", "",
            "Preset files (*.json *.yaml *.yml);;All files (*)",
        )
        if not path:
            return
        try:
            dest = get_caption_preset_dir() / Path(path).name
            shutil.copy2(path, dest)
            self._refresh_library()
            self._status_label.setText(f"Imported: {Path(path).name}")
        except Exception as exc:
            QMessageBox.warning(self, "Import Error", str(exc))

    def _export_preset(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Current Preset", "preset.json",
            "JSON files (*.json);;All files (*)",
        )
        if not path:
            return
        try:
            preset = self._collect_preset_config()
            Path(path).write_text(preset.to_json(), encoding="utf-8")
            self._status_label.setText(f"Exported to: {Path(path).name}")
        except Exception as exc:
            QMessageBox.warning(self, "Export Error", str(exc))

    def _open_preset_folder(self) -> None:
        preset_dir = get_caption_preset_dir()
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(preset_dir)))
        except Exception:
            self._status_label.setText(f"Preset folder: {preset_dir}")

    def _apply_preset_to_ui(self, preset: PresetConfig) -> None:
        """Populate all UI controls from a PresetConfig."""
        self._font_name_edit.setText(preset.font_name)
        self._font_size_spin.setValue(preset.font_size)
        self._bold_cb.setChecked(preset.bold)
        self._italic_cb.setChecked(preset.italic)
        self._font_file_edit.setText(preset.font_file)
        self._primary_color_edit.setText(preset.primary_color)
        self._outline_color_edit.setText(preset.outline_color)
        self._shadow_color_edit.setText(preset.shadow_color)
        self._outline_px_spin.setValue(preset.outline_px)
        self._shadow_px_spin.setValue(preset.shadow_px)
        self._blur_px_spin.setValue(preset.blur_px)
        self._line_spacing_spin.setValue(preset.line_spacing)
        self._max_width_spin.setValue(preset.max_width_px)
        if len(preset.padding) == 4:
            self._pad_top_spin.setValue(preset.padding[0])
            self._pad_right_spin.setValue(preset.padding[1])
            self._pad_bottom_spin.setValue(preset.padding[2])
            self._pad_left_spin.setValue(preset.padding[3])

        # Alignment
        for i in range(self._alignment_combo.count()):
            if self._alignment_combo.itemData(i) == preset.alignment:
                self._alignment_combo.setCurrentIndex(i)
                break

        self._margin_l_spin.setValue(preset.margin_l)
        self._margin_r_spin.setValue(preset.margin_r)
        self._margin_v_spin.setValue(preset.margin_v)

        # Wrap style
        for i in range(self._wrap_style_combo.count()):
            if self._wrap_style_combo.itemData(i) == preset.wrap_style:
                self._wrap_style_combo.setCurrentIndex(i)
                break

        # Animation
        if preset.animation:
            atype = preset.animation.type
            idx = self._animation_type_combo.findText(atype)
            if idx >= 0:
                self._animation_type_combo.setCurrentIndex(idx)
            # Apply params after type change triggers param rebuild
            for key, val in preset.animation.params.items():
                if key in self._anim_param_spins:
                    self._anim_param_spins[key].setValue(float(val))

        self._update_preview_style()

    def _collect_preset_config(self) -> PresetConfig:
        """Collect a PresetConfig from the current UI state."""
        animation = None
        atype = self._animation_type_combo.currentText()
        if atype and atype != "(none)":
            params = {}
            for key, spin in self._anim_param_spins.items():
                params[key] = spin.value()
            animation = AnimationConfig(type=atype, params=params)

        return PresetConfig(
            font_file=self._font_file_edit.text(),
            font_name=self._font_name_edit.text(),
            font_size=self._font_size_spin.value(),
            bold=self._bold_cb.isChecked(),
            italic=self._italic_cb.isChecked(),
            primary_color=self._primary_color_edit.text(),
            outline_color=self._outline_color_edit.text(),
            shadow_color=self._shadow_color_edit.text(),
            outline_px=self._outline_px_spin.value(),
            shadow_px=self._shadow_px_spin.value(),
            blur_px=self._blur_px_spin.value(),
            line_spacing=self._line_spacing_spin.value(),
            max_width_px=self._max_width_spin.value(),
            padding=[
                self._pad_top_spin.value(),
                self._pad_right_spin.value(),
                self._pad_bottom_spin.value(),
                self._pad_left_spin.value(),
            ],
            alignment=self._alignment_combo.currentData() or 2,
            margin_l=self._margin_l_spin.value(),
            margin_r=self._margin_r_spin.value(),
            margin_v=self._margin_v_spin.value(),
            wrap_style=self._wrap_style_combo.currentData() or 2,
            animation=animation,
        )

    # ------------------------------------------------------------------
    # Animation controls
    # ------------------------------------------------------------------

    def _on_animation_type_changed(self, atype: str) -> None:
        """Rebuild dynamic parameter controls for the selected animation type."""
        # Clear existing
        for spin in self._anim_param_spins.values():
            spin.deleteLater()
        self._anim_param_spins.clear()

        # Clear layout items
        while self._anim_params_layout.count():
            item = self._anim_params_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not atype or atype == "(none)":
            return

        try:
            defaults = AnimationRegistry.get_defaults(atype)
        except ValueError:
            return

        for key, default_val in defaults.items():
            label = QLabel(f"{key}:")
            self._anim_params_layout.addWidget(label)
            spin = QDoubleSpinBox()
            spin.setRange(-10000, 10000)
            spin.setSingleStep(1.0)
            spin.setDecimals(1)
            spin.setValue(float(default_val))
            self._anim_params_layout.addWidget(spin)
            self._anim_param_spins[key] = spin

    # ------------------------------------------------------------------
    # File browsing
    # ------------------------------------------------------------------

    def _browse_subtitle(self) -> None:
        path = self._pick_session_or_file("subtitle", "Select Subtitle File", _SUBTITLE_FILTERS)
        if path is not None:
            self._subtitle_edit.setText(str(path))

    def _browse_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if path:
            self._output_dir_edit.setText(path)

    def _browse_font_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Font File", "",
            "Font files (*.ttf *.otf);;All files (*)"
        )
        if path:
            self._font_file_edit.setText(path)

    def _browse_audio_file(self) -> None:
        path = self._pick_session_or_file("audio", "Select Audio File", _AUDIO_FILTERS)
        if path is not None:
            self._audio_file_edit.setText(str(path))

    def _pick_session_or_file(
        self,
        category: str | None,
        title: str,
        file_filter: str,
    ) -> Path | None:
        ctx = self.session_context
        if ctx is None:
            path, _ = QFileDialog.getOpenFileName(self, title, "", file_filter)
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
    # Session context integration
    # ------------------------------------------------------------------

    def set_session_context(self, context: SessionContext) -> None:
        super().set_session_context(context)
        context.asset_added.connect(self._refresh_session_combos)
        context.asset_removed.connect(self._refresh_session_combos)
        self._refresh_session_combos()

    def _refresh_session_combos(self, _asset_id: str | None = None) -> None:
        ctx = self.session_context
        if ctx is None:
            return

        # Subtitle assets
        current_sub = self._session_subtitle_combo.currentText()
        self._session_subtitle_combo.blockSignals(True)
        self._session_subtitle_combo.clear()
        self._session_subtitle_combo.addItem("(none)")
        for asset in ctx.list_assets(category="subtitle"):
            self._session_subtitle_combo.addItem(asset.display_name, asset.id)
        idx = self._session_subtitle_combo.findText(current_sub)
        if idx >= 0:
            self._session_subtitle_combo.setCurrentIndex(idx)
        self._session_subtitle_combo.blockSignals(False)

        # Audio assets
        current_audio = self._session_audio_combo.currentText()
        self._session_audio_combo.blockSignals(True)
        self._session_audio_combo.clear()
        self._session_audio_combo.addItem("(none)")
        for asset in ctx.list_assets(category="audio"):
            self._session_audio_combo.addItem(asset.display_name, asset.id)
        idx = self._session_audio_combo.findText(current_audio)
        if idx >= 0:
            self._session_audio_combo.setCurrentIndex(idx)
        self._session_audio_combo.blockSignals(False)

    def _on_session_subtitle_changed(self, index: int) -> None:
        asset_id = self._session_subtitle_combo.currentData()
        if not asset_id or not self.session_context:
            return
        asset = self.session_context.get_asset(asset_id)
        if asset:
            self._subtitle_edit.setText(str(asset.path))

    def _on_session_audio_changed(self, index: int) -> None:
        asset_id = self._session_audio_combo.currentData()
        if not asset_id or not self.session_context:
            return
        asset = self.session_context.get_asset(asset_id)
        if asset:
            self._audio_file_edit.setText(str(asset.path))

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _update_preview_style(self) -> None:
        """Update the preview label to reflect current style settings."""
        color = self._primary_color_edit.text() or "#FFFFFF"
        outline = self._outline_color_edit.text() or "#000000"
        size = self._font_size_spin.value()
        font = self._font_name_edit.text() or "Arial"
        bold = "bold" if self._bold_cb.isChecked() else "normal"
        italic = "italic" if self._italic_cb.isChecked() else "normal"

        preview_size = max(12, min(size // 3, 32))
        self._preview_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {color};"
            f"  background-color: #333333;"
            f"  font-family: '{font}';"
            f"  font-size: {preview_size}px;"
            f"  font-weight: {bold};"
            f"  font-style: {italic};"
            f"  padding: 12px;"
            f"  border: 2px solid {outline};"
            f"  border-radius: 4px;"
            f"}}"
        )

    # ------------------------------------------------------------------
    # Render lifecycle
    # ------------------------------------------------------------------

    def _start_render(self) -> None:
        valid, msg = self.validate_settings()
        if not valid:
            QMessageBox.warning(self, "Validation Error", msg)
            return

        # Acquire shared job slot
        if not self._main_window.try_start_job(self.tab_id):
            return

        subtitle_path = Path(self._subtitle_edit.text().strip())
        output_dir = self._output_dir_edit.text().strip()
        if output_dir:
            out_parent = Path(output_dir)
        else:
            out_parent = subtitle_path.parent

        delivery_path = out_parent / f"{subtitle_path.stem}_caption.mp4"
        overlay_path = out_parent / f"{subtitle_path.stem}_caption_overlay.mov"

        # Build render config — use the preset name from builtin if selected
        preset_name = self._current_preset_name()

        config = RenderConfig(
            preset=preset_name,
            fps=self._fps_combo.currentText(),
            quality=self._quality_combo.currentData() or "small",
            safety_scale=self._safety_scale_spin.value(),
            apply_animation=self._apply_animation_cb.isChecked(),
            reskin=self._reskin_cb.isChecked(),
        )

        # Collect the full preset from UI for style parity
        preset_override = self._collect_preset_config()

        # Determine audio path for muxing or audio-reactive features
        audio_path = None
        if self._audio_file_edit.text().strip():
            audio_path = Path(self._audio_file_edit.text().strip())
        delivery_audio_path = audio_path if self._mux_audio_cb.isChecked() else None

        spec = CaptionRenderJobSpec(
            subtitle_path=subtitle_path,
            output_path=overlay_path,
            config=config,
            preset_override=preset_override,
            audio_path=audio_path if self._audio_reactive_group.isChecked() else None,
            delivery_output_path=delivery_path,
            delivery_audio_path=delivery_audio_path,
        )

        emitter = AppEventEmitter()
        worker = CaptionRenderWorker(spec=spec, emitter=emitter)
        self._active_worker = worker

        # Connect signals
        worker.signals.progress.connect(self._on_progress)
        worker.signals.stage.connect(self._on_stage)
        worker.signals.log.connect(self._on_log)
        worker.signals.completed.connect(self._on_render_completed)
        worker.signals.failed.connect(self._on_render_failed)
        worker.signals.canceled.connect(self._on_render_canceled)

        # Update UI
        self._start_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self._progress_bar.setValue(0)
        self._status_label.setText("Starting caption render...")

        # Show in global progress
        self._main_window.show_job_status(
            "caption_render", self.tab_id, f"Rendering captions for {subtitle_path.name}..."
        )

        self._thread_pool.start(worker)
        logger.info("Started CaptionRenderWorker for %s", subtitle_path.name)

    def cancel_job(self) -> None:
        if self._active_worker is not None:
            self._active_worker.cancel()
            self._status_label.setText("Cancelling...")
            logger.info("Cancel requested for CaptionRenderWorker")

    # ------------------------------------------------------------------
    # Worker signal handlers
    # ------------------------------------------------------------------

    def _on_progress(self, percent: float, message: str, data: dict) -> None:
        if percent >= 0:
            self._progress_bar.setValue(int(percent))
            self._main_window.update_job_progress(percent, message or "")
        if message:
            self._status_label.setText(message)

    def _on_stage(self, name: str, index: int, total: int, data: dict) -> None:
        self._status_label.setText(name)
        self._main_window.update_job_status(name)

    def _on_log(self, level: str, message: str, data: dict) -> None:
        logger.log(
            logging.getLevelName(level) if isinstance(level, str) else logging.INFO,
            "Caption Render: %s",
            message,
        )

    def _on_render_completed(self, data: dict) -> None:
        self._active_worker = None
        self._start_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._progress_bar.setValue(100)

        output_path = data.get("output_path", "")
        delivery_path = data.get("delivery_path", output_path)
        overlay_path = data.get("overlay_path", "")
        width = data.get("width", 0)
        height = data.get("height", 0)
        duration_ms = data.get("duration_ms", 0)
        quality = data.get("quality", "small")
        has_alpha = data.get("overlay_has_alpha", data.get("has_alpha", True))
        preset_name = self._current_preset_name()
        alpha_expected = quality != "medium"

        self._status_label.setText(
            f"Render complete: {Path(delivery_path).name} ({width}x{height})"
        )
        self._main_window.show_job_completed(
            f"Caption render complete: {Path(delivery_path).name}",
            output_path=delivery_path,
            owner_tab_id=self.tab_id,
        )

        # Register the user-facing delivery asset.
        if delivery_path and Path(delivery_path).exists():
            self.register_output_asset(
                SessionAsset(
                    id=str(uuid.uuid4()),
                    display_name=Path(delivery_path).name,
                    path=Path(delivery_path),
                    category="video",
                    source_tab=self.tab_id,
                    has_audio=data.get("delivery_has_audio", False),
                    width=width,
                    height=height,
                    duration_ms=duration_ms,
                    has_alpha=False,
                    metadata={
                        "quality": quality,
                        "quality_tier": quality,
                        "preset_name": preset_name,
                        "render_quality": quality,
                        "alpha_expected": alpha_expected,
                        "delivery": True,
                        "fps": self._fps_combo.currentText(),
                    },
                )
            )

        # Register the composition-facing overlay intermediate separately.
        if overlay_path and Path(overlay_path).exists():
            self.register_output_asset(
                SessionAsset(
                    id=str(uuid.uuid4()),
                    display_name=Path(overlay_path).name,
                    path=Path(overlay_path),
                    category="video",
                    source_tab=self.tab_id,
                    role="caption_overlay",
                    width=width,
                    height=height,
                    duration_ms=duration_ms,
                    has_alpha=has_alpha,
                    is_overlay_ready=quality == "large",
                    preferred_for_overlay=quality == "large",
                    metadata={
                        "quality": quality,
                        "quality_tier": quality,
                        "preset_name": preset_name,
                        "render_quality": quality,
                        "alpha_expected": alpha_expected,
                        "delivery_path": delivery_path,
                        "fps": self._fps_combo.currentText(),
                    },
                )
            )

        logger.info("Caption render completed: %s", delivery_path)

    def _on_render_failed(self, error_message: str, data: dict) -> None:
        self._active_worker = None
        self._start_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._progress_bar.setValue(0)
        self._status_label.setText(f"Failed: {error_message}")
        self._main_window.show_job_failed(
            f"Caption render error: {error_message}",
            owner_tab_id=self.tab_id,
        )
        logger.error("Caption render failed: %s", error_message)

    def _on_render_canceled(self, message: str) -> None:
        self._active_worker = None
        self._start_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._progress_bar.setValue(0)
        self._status_label.setText(f"Cancelled: {message}")
        self._main_window.show_job_canceled(
            f"Caption render cancelled: {message}",
            owner_tab_id=self.tab_id,
        )
        logger.info("Caption render cancelled: %s", message)

    # ------------------------------------------------------------------
    # BaseTab contract
    # ------------------------------------------------------------------

    def validate_settings(self) -> tuple[bool, str]:
        sub_path = self._subtitle_edit.text().strip()
        if not sub_path:
            return False, "No subtitle file selected."
        p = Path(sub_path)
        if p.suffix.lower() not in (".srt", ".ass"):
            return False, "Subtitle file must be .srt or .ass."
        if self._mux_audio_cb.isChecked() and not self._audio_file_edit.text().strip():
            return False, "Select an audio file before enabling delivery audio mux."
        return True, ""

    def collect_settings(self) -> dict[str, Any]:
        return {
            "subtitle_path": self._subtitle_edit.text(),
            "session_subtitle": self._session_subtitle_combo.currentText(),
            "output_dir": self._output_dir_edit.text(),
            "fps": self._fps_combo.currentText(),
            "quality": self._quality_combo.currentData() or "small",
            "safety_scale": self._safety_scale_spin.value(),
            "reskin": self._reskin_cb.isChecked(),
            "preset_source": self._preset_source_combo.currentText(),
            "builtin_preset": self._builtin_preset_combo.currentText(),
            "preset_file": self._preset_file_edit.text(),
            "library_preset": self._library_combo.currentText(),
            "font": {
                "name": self._font_name_edit.text(),
                "size": self._font_size_spin.value(),
                "bold": self._bold_cb.isChecked(),
                "italic": self._italic_cb.isChecked(),
                "file": self._font_file_edit.text(),
            },
            "colors": {
                "primary": self._primary_color_edit.text(),
                "outline": self._outline_color_edit.text(),
                "shadow": self._shadow_color_edit.text(),
            },
            "styling": {
                "outline_px": self._outline_px_spin.value(),
                "shadow_px": self._shadow_px_spin.value(),
                "blur_px": self._blur_px_spin.value(),
            },
            "layout": {
                "line_spacing": self._line_spacing_spin.value(),
                "max_width_px": self._max_width_spin.value(),
                "padding": [
                    self._pad_top_spin.value(),
                    self._pad_right_spin.value(),
                    self._pad_bottom_spin.value(),
                    self._pad_left_spin.value(),
                ],
                "alignment": self._alignment_combo.currentData() or 2,
                "margin_l": self._margin_l_spin.value(),
                "margin_r": self._margin_r_spin.value(),
                "margin_v": self._margin_v_spin.value(),
                "wrap_style": self._wrap_style_combo.currentData() or 2,
            },
            "animation": {
                "apply": self._apply_animation_cb.isChecked(),
                "type": self._animation_type_combo.currentText(),
                "params": {
                    k: spin.value() for k, spin in self._anim_param_spins.items()
                },
            },
            "mux_audio": self._mux_audio_cb.isChecked(),
            "audio_reactive": {
                "enabled": self._audio_reactive_group.isChecked(),
                "audio_path": self._audio_file_edit.text(),
                "session_audio": self._session_audio_combo.currentText(),
            },
        }

    def apply_settings(self, data: dict[str, Any]) -> None:
        self._subtitle_edit.setText(data.get("subtitle_path", ""))
        self._output_dir_edit.setText(data.get("output_dir", ""))

        # Session subtitle
        session_sub = data.get("session_subtitle", "(none)")
        idx = self._session_subtitle_combo.findText(session_sub)
        if idx >= 0:
            self._session_subtitle_combo.setCurrentIndex(idx)

        # FPS
        fps = data.get("fps", "30")
        idx = self._fps_combo.findText(fps)
        if idx >= 0:
            self._fps_combo.setCurrentIndex(idx)

        # Quality
        quality = data.get("quality", "small")
        for i in range(self._quality_combo.count()):
            if self._quality_combo.itemData(i) == quality:
                self._quality_combo.setCurrentIndex(i)
                break

        self._safety_scale_spin.setValue(data.get("safety_scale", 1.12))
        self._reskin_cb.setChecked(data.get("reskin", False))

        # Preset source
        source = data.get("preset_source", "Built-in")
        idx = self._preset_source_combo.findText(source)
        if idx >= 0:
            self._preset_source_combo.setCurrentIndex(idx)

        builtin = data.get("builtin_preset", "")
        idx = self._builtin_preset_combo.findText(builtin)
        if idx >= 0:
            self._builtin_preset_combo.setCurrentIndex(idx)

        self._preset_file_edit.setText(data.get("preset_file", ""))

        lib = data.get("library_preset", "")
        idx = self._library_combo.findText(lib)
        if idx >= 0:
            self._library_combo.setCurrentIndex(idx)

        # Font
        font_data = data.get("font", {})
        self._font_name_edit.setText(font_data.get("name", "Arial"))
        self._font_size_spin.setValue(font_data.get("size", 64))
        self._bold_cb.setChecked(font_data.get("bold", False))
        self._italic_cb.setChecked(font_data.get("italic", False))
        self._font_file_edit.setText(font_data.get("file", ""))

        # Colors
        colors = data.get("colors", {})
        self._primary_color_edit.setText(colors.get("primary", "#FFFFFF"))
        self._outline_color_edit.setText(colors.get("outline", "#000000"))
        self._shadow_color_edit.setText(colors.get("shadow", "#000000"))

        # Styling
        styling = data.get("styling", {})
        self._outline_px_spin.setValue(styling.get("outline_px", 4.0))
        self._shadow_px_spin.setValue(styling.get("shadow_px", 2.0))
        self._blur_px_spin.setValue(styling.get("blur_px", 0.0))

        # Layout
        layout_data = data.get("layout", {})
        self._line_spacing_spin.setValue(layout_data.get("line_spacing", 8))
        self._max_width_spin.setValue(layout_data.get("max_width_px", 1200))
        padding = layout_data.get("padding", [40, 60, 50, 60])
        if len(padding) == 4:
            self._pad_top_spin.setValue(padding[0])
            self._pad_right_spin.setValue(padding[1])
            self._pad_bottom_spin.setValue(padding[2])
            self._pad_left_spin.setValue(padding[3])

        alignment = layout_data.get("alignment", 2)
        for i in range(self._alignment_combo.count()):
            if self._alignment_combo.itemData(i) == alignment:
                self._alignment_combo.setCurrentIndex(i)
                break

        self._margin_l_spin.setValue(layout_data.get("margin_l", 0))
        self._margin_r_spin.setValue(layout_data.get("margin_r", 0))
        self._margin_v_spin.setValue(layout_data.get("margin_v", 0))

        wrap = layout_data.get("wrap_style", 2)
        for i in range(self._wrap_style_combo.count()):
            if self._wrap_style_combo.itemData(i) == wrap:
                self._wrap_style_combo.setCurrentIndex(i)
                break

        # Animation
        anim_data = data.get("animation", {})
        self._apply_animation_cb.setChecked(anim_data.get("apply", True))
        atype = anim_data.get("type", "fade")
        idx = self._animation_type_combo.findText(atype)
        if idx >= 0:
            self._animation_type_combo.setCurrentIndex(idx)
        anim_params = anim_data.get("params", {})
        for key, val in anim_params.items():
            if key in self._anim_param_spins:
                self._anim_param_spins[key].setValue(float(val))

        # Audio-reactive
        ar = data.get("audio_reactive", {})
        self._audio_reactive_group.setChecked(ar.get("enabled", False))
        self._audio_file_edit.setText(ar.get("audio_path", ""))
        self._mux_audio_cb.setChecked(data.get("mux_audio", False))
        session_audio = ar.get("session_audio", "(none)")
        idx = self._session_audio_combo.findText(session_audio)
        if idx >= 0:
            self._session_audio_combo.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    # Global busy
    # ------------------------------------------------------------------

    def set_global_busy(self, is_busy: bool, owner_tab_id: str | None = None) -> None:
        if owner_tab_id == self.tab_id:
            return
        self._start_btn.setEnabled(not is_busy)

    def _current_preset_name(self) -> str:
        source_idx = self._preset_source_combo.currentIndex()
        if source_idx == 0:
            return self._builtin_preset_combo.currentText() or "modern_box"
        if source_idx == 1:
            preset_path = self._preset_file_edit.text().strip()
            return Path(preset_path).stem if preset_path else "custom"
        preset_name = self._library_combo.currentText().strip()
        return Path(preset_name).stem if preset_name else "library"
