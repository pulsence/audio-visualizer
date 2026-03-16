"""Audio Visualizer tab — full workflow extracted from the old MainWindow.

Owns general settings, general visualizer settings, per-type specific
visualizer views (lazy-loaded), a live preview panel, and render controls.
Delegates job lifecycle to the main-window shell.
"""
from __future__ import annotations

import importlib
import logging
import time
import uuid
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer, QSize, QUrl
from PySide6.QtWidgets import (
    QGridLayout, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QCheckBox, QComboBox, QSlider, QWidget,
    QSizePolicy, QMessageBox,
)
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from audio_visualizer.ui.tabs.baseTab import BaseTab
from audio_visualizer.ui.views import Fonts
from audio_visualizer.ui.views.general.generalSettingViews import GeneralSettingsView, GeneralSettings
from audio_visualizer.ui.views.general.generalVisualizerView import GeneralVisualizerView, GeneralVisualizerSettings
from audio_visualizer.visualizers.utilities import AudioData, VideoData, VisualizerOptions
from audio_visualizer.app_paths import get_data_dir

logger = logging.getLogger(__name__)


class AudioVisualizerTab(BaseTab):
    """Complete Audio Visualizer workflow tab.

    Provides the same grid layout, visualizer registry, settings
    persistence, live preview, and render orchestration that previously
    lived directly in ``MainWindow``.
    """

    _VIEW_ATTRIBUTE_MAP = {
        "rectangleVolumeVisualizerView": VisualizerOptions.VOLUME_RECTANGLE,
        "circleVolumeVisualizerView": VisualizerOptions.VOLUME_CIRCLE,
        "lineVolumeVisualizerView": VisualizerOptions.VOLUME_LINE,
        "forceLineVolumeVisualizerView": VisualizerOptions.VOLUME_FORCE_LINE,
        "rectangleChromaVisualizerView": VisualizerOptions.CHROMA_RECTANGLE,
        "circleChromaVisualizerView": VisualizerOptions.CHROMA_CIRCLE,
        "lineChromaVisualizerView": VisualizerOptions.CHROMA_LINE,
        "lineChromaBandsVisualizerView": VisualizerOptions.CHROMA_LINES,
        "forceRectangleChromaVisualizerView": VisualizerOptions.CHROMA_FORCE_RECTANGLE,
        "forceCircleChromaVisualizerView": VisualizerOptions.CHROMA_FORCE_CIRCLE,
        "forceLineChromaVisualizerView": VisualizerOptions.CHROMA_FORCE_LINE,
        "forceLinesChromaVisualizerView": VisualizerOptions.CHROMA_FORCE_LINES,
        "waveformVisualizerView": VisualizerOptions.WAVEFORM,
        "combinedVisualizerView": VisualizerOptions.COMBINED_RECTANGLE,
    }
    _VIEW_CLASS_REGISTRY = {
        VisualizerOptions.VOLUME_RECTANGLE: (
            "audio_visualizer.ui.views.volume.rectangleVolumeVisualizerView",
            "RectangleVolumeVisualizerView",
        ),
        VisualizerOptions.VOLUME_CIRCLE: (
            "audio_visualizer.ui.views.volume.circleVolumeVisualizerView",
            "CircleVolumeVisualizerView",
        ),
        VisualizerOptions.VOLUME_LINE: (
            "audio_visualizer.ui.views.volume.lineVolumeVisualizerView",
            "LineVolumeVisualizerView",
        ),
        VisualizerOptions.VOLUME_FORCE_LINE: (
            "audio_visualizer.ui.views.volume.forceLineVolumeVisualizerView",
            "ForceLineVolumeVisualizerView",
        ),
        VisualizerOptions.CHROMA_RECTANGLE: (
            "audio_visualizer.ui.views.chroma.rectangleChromaVisualizerView",
            "RectangleChromaVisualizerView",
        ),
        VisualizerOptions.CHROMA_CIRCLE: (
            "audio_visualizer.ui.views.chroma.circleChromaVisualizerView",
            "CircleChromeVisualizerView",
        ),
        VisualizerOptions.CHROMA_LINE: (
            "audio_visualizer.ui.views.chroma.lineChromaVisualizerView",
            "LineChromaVisualizerView",
        ),
        VisualizerOptions.CHROMA_LINES: (
            "audio_visualizer.ui.views.chroma.lineChromaBandsVisualizerView",
            "LineChromaBandsVisualizerView",
        ),
        VisualizerOptions.CHROMA_FORCE_RECTANGLE: (
            "audio_visualizer.ui.views.chroma.forceRectangleChromaVisualizerView",
            "ForceRectangleChromaVisualizerView",
        ),
        VisualizerOptions.CHROMA_FORCE_CIRCLE: (
            "audio_visualizer.ui.views.chroma.forceCircleChromaVisualizerView",
            "ForceCircleChromaVisualizerView",
        ),
        VisualizerOptions.CHROMA_FORCE_LINE: (
            "audio_visualizer.ui.views.chroma.forceLineChromaVisualizerView",
            "ForceLineChromaVisualizerView",
        ),
        VisualizerOptions.CHROMA_FORCE_LINES: (
            "audio_visualizer.ui.views.chroma.forceLinesChromaVisualizerView",
            "ForceLinesChromaVisualizerView",
        ),
        VisualizerOptions.WAVEFORM: (
            "audio_visualizer.ui.views.general.waveformVisualizerView",
            "WaveformVisualizerView",
        ),
        VisualizerOptions.COMBINED_RECTANGLE: (
            "audio_visualizer.ui.views.general.combinedVisualizerView",
            "CombinedVisualizerView",
        ),
    }
    _VIEW_OPTION_TO_ATTRIBUTE = {
        option: name for name, option in _VIEW_ATTRIBUTE_MAP.items()
    }

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def tab_id(self) -> str:
        return "audio_visualizer"

    @property
    def tab_title(self) -> str:
        return "Audio Visualizer"

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._main_window = parent
        self._visualizer_views: dict[VisualizerOptions, Any] = {}
        self._visualizer_view_layout: QGridLayout | None = None
        for attribute_name in self._VIEW_ATTRIBUTE_MAP:
            setattr(self, attribute_name, None)

        self.rendering = False
        self._show_output_for_last_render = True
        self._active_preview = False
        self._active_render_worker = None
        self._pending_preview_refresh = False
        self._render_includes_audio = False

        primary_layout = QGridLayout()

        # Row 0 col 0: general settings
        self._prepare_general_settings_elements(primary_layout, r=0, c=0)
        # Row 0 col 1: general visualizer settings
        self._prepare_general_visualizer_elements(primary_layout, r=0, c=1)
        # Row 1 col 1: specific visualizer settings
        self._prepare_specific_visualizer_elements(primary_layout, r=1, c=1)
        # Row 1 col 0: live preview panel
        self._prepare_preview_panel_elements(primary_layout, r=1, c=0)
        # Row 2 col 0: render controls
        self._prepare_render_elements(primary_layout, r=2, c=0)

        # Push content to top
        primary_layout.setRowStretch(3, 1)

        self.setLayout(primary_layout)

        # Live preview timer
        self._preview_update_timer = QTimer(self)
        self._preview_update_timer.setSingleShot(True)
        self._preview_update_timer.setInterval(400)
        self._preview_update_timer.timeout.connect(self._trigger_live_preview_update)

        self._connect_live_preview_updates()

    # ------------------------------------------------------------------
    # Layout builders
    # ------------------------------------------------------------------

    def _prepare_general_settings_elements(self, layout: QGridLayout, r: int = 1, c: int = 0) -> None:
        self.generalSettingsView = GeneralSettingsView()
        layout.addLayout(self.generalSettingsView.get_view_in_layout(), r, c)

    def _prepare_general_visualizer_elements(self, layout: QGridLayout, r: int = 1, c: int = 1) -> None:
        self.generalVisualizerView = GeneralVisualizerView(self)
        layout.addLayout(self.generalVisualizerView.get_view_in_layout(), r, c)

    def _prepare_specific_visualizer_elements(self, layout: QGridLayout, r: int = 2, c: int = 1) -> None:
        main_layout = QGridLayout()

        section_label = QLabel("Selected Visualizer Settings")
        section_label.setFont(Fonts.h2_font)
        section_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        section_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        main_layout.addWidget(section_label, 0, 0)

        self._visualizer_view_layout = QGridLayout()
        self._visualizer_view_container = QWidget()
        self._visualizer_view_container.setLayout(self._visualizer_view_layout)
        main_layout.addWidget(self._visualizer_view_container, 1, 0)

        layout.addLayout(main_layout, r, c)
        current = VisualizerOptions(self.generalVisualizerView.visualizer.currentText())
        self._show_visualizer_view(current)

    def _prepare_preview_panel_elements(self, layout: QGridLayout, r: int = 2, c: int = 0) -> None:
        preview_group = QGroupBox("Live Preview")
        preview_layout = QVBoxLayout()

        self.preview_panel_body = QWidget()
        body_layout = QVBoxLayout()
        self.preview_video_widget = QVideoWidget()
        body_layout.addWidget(self.preview_video_widget)

        volume_row = QHBoxLayout()
        volume_label = QLabel("Preview Volume")
        volume_row.addWidget(volume_label)
        self.preview_volume_slider = QSlider()
        self.preview_volume_slider.setOrientation(Qt.Orientation.Horizontal)
        self.preview_volume_slider.setRange(0, 100)
        self.preview_volume_slider.setValue(0)
        volume_row.addWidget(self.preview_volume_slider)
        body_layout.addLayout(volume_row)

        self.preview_panel_body.setLayout(body_layout)
        preview_layout.addWidget(self.preview_panel_body)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group, r, c)

        self._preview_player = QMediaPlayer()
        self._preview_audio_output = QAudioOutput()
        self._preview_player.setAudioOutput(self._preview_audio_output)
        self._preview_player.setVideoOutput(self.preview_video_widget)
        self._preview_player.setLoops(QMediaPlayer.Loops.Infinite)
        self.preview_volume_slider.valueChanged.connect(self._preview_volume_changed)
        self._preview_volume_changed(self.preview_volume_slider.value())

    def _prepare_render_elements(self, layout: QGridLayout, r: int = 2, c: int = 0) -> None:
        render_section_layout = QGridLayout()

        self.preview_checkbox = QCheckBox("Preview Video (30 seconds)")
        self.preview_checkbox.setChecked(True)
        render_section_layout.addWidget(self.preview_checkbox, 0, 0)

        self.preview_panel_toggle = QCheckBox("Show Live Preview Panel")
        self.preview_panel_toggle.setChecked(True)
        self.preview_panel_toggle.stateChanged.connect(self._toggle_preview_panel)
        render_section_layout.addWidget(self.preview_panel_toggle, 0, 1)

        self.show_output_checkbox = QCheckBox("Show Rendered Video")
        self.show_output_checkbox.setChecked(True)
        render_section_layout.addWidget(self.show_output_checkbox, 1, 0)

        self.render_button = QPushButton("Render Video")
        self.render_button.clicked.connect(self.render_video)
        render_section_layout.addWidget(self.render_button, 1, 1)

        self.cancel_button = QPushButton("Cancel Render")
        self.cancel_button.clicked.connect(self.cancel_render)
        self.cancel_button.hide()
        render_section_layout.addWidget(self.cancel_button, 2, 0, 1, 2)

        layout.addLayout(render_section_layout, r, c)

    # ------------------------------------------------------------------
    # Visualizer view factory / registry
    # ------------------------------------------------------------------

    def _build_visualizer_view(self, visualizer: VisualizerOptions) -> Any:
        module_name, class_name = self._VIEW_CLASS_REGISTRY[visualizer]
        module = importlib.import_module(module_name)
        view_class = getattr(module, class_name)
        return view_class()

    def _get_visualizer_view(self, visualizer: VisualizerOptions) -> Any:
        view = self._visualizer_views.get(visualizer)
        if view is None:
            view = self._build_visualizer_view(visualizer)
            widget = view.get_view_in_widget()
            widget.hide()
            self._visualizer_view_layout.addWidget(widget, 0, 0)
            self._visualizer_views[visualizer] = view
            attribute_name = self._VIEW_OPTION_TO_ATTRIBUTE.get(visualizer)
            if attribute_name:
                setattr(self, attribute_name, view)
        return view

    def _show_visualizer_view(self, visualizer: VisualizerOptions) -> None:
        for view in self._visualizer_views.values():
            view.get_view_in_widget().hide()
        view = self._get_visualizer_view(visualizer)
        view.get_view_in_widget().show()

    def visualizer_selection_changed(self, visualizer: str) -> None:
        if self._visualizer_view_layout is None:
            return
        visualizer_opt = VisualizerOptions(visualizer)
        self._show_visualizer_view(visualizer_opt)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_settings(self) -> tuple[bool, str]:
        return self.validate_render_settings()

    def validate_render_settings(self) -> tuple[bool, str]:
        if not self.generalSettingsView.validate_view():
            return False, self.generalSettingsView.last_error or "General settings are invalid."
        if not self.generalVisualizerView.validate_view():
            return False, "General visualization settings are invalid."

        selected = VisualizerOptions(self.generalVisualizerView.visualizer.currentText())
        error_map = {
            VisualizerOptions.VOLUME_RECTANGLE: "Rectangle volume settings are invalid.",
            VisualizerOptions.VOLUME_CIRCLE: "Circle volume settings are invalid.",
            VisualizerOptions.VOLUME_LINE: "Smooth line volume settings are invalid.",
            VisualizerOptions.VOLUME_FORCE_LINE: "Force line volume settings are invalid.",
            VisualizerOptions.CHROMA_RECTANGLE: "Rectangle chroma settings are invalid.",
            VisualizerOptions.CHROMA_CIRCLE: "Circle chroma settings are invalid.",
            VisualizerOptions.CHROMA_LINE: "Smooth line chroma settings are invalid.",
            VisualizerOptions.CHROMA_LINES: "Chroma lines settings are invalid.",
            VisualizerOptions.CHROMA_FORCE_RECTANGLE: "Force rectangle chroma settings are invalid.",
            VisualizerOptions.CHROMA_FORCE_CIRCLE: "Force circle chroma settings are invalid.",
            VisualizerOptions.CHROMA_FORCE_LINE: "Force line chroma settings are invalid.",
            VisualizerOptions.CHROMA_FORCE_LINES: "Force lines chroma settings are invalid.",
            VisualizerOptions.WAVEFORM: "Waveform settings are invalid.",
            VisualizerOptions.COMBINED_RECTANGLE: "Combined settings are invalid.",
        }
        if selected in error_map:
            if not self._get_visualizer_view(selected).validate_view():
                return False, error_map[selected]

        return True, ""

    # ------------------------------------------------------------------
    # Visualizer construction
    # ------------------------------------------------------------------

    def _create_visualizer(self, audio_data: AudioData, video_data: VideoData,
                           visualizer_settings: GeneralVisualizerSettings) -> Any:
        from audio_visualizer.visualizers import volume, chroma, waveform, combined
        if visualizer_settings.visualizer_type == VisualizerOptions.VOLUME_RECTANGLE:
            settings = self.rectangleVolumeVisualizerView.read_view_values()

            return volume.RectangleVisualizer(
                audio_data, video_data, visualizer_settings.x, visualizer_settings.y,
                super_sampling=visualizer_settings.super_sampling,
                box_height=settings.box_height, box_width=settings.box_width,
                corner_radius=settings.corner_radius,
                border_width=visualizer_settings.border_width, spacing=visualizer_settings.spacing,
                bg_color=visualizer_settings.bg_color, border_color=visualizer_settings.border_color,
                alignment=visualizer_settings.alignment, flow=settings.flow
            )
        elif visualizer_settings.visualizer_type == VisualizerOptions.VOLUME_CIRCLE:
            settings = self.circleVolumeVisualizerView.read_view_values()

            return volume.CircleVisualizer(
                audio_data, video_data, visualizer_settings.x, visualizer_settings.y,
                super_sampling=visualizer_settings.super_sampling,
                max_radius=settings.radius, border_width=visualizer_settings.border_width,
                spacing=visualizer_settings.spacing,
                bg_color=visualizer_settings.bg_color, border_color=visualizer_settings.border_color,
                alignment=visualizer_settings.alignment, flow=settings.flow
            )
        elif visualizer_settings.visualizer_type == VisualizerOptions.VOLUME_LINE:
            settings = self.lineVolumeVisualizerView.read_view_values()

            return volume.LineVisualizer(
                audio_data, video_data, visualizer_settings.x, visualizer_settings.y,
                super_sampling=visualizer_settings.super_sampling,
                max_height=settings.max_height, line_thickness=settings.line_thickness,
                spacing=visualizer_settings.spacing,
                color=visualizer_settings.bg_color,
                alignment=visualizer_settings.alignment, flow=settings.flow,
                smoothness=settings.smoothness
            )
        elif visualizer_settings.visualizer_type == VisualizerOptions.VOLUME_FORCE_LINE:
            settings = self.forceLineVolumeVisualizerView.read_view_values()

            return volume.ForceLineVisualizer(
                audio_data, video_data, visualizer_settings.x, visualizer_settings.y,
                super_sampling=visualizer_settings.super_sampling,
                line_thickness=settings.line_thickness,
                points_count=settings.points_count,
                color=visualizer_settings.bg_color,
                alignment=visualizer_settings.alignment,
                flow=settings.flow,
                tension=settings.tension,
                damping=settings.damping,
                impulse_strength=settings.impulse_strength,
                gravity=settings.gravity,
            )
        elif visualizer_settings.visualizer_type == VisualizerOptions.CHROMA_RECTANGLE:
            settings = self.rectangleChromaVisualizerView.read_view_values()

            return chroma.RectangleVisualizer(
                audio_data, video_data, visualizer_settings.x, visualizer_settings.y,
                super_sampling=visualizer_settings.super_sampling,
                box_height=settings.box_height,
                corner_radius=settings.corner_radius,
                border_width=visualizer_settings.border_width, spacing=visualizer_settings.spacing,
                bg_color=visualizer_settings.bg_color, border_color=visualizer_settings.border_color,
                alignment=visualizer_settings.alignment,
                color_mode=settings.color_mode,
                gradient_start=settings.gradient_start,
                gradient_end=settings.gradient_end,
                band_colors=settings.band_colors,
            )
        elif visualizer_settings.visualizer_type == VisualizerOptions.CHROMA_CIRCLE:
            settings = self.circleChromaVisualizerView.read_view_values()

            return chroma.CircleVisualizer(
                audio_data, video_data, visualizer_settings.x, visualizer_settings.y,
                super_sampling=visualizer_settings.super_sampling,
                border_width=visualizer_settings.border_width,
                spacing=visualizer_settings.spacing,
                bg_color=visualizer_settings.bg_color, border_color=visualizer_settings.border_color,
                alignment=visualizer_settings.alignment,
                color_mode=settings.color_mode,
                gradient_start=settings.gradient_start,
                gradient_end=settings.gradient_end,
                band_colors=settings.band_colors,
            )
        elif visualizer_settings.visualizer_type == VisualizerOptions.CHROMA_LINE:
            settings = self.lineChromaVisualizerView.read_view_values()

            return chroma.LineVisualizer(
                audio_data, video_data, visualizer_settings.x, visualizer_settings.y,
                super_sampling=visualizer_settings.super_sampling,
                max_height=settings.max_height, line_thickness=settings.line_thickness,
                color=visualizer_settings.bg_color,
                alignment=visualizer_settings.alignment,
                smoothness=settings.smoothness,
                color_mode=settings.color_mode,
                gradient_start=settings.gradient_start,
                gradient_end=settings.gradient_end,
                band_colors=settings.band_colors,
            )
        elif visualizer_settings.visualizer_type == VisualizerOptions.CHROMA_LINES:
            settings = self.lineChromaBandsVisualizerView.read_view_values()

            return chroma.LineBandsVisualizer(
                audio_data, video_data, visualizer_settings.x, visualizer_settings.y,
                super_sampling=visualizer_settings.super_sampling,
                max_height=settings.max_height, line_thickness=settings.line_thickness,
                spacing=visualizer_settings.spacing,
                color=visualizer_settings.bg_color,
                alignment=visualizer_settings.alignment,
                flow=settings.flow,
                smoothness=settings.smoothness,
                band_spacing=settings.band_spacing,
                band_colors=settings.band_colors,
            )
        elif visualizer_settings.visualizer_type == VisualizerOptions.CHROMA_FORCE_RECTANGLE:
            settings = self.forceRectangleChromaVisualizerView.read_view_values()

            return chroma.ForceRectangleVisualizer(
                audio_data, video_data, visualizer_settings.x, visualizer_settings.y,
                super_sampling=visualizer_settings.super_sampling,
                box_height=settings.box_height,
                corner_radius=settings.corner_radius,
                border_width=visualizer_settings.border_width,
                spacing=visualizer_settings.spacing,
                bg_color=visualizer_settings.bg_color,
                border_color=visualizer_settings.border_color,
                alignment=visualizer_settings.alignment,
                color_mode=settings.color_mode,
                gradient_start=settings.gradient_start,
                gradient_end=settings.gradient_end,
                band_colors=settings.band_colors,
                gravity=settings.gravity,
                force_strength=settings.force_strength,
            )
        elif visualizer_settings.visualizer_type == VisualizerOptions.CHROMA_FORCE_CIRCLE:
            settings = self.forceCircleChromaVisualizerView.read_view_values()

            return chroma.ForceCircleVisualizer(
                audio_data, video_data, visualizer_settings.x, visualizer_settings.y,
                super_sampling=visualizer_settings.super_sampling,
                border_width=visualizer_settings.border_width,
                spacing=visualizer_settings.spacing,
                bg_color=visualizer_settings.bg_color,
                border_color=visualizer_settings.border_color,
                alignment=visualizer_settings.alignment,
                color_mode=settings.color_mode,
                gradient_start=settings.gradient_start,
                gradient_end=settings.gradient_end,
                band_colors=settings.band_colors,
                gravity=settings.gravity,
                force_strength=settings.force_strength,
            )
        elif visualizer_settings.visualizer_type == VisualizerOptions.CHROMA_FORCE_LINE:
            settings = self.forceLineChromaVisualizerView.read_view_values()

            return chroma.ForceLineVisualizer(
                audio_data, video_data, visualizer_settings.x, visualizer_settings.y,
                super_sampling=visualizer_settings.super_sampling,
                line_thickness=settings.line_thickness,
                points_count=settings.points_count,
                color=visualizer_settings.bg_color,
                alignment=visualizer_settings.alignment,
                tension=settings.tension,
                damping=settings.damping,
                force_strength=settings.force_strength,
                gravity=settings.gravity,
                smoothness=settings.smoothness,
            )
        elif visualizer_settings.visualizer_type == VisualizerOptions.CHROMA_FORCE_LINES:
            settings = self.forceLinesChromaVisualizerView.read_view_values()

            return chroma.ForceLinesVisualizer(
                audio_data, video_data, visualizer_settings.x, visualizer_settings.y,
                super_sampling=visualizer_settings.super_sampling,
                line_thickness=settings.line_thickness,
                points_count=settings.points_count,
                color=visualizer_settings.bg_color,
                alignment=visualizer_settings.alignment,
                tension=settings.tension,
                damping=settings.damping,
                force_strength=settings.force_strength,
                gravity=settings.gravity,
                smoothness=settings.smoothness,
                band_spacing=settings.band_spacing,
                band_colors=settings.band_colors,
            )
        elif visualizer_settings.visualizer_type == VisualizerOptions.WAVEFORM:
            settings = self.waveformVisualizerView.read_view_values()

            return waveform.WaveformVisualizer(
                audio_data, video_data, visualizer_settings.x, visualizer_settings.y,
                line_thickness=settings.line_thickness,
                super_sampling=visualizer_settings.super_sampling,
                color=visualizer_settings.bg_color,
                alignment=visualizer_settings.alignment
            )
        elif visualizer_settings.visualizer_type == VisualizerOptions.COMBINED_RECTANGLE:
            settings = self.combinedVisualizerView.read_view_values()

            return combined.RectangleVisualizer(
                audio_data, video_data, visualizer_settings.x, visualizer_settings.y,
                super_sampling=visualizer_settings.super_sampling,
                box_height=settings.box_height, box_width=settings.box_width,
                corner_radius=settings.corner_radius,
                chroma_box_height=settings.chroma_box_height,
                chroma_corner_radius=settings.chroma_corner_radius,
                border_width=visualizer_settings.border_width, spacing=visualizer_settings.spacing,
                volume_color=visualizer_settings.bg_color,
                chroma_color=visualizer_settings.border_color,
                border_color=visualizer_settings.border_color,
                alignment=visualizer_settings.alignment, flow=settings.flow
            )
        return None

    # ------------------------------------------------------------------
    # Settings collection (BaseTab contract)
    # ------------------------------------------------------------------

    def collect_settings(self) -> dict[str, Any]:
        general = self.generalSettingsView.read_view_values()
        visualizer = self.generalVisualizerView.read_view_values()

        specific: dict[str, Any] = {}
        selected = visualizer.visualizer_type
        if selected == VisualizerOptions.VOLUME_RECTANGLE:
            settings = self.rectangleVolumeVisualizerView.read_view_values()
            specific = {
                "box_height": settings.box_height,
                "box_width": settings.box_width,
                "corner_radius": settings.corner_radius,
                "flow": settings.flow.value,
            }
        elif selected == VisualizerOptions.VOLUME_CIRCLE:
            settings = self.circleVolumeVisualizerView.read_view_values()
            specific = {
                "radius": settings.radius,
                "flow": settings.flow.value,
            }
        elif selected == VisualizerOptions.VOLUME_LINE:
            settings = self.lineVolumeVisualizerView.read_view_values()
            specific = {
                "max_height": settings.max_height,
                "line_thickness": settings.line_thickness,
                "flow": settings.flow.value,
                "smoothness": settings.smoothness,
            }
        elif selected == VisualizerOptions.VOLUME_FORCE_LINE:
            settings = self.forceLineVolumeVisualizerView.read_view_values()
            specific = {
                "line_thickness": settings.line_thickness,
                "points_count": settings.points_count,
                "tension": settings.tension,
                "damping": settings.damping,
                "impulse_strength": settings.impulse_strength,
                "gravity": settings.gravity,
                "flow": settings.flow.value,
            }
        elif selected == VisualizerOptions.CHROMA_RECTANGLE:
            settings = self.rectangleChromaVisualizerView.read_view_values()
            specific = {
                "box_height": settings.box_height,
                "corner_radius": settings.corner_radius,
                "color_mode": settings.color_mode,
                "gradient_start": list(settings.gradient_start),
                "gradient_end": list(settings.gradient_end),
                "band_colors": [list(color) for color in settings.band_colors],
            }
        elif selected == VisualizerOptions.CHROMA_CIRCLE:
            settings = self.circleChromaVisualizerView.read_view_values()
            specific = {
                "color_mode": settings.color_mode,
                "gradient_start": list(settings.gradient_start),
                "gradient_end": list(settings.gradient_end),
                "band_colors": [list(color) for color in settings.band_colors],
            }
        elif selected == VisualizerOptions.CHROMA_LINE:
            settings = self.lineChromaVisualizerView.read_view_values()
            specific = {
                "max_height": settings.max_height,
                "line_thickness": settings.line_thickness,
                "smoothness": settings.smoothness,
                "color_mode": settings.color_mode,
                "gradient_start": list(settings.gradient_start) if settings.gradient_start else None,
                "gradient_end": list(settings.gradient_end) if settings.gradient_end else None,
                "band_colors": [list(color) for color in settings.band_colors],
            }
        elif selected == VisualizerOptions.CHROMA_LINES:
            settings = self.lineChromaBandsVisualizerView.read_view_values()
            specific = {
                "max_height": settings.max_height,
                "line_thickness": settings.line_thickness,
                "smoothness": settings.smoothness,
                "flow": settings.flow.value,
                "band_colors": [list(color) for color in settings.band_colors],
                "band_spacing": settings.band_spacing,
            }
        elif selected == VisualizerOptions.CHROMA_FORCE_RECTANGLE:
            settings = self.forceRectangleChromaVisualizerView.read_view_values()
            specific = {
                "box_height": settings.box_height,
                "corner_radius": settings.corner_radius,
                "color_mode": settings.color_mode,
                "gradient_start": list(settings.gradient_start),
                "gradient_end": list(settings.gradient_end),
                "band_colors": [list(color) for color in settings.band_colors],
                "gravity": settings.gravity,
                "force_strength": settings.force_strength,
            }
        elif selected == VisualizerOptions.CHROMA_FORCE_CIRCLE:
            settings = self.forceCircleChromaVisualizerView.read_view_values()
            specific = {
                "color_mode": settings.color_mode,
                "gradient_start": list(settings.gradient_start),
                "gradient_end": list(settings.gradient_end),
                "band_colors": [list(color) for color in settings.band_colors],
                "gravity": settings.gravity,
                "force_strength": settings.force_strength,
            }
        elif selected == VisualizerOptions.CHROMA_FORCE_LINE:
            settings = self.forceLineChromaVisualizerView.read_view_values()
            specific = {
                "line_thickness": settings.line_thickness,
                "points_count": settings.points_count,
                "smoothness": settings.smoothness,
                "tension": settings.tension,
                "damping": settings.damping,
                "force_strength": settings.force_strength,
                "gravity": settings.gravity,
            }
        elif selected == VisualizerOptions.CHROMA_FORCE_LINES:
            settings = self.forceLinesChromaVisualizerView.read_view_values()
            specific = {
                "line_thickness": settings.line_thickness,
                "points_count": settings.points_count,
                "smoothness": settings.smoothness,
                "band_spacing": settings.band_spacing,
                "tension": settings.tension,
                "damping": settings.damping,
                "force_strength": settings.force_strength,
                "gravity": settings.gravity,
                "band_colors": [list(color) for color in settings.band_colors],
            }
        elif selected == VisualizerOptions.WAVEFORM:
            settings = self.waveformVisualizerView.read_view_values()
            specific = {
                "line_thickness": settings.line_thickness,
            }
        elif selected == VisualizerOptions.COMBINED_RECTANGLE:
            settings = self.combinedVisualizerView.read_view_values()
            specific = {
                "box_height": settings.box_height,
                "box_width": settings.box_width,
                "corner_radius": settings.corner_radius,
                "flow": settings.flow.value,
                "chroma_box_height": settings.chroma_box_height,
                "chroma_corner_radius": settings.chroma_corner_radius,
            }

        return {
            "general": {
                "audio_file_path": general.audio_file_path,
                "video_file_path": general.video_file_path,
                "fps": general.fps,
                "video_width": general.video_width,
                "video_height": general.video_height,
                "codec": general.codec,
                "bitrate": general.bitrate,
                "crf": general.crf,
                "hardware_accel": general.hardware_accel,
                "include_audio": general.include_audio,
            },
            "visualizer": {
                "visualizer_type": visualizer.visualizer_type.value,
                "alignment": visualizer.alignment.value,
                "x": visualizer.x,
                "y": visualizer.y,
                "bg_color": list(visualizer.bg_color),
                "border_color": list(visualizer.border_color),
                "border_width": visualizer.border_width,
                "spacing": visualizer.spacing,
                "super_sampling": visualizer.super_sampling,
            },
            "specific": specific,
            "ui": {
                "preview": self.preview_checkbox.isChecked(),
                "show_output": self.show_output_checkbox.isChecked(),
                "preview_panel_visible": self.preview_panel_toggle.isChecked(),
            },
        }

    # ------------------------------------------------------------------
    # Settings application (BaseTab contract)
    # ------------------------------------------------------------------

    def apply_settings(self, data: dict[str, Any]) -> None:
        general = data.get("general", {})
        visualizer = data.get("visualizer", {})
        specific = data.get("specific", {})
        ui_state = data.get("ui", {})

        if general:
            self.generalSettingsView.audio_file_path.setText(general.get("audio_file_path", self.generalSettingsView.audio_file_path.text()))
            self.generalSettingsView.video_file_path.setText(general.get("video_file_path", self.generalSettingsView.video_file_path.text()))
            if "fps" in general:
                self.generalSettingsView.visualizer_fps.setText(str(general["fps"]))
            if "video_width" in general:
                self.generalSettingsView.video_width.setText(str(general["video_width"]))
            if "video_height" in general:
                self.generalSettingsView.video_height.setText(str(general["video_height"]))
            if "codec" in general and general["codec"]:
                self.generalSettingsView.codec.setCurrentText(general["codec"])
            if "bitrate" in general and general["bitrate"] is not None:
                self.generalSettingsView.bitrate.setText(str(general["bitrate"]))
            else:
                self.generalSettingsView.bitrate.setText("")
            if "crf" in general and general["crf"] is not None:
                self.generalSettingsView.crf.setText(str(general["crf"]))
            else:
                self.generalSettingsView.crf.setText("")
            if "hardware_accel" in general:
                self.generalSettingsView.hardware_accel.setChecked(bool(general["hardware_accel"]))
            if "include_audio" in general:
                self.generalSettingsView.include_audio.setChecked(bool(general["include_audio"]))

        if visualizer:
            if "visualizer_type" in visualizer:
                self.generalVisualizerView.visualizer.setCurrentText(visualizer["visualizer_type"])
                self.visualizer_selection_changed(visualizer["visualizer_type"])
            if "alignment" in visualizer:
                self.generalVisualizerView.visualizer_alignment.setCurrentText(visualizer["alignment"])
            if "x" in visualizer:
                self.generalVisualizerView.visualizer_x.setText(str(visualizer["x"]))
            if "y" in visualizer:
                self.generalVisualizerView.visualizer_y.setText(str(visualizer["y"]))
            if "bg_color" in visualizer:
                bg = visualizer["bg_color"]
                self.generalVisualizerView.visualizer_bg_color_field.setText(f"{bg[0]}, {bg[1]}, {bg[2]}")
            if "border_color" in visualizer:
                bc = visualizer["border_color"]
                self.generalVisualizerView.visualizer_border_color_field.setText(f"{bc[0]}, {bc[1]}, {bc[2]}")
            if "border_width" in visualizer:
                self.generalVisualizerView.visualizer_border_width.setText(str(visualizer["border_width"]))
            if "spacing" in visualizer:
                self.generalVisualizerView.visualizer_spacing.setText(str(visualizer["spacing"]))
            if "super_sampling" in visualizer:
                self.generalVisualizerView.super_sampling.setText(str(visualizer["super_sampling"]))

        current_type = self.generalVisualizerView.visualizer.currentText()
        if current_type == VisualizerOptions.VOLUME_RECTANGLE.value:
            if "box_height" in specific:
                self.rectangleVolumeVisualizerView.box_height.setText(str(specific["box_height"]))
            if "box_width" in specific:
                self.rectangleVolumeVisualizerView.box_width.setText(str(specific["box_width"]))
            if "corner_radius" in specific:
                self.rectangleVolumeVisualizerView.corner_radius.setText(str(specific["corner_radius"]))
            if "flow" in specific:
                self.rectangleVolumeVisualizerView.visualizer_flow.setCurrentText(specific["flow"])
        elif current_type == VisualizerOptions.VOLUME_CIRCLE.value:
            if "radius" in specific:
                self.circleVolumeVisualizerView.radius.setText(str(specific["radius"]))
            if "flow" in specific:
                self.circleVolumeVisualizerView.visualizer_flow.setCurrentText(specific["flow"])
        elif current_type == VisualizerOptions.VOLUME_LINE.value:
            if "max_height" in specific:
                self.lineVolumeVisualizerView.max_height.setText(str(specific["max_height"]))
            if "line_thickness" in specific:
                self.lineVolumeVisualizerView.line_thickness.setText(str(specific["line_thickness"]))
            if "flow" in specific:
                self.lineVolumeVisualizerView.visualizer_flow.setCurrentText(specific["flow"])
            if "smoothness" in specific:
                self.lineVolumeVisualizerView.smoothness.setText(str(specific["smoothness"]))
        elif current_type == VisualizerOptions.VOLUME_FORCE_LINE.value:
            if "line_thickness" in specific:
                self.forceLineVolumeVisualizerView.line_thickness.setText(str(specific["line_thickness"]))
            if "points_count" in specific:
                self.forceLineVolumeVisualizerView.points_count.setText(str(specific["points_count"]))
            if "tension" in specific:
                self.forceLineVolumeVisualizerView.tension.setText(str(specific["tension"]))
            if "damping" in specific:
                self.forceLineVolumeVisualizerView.damping.setText(str(specific["damping"]))
            if "impulse_strength" in specific:
                self.forceLineVolumeVisualizerView.impulse_strength.setText(str(specific["impulse_strength"]))
            if "gravity" in specific:
                self.forceLineVolumeVisualizerView.gravity.setText(str(specific["gravity"]))
            if "flow" in specific:
                self.forceLineVolumeVisualizerView.visualizer_flow.setCurrentText(specific["flow"])
        elif current_type == VisualizerOptions.CHROMA_RECTANGLE.value:
            if "box_height" in specific:
                self.rectangleChromaVisualizerView.box_height.setText(str(specific["box_height"]))
            if "corner_radius" in specific:
                self.rectangleChromaVisualizerView.corner_radius.setText(str(specific["corner_radius"]))
            if "color_mode" in specific:
                self.rectangleChromaVisualizerView.color_mode.setCurrentText(specific["color_mode"])
            if "gradient_start" in specific:
                gs = specific["gradient_start"]
                self.rectangleChromaVisualizerView.gradient_start.setText(f"{gs[0]}, {gs[1]}, {gs[2]}")
            if "gradient_end" in specific:
                ge = specific["gradient_end"]
                self.rectangleChromaVisualizerView.gradient_end.setText(f"{ge[0]}, {ge[1]}, {ge[2]}")
            if "band_colors" in specific:
                colors = ["{0}, {1}, {2}".format(*color) for color in specific["band_colors"]]
                self.rectangleChromaVisualizerView.band_colors.setText("|".join(colors))
        elif current_type == VisualizerOptions.CHROMA_CIRCLE.value:
            if "color_mode" in specific:
                self.circleChromaVisualizerView.color_mode.setCurrentText(specific["color_mode"])
            if "gradient_start" in specific:
                gs = specific["gradient_start"]
                self.circleChromaVisualizerView.gradient_start.setText(f"{gs[0]}, {gs[1]}, {gs[2]}")
            if "gradient_end" in specific:
                ge = specific["gradient_end"]
                self.circleChromaVisualizerView.gradient_end.setText(f"{ge[0]}, {ge[1]}, {ge[2]}")
            if "band_colors" in specific:
                colors = ["{0}, {1}, {2}".format(*color) for color in specific["band_colors"]]
                self.circleChromaVisualizerView.band_colors.setText("|".join(colors))
        elif current_type == VisualizerOptions.CHROMA_LINE.value:
            if "max_height" in specific:
                self.lineChromaVisualizerView.max_height.setText(str(specific["max_height"]))
            if "line_thickness" in specific:
                self.lineChromaVisualizerView.line_thickness.setText(str(specific["line_thickness"]))
            if "smoothness" in specific:
                self.lineChromaVisualizerView.smoothness.setText(str(specific["smoothness"]))
            if "color_mode" in specific:
                self.lineChromaVisualizerView.color_mode.setCurrentText(specific["color_mode"])
            if "gradient_start" in specific and specific["gradient_start"]:
                gs = specific["gradient_start"]
                self.lineChromaVisualizerView.gradient_start.setText(f"{gs[0]}, {gs[1]}, {gs[2]}")
            if "gradient_end" in specific and specific["gradient_end"]:
                ge = specific["gradient_end"]
                self.lineChromaVisualizerView.gradient_end.setText(f"{ge[0]}, {ge[1]}, {ge[2]}")
            if "band_colors" in specific and specific["band_colors"]:
                colors = ["{0}, {1}, {2}".format(*color) for color in specific["band_colors"]]
                self.lineChromaVisualizerView.band_colors.setText("|".join(colors))
        elif current_type == VisualizerOptions.CHROMA_LINES.value:
            if "max_height" in specific:
                self.lineChromaBandsVisualizerView.max_height.setText(str(specific["max_height"]))
            if "line_thickness" in specific:
                self.lineChromaBandsVisualizerView.line_thickness.setText(str(specific["line_thickness"]))
            if "smoothness" in specific:
                self.lineChromaBandsVisualizerView.smoothness.setText(str(specific["smoothness"]))
            if "flow" in specific:
                self.lineChromaBandsVisualizerView.visualizer_flow.setCurrentText(specific["flow"])
            if "band_colors" in specific and specific["band_colors"]:
                colors = ["{0}, {1}, {2}".format(*color) for color in specific["band_colors"]]
                for field, color in zip(self.lineChromaBandsVisualizerView.band_color_fields, colors):
                    field.setText(color)
            if "band_spacing" in specific:
                self.lineChromaBandsVisualizerView.band_spacing.setText(str(specific["band_spacing"]))
        elif current_type == VisualizerOptions.CHROMA_FORCE_RECTANGLE.value:
            if "box_height" in specific:
                self.forceRectangleChromaVisualizerView.box_height.setText(str(specific["box_height"]))
            if "corner_radius" in specific:
                self.forceRectangleChromaVisualizerView.corner_radius.setText(str(specific["corner_radius"]))
            if "color_mode" in specific:
                self.forceRectangleChromaVisualizerView.color_mode.setCurrentText(specific["color_mode"])
            if "gradient_start" in specific and specific["gradient_start"]:
                gs = specific["gradient_start"]
                self.forceRectangleChromaVisualizerView.gradient_start.setText(f"{gs[0]}, {gs[1]}, {gs[2]}")
            if "gradient_end" in specific and specific["gradient_end"]:
                ge = specific["gradient_end"]
                self.forceRectangleChromaVisualizerView.gradient_end.setText(f"{ge[0]}, {ge[1]}, {ge[2]}")
            if "band_colors" in specific and specific["band_colors"]:
                colors = ["{0}, {1}, {2}".format(*color) for color in specific["band_colors"]]
                self.forceRectangleChromaVisualizerView.band_colors.setText("|".join(colors))
            if "gravity" in specific:
                self.forceRectangleChromaVisualizerView.gravity.setText(str(specific["gravity"]))
            if "force_strength" in specific:
                self.forceRectangleChromaVisualizerView.force_strength.setText(str(specific["force_strength"]))
        elif current_type == VisualizerOptions.CHROMA_FORCE_CIRCLE.value:
            if "color_mode" in specific:
                self.forceCircleChromaVisualizerView.color_mode.setCurrentText(specific["color_mode"])
            if "gradient_start" in specific and specific["gradient_start"]:
                gs = specific["gradient_start"]
                self.forceCircleChromaVisualizerView.gradient_start.setText(f"{gs[0]}, {gs[1]}, {gs[2]}")
            if "gradient_end" in specific and specific["gradient_end"]:
                ge = specific["gradient_end"]
                self.forceCircleChromaVisualizerView.gradient_end.setText(f"{ge[0]}, {ge[1]}, {ge[2]}")
            if "band_colors" in specific and specific["band_colors"]:
                colors = ["{0}, {1}, {2}".format(*color) for color in specific["band_colors"]]
                self.forceCircleChromaVisualizerView.band_colors.setText("|".join(colors))
            if "gravity" in specific:
                self.forceCircleChromaVisualizerView.gravity.setText(str(specific["gravity"]))
            if "force_strength" in specific:
                self.forceCircleChromaVisualizerView.force_strength.setText(str(specific["force_strength"]))
        elif current_type == VisualizerOptions.CHROMA_FORCE_LINE.value:
            if "line_thickness" in specific:
                self.forceLineChromaVisualizerView.line_thickness.setText(str(specific["line_thickness"]))
            if "points_count" in specific:
                self.forceLineChromaVisualizerView.points_count.setText(str(specific["points_count"]))
            if "smoothness" in specific:
                self.forceLineChromaVisualizerView.smoothness.setText(str(specific["smoothness"]))
            if "tension" in specific:
                self.forceLineChromaVisualizerView.tension.setText(str(specific["tension"]))
            if "damping" in specific:
                self.forceLineChromaVisualizerView.damping.setText(str(specific["damping"]))
            if "force_strength" in specific:
                self.forceLineChromaVisualizerView.force_strength.setText(str(specific["force_strength"]))
            if "gravity" in specific:
                self.forceLineChromaVisualizerView.gravity.setText(str(specific["gravity"]))
        elif current_type == VisualizerOptions.CHROMA_FORCE_LINES.value:
            if "line_thickness" in specific:
                self.forceLinesChromaVisualizerView.line_thickness.setText(str(specific["line_thickness"]))
            if "points_count" in specific:
                self.forceLinesChromaVisualizerView.points_count.setText(str(specific["points_count"]))
            if "smoothness" in specific:
                self.forceLinesChromaVisualizerView.smoothness.setText(str(specific["smoothness"]))
            if "band_spacing" in specific:
                self.forceLinesChromaVisualizerView.band_spacing.setText(str(specific["band_spacing"]))
            if "tension" in specific:
                self.forceLinesChromaVisualizerView.tension.setText(str(specific["tension"]))
            if "damping" in specific:
                self.forceLinesChromaVisualizerView.damping.setText(str(specific["damping"]))
            if "force_strength" in specific:
                self.forceLinesChromaVisualizerView.force_strength.setText(str(specific["force_strength"]))
            if "gravity" in specific:
                self.forceLinesChromaVisualizerView.gravity.setText(str(specific["gravity"]))
            if "band_colors" in specific and specific["band_colors"]:
                colors = ["{0}, {1}, {2}".format(*color) for color in specific["band_colors"]]
                for field, color in zip(self.forceLinesChromaVisualizerView.band_color_fields, colors):
                    field.setText(color)
        elif current_type == VisualizerOptions.WAVEFORM.value:
            if "line_thickness" in specific:
                self.waveformVisualizerView.line_thickness.setText(str(specific["line_thickness"]))
        elif current_type == VisualizerOptions.COMBINED_RECTANGLE.value:
            if "box_height" in specific:
                self.combinedVisualizerView.box_height.setText(str(specific["box_height"]))
            if "box_width" in specific:
                self.combinedVisualizerView.box_width.setText(str(specific["box_width"]))
            if "corner_radius" in specific:
                self.combinedVisualizerView.corner_radius.setText(str(specific["corner_radius"]))
            if "flow" in specific:
                self.combinedVisualizerView.visualizer_flow.setCurrentText(specific["flow"])
            if "chroma_box_height" in specific:
                self.combinedVisualizerView.chroma_box_height.setText(str(specific["chroma_box_height"]))
            if "chroma_corner_radius" in specific:
                self.combinedVisualizerView.chroma_corner_radius.setText(str(specific["chroma_corner_radius"]))

        if "preview" in ui_state:
            self.preview_checkbox.setChecked(bool(ui_state["preview"]))
        if "show_output" in ui_state:
            self.show_output_checkbox.setChecked(bool(ui_state["show_output"]))
        if "preview_panel_visible" in ui_state:
            self.preview_panel_toggle.setChecked(bool(ui_state["preview_panel_visible"]))
            self._toggle_preview_panel(None)

    # ------------------------------------------------------------------
    # Global busy state
    # ------------------------------------------------------------------

    def set_global_busy(self, is_busy: bool, owner_tab_id: str | None = None) -> None:
        if is_busy and owner_tab_id != self.tab_id:
            self.render_button.setEnabled(False)
        elif not is_busy:
            self.render_button.setEnabled(True)

    # ------------------------------------------------------------------
    # Render controls
    # ------------------------------------------------------------------

    def _preview_output_path(self) -> str:
        return str(get_data_dir() / "preview_output.mp4")

    def _reset_render_controls(self) -> None:
        self.rendering = False
        self._set_controls_enabled(True)
        self.render_button.setText("Render Video")
        self.cancel_button.hide()
        self.cancel_button.setEnabled(True)
        self._active_preview = False

    def _start_render(self, preview_seconds: int | None = None,
                      output_path: str | None = None,
                      force_show_output: bool | None = None,
                      show_validation_errors: bool = True) -> None:
        if self.rendering:
            return

        is_live_preview = preview_seconds is not None and output_path == self._preview_output_path()

        # Acquire shared job slot for non-preview renders
        if not is_live_preview:
            if not self._main_window.try_start_job(self.tab_id):
                return

        self.rendering = True
        self._active_preview = is_live_preview
        if self._active_preview:
            self._reset_preview_player()
        self._set_controls_enabled(False)
        if self._active_preview:
            self.render_button.setText("Previewing...")
        else:
            self.render_button.setText("Rendering...")

        self.cancel_button.show()
        self.cancel_button.setEnabled(True)

        valid, validation_error = self.validate_render_settings()
        if not valid:
            self._reset_render_controls()
            if not is_live_preview:
                self._main_window.finish_job(self.tab_id)
            if show_validation_errors:
                message = QMessageBox(QMessageBox.Icon.Critical, "Settings Error",
                                      f"The render cannot run. {validation_error}")
                message.exec()
            return

        general_settings = self.generalSettingsView.read_view_values()
        visualizer_settings = self.generalVisualizerView.read_view_values()

        audio_data = AudioData(general_settings.audio_file_path)
        file_path = output_path or general_settings.video_file_path
        # Ensure .mp4 extension on user-typed paths
        if file_path and not Path(file_path).suffix:
            file_path = file_path + ".mp4"
        video_data = VideoData(
            general_settings.video_width,
            general_settings.video_height,
            general_settings.fps,
            file_path=file_path,
            codec=general_settings.codec,
            bitrate=general_settings.bitrate,
            crf=general_settings.crf,
            hardware_accel=general_settings.hardware_accel,
        )

        visualizer = self._create_visualizer(audio_data, video_data, visualizer_settings)

        if force_show_output is None:
            self._show_output_for_last_render = self.show_output_checkbox.isChecked()
        else:
            self._show_output_for_last_render = force_show_output

        if not is_live_preview:
            self._main_window.show_job_status(
                "render", self.tab_id,
                f"Rendering {'preview' if preview_seconds else 'video'}...",
            )

        from audio_visualizer.ui.mainWindow import RenderWorker
        render_worker = RenderWorker(
            audio_data,
            video_data,
            visualizer,
            preview_seconds,
            include_audio=general_settings.include_audio,
        )
        self._active_render_worker = render_worker
        self._render_includes_audio = general_settings.include_audio
        render_worker.signals.finished.connect(self.render_finished)
        render_worker.signals.error.connect(self.render_failed)
        render_worker.signals.status.connect(self.render_status_update)
        render_worker.signals.progress.connect(self.render_progress_update)
        render_worker.signals.mux_progress.connect(self._render_mux_progress_update)
        render_worker.signals.canceled.connect(self.render_canceled)
        self._main_window.render_thread_pool.start(render_worker)

    def render_video(self) -> None:
        preview_seconds = 30 if self.preview_checkbox.isChecked() else None
        self._start_render(preview_seconds=preview_seconds)

    def render_preview(self) -> None:
        self._start_render(preview_seconds=5, output_path=self._preview_output_path(), force_show_output=True)

    def render_finished(self, video_data: VideoData) -> None:
        if self._active_preview:
            self._show_preview_in_panel(video_data)
        elif self._show_output_for_last_render:
            # Register the output as a session asset
            self._register_render_asset(video_data)
            self._main_window.show_job_completed(
                "Render complete.",
                output_path=video_data.file_path,
                owner_tab_id=self.tab_id,
            )
        else:
            self._register_render_asset(video_data)
            self._main_window.finish_job(self.tab_id)

        self._active_render_worker = None
        self._reset_render_controls()
        if self._pending_preview_refresh:
            self._trigger_live_preview_update()

    def render_failed(self, msg: str) -> None:
        if self._active_preview:
            self._reset_preview_player()
            self._active_render_worker = None
            self._reset_render_controls()
        else:
            self._active_render_worker = None
            self._reset_preview_player()
            self._reset_render_controls()
            self._main_window.show_job_failed(
                f"Render error: {msg}",
                owner_tab_id=self.tab_id,
            )

    def render_status_update(self, msg: str) -> None:
        if not self._active_preview:
            self._main_window.update_job_status(msg)

    def render_progress_update(self, current_frame: int, total_frames: int, elapsed_seconds: float) -> None:
        if current_frame > 0 and total_frames > 0:
            eta_seconds = (elapsed_seconds / current_frame) * (total_frames - current_frame)
            eta = self._format_duration(eta_seconds)
            if not self._active_preview:
                # Stage-aware: encoding is 90% of total when audio mux
                # will follow, otherwise 100%.
                encode_weight = 0.9 if self._render_includes_audio else 1.0
                encode_percent = (current_frame / total_frames) * encode_weight * 100
                self._main_window.update_job_progress(
                    encode_percent,
                    f"Encoding {current_frame}/{total_frames} frames, ETA {eta}",
                )

    def _render_mux_progress_update(self, fraction: float) -> None:
        """Handle audio-mux progress (0.0-1.0) mapped to the final 10%."""
        if not self._active_preview:
            percent = 90.0 + fraction * 10.0
            self._main_window.update_job_progress(
                percent,
                f"Muxing audio... {percent:.0f}%",
            )

    def render_canceled(self) -> None:
        was_preview = self._active_preview
        self._active_render_worker = None
        self._reset_render_controls()
        if not was_preview:
            self._main_window.show_job_canceled(
                "Render canceled.",
                owner_tab_id=self.tab_id,
            )

    def cancel_render(self) -> None:
        if self._active_render_worker is None:
            return
        self.cancel_button.setEnabled(False)
        if not self._active_preview:
            self._main_window.update_job_status("Canceling render...")
        self._active_render_worker.cancel()

    def cancel_job(self) -> None:
        """Cancel the active render (called by the main-window shell)."""
        self.cancel_render()

    # ------------------------------------------------------------------
    # Asset registration
    # ------------------------------------------------------------------

    def _register_render_asset(self, video_data: VideoData) -> None:
        """Register the rendered video as a session asset."""
        general_settings = self.generalSettingsView.read_view_values()
        visualizer_settings = self.generalVisualizerView.read_view_values()

        from audio_visualizer.ui.sessionContext import SessionAsset
        asset = SessionAsset(
            id=str(uuid.uuid4()),
            display_name=Path(video_data.file_path).name,
            path=Path(video_data.file_path),
            category="video",
            source_tab="audio_visualizer",
            role="visualizer_output",
            width=video_data.video_width,
            height=video_data.video_height,
            fps=float(video_data.fps),
            has_audio=general_settings.include_audio,
            metadata={
                "include_audio_in_output": general_settings.include_audio,
                "resolution": f"{video_data.video_width}x{video_data.video_height}",
                "codec": general_settings.codec,
                "visualizer_type": visualizer_settings.visualizer_type.value,
            },
        )
        self.register_output_asset(asset)

    # ------------------------------------------------------------------
    # Control-enable helpers
    # ------------------------------------------------------------------

    def _set_controls_enabled(self, enabled: bool) -> None:
        for widget_type in (QLineEdit, QComboBox, QCheckBox, QPushButton):
            for widget in self.findChildren(widget_type):
                if widget is self.cancel_button:
                    continue
                widget.setEnabled(enabled)
        if enabled:
            self.cancel_button.setEnabled(False)

    @staticmethod
    def _format_duration(seconds: float) -> str:
        if seconds < 0:
            seconds = 0
        total = int(seconds)
        minutes, secs = divmod(total, 60)
        return f"{minutes:02d}:{secs:02d}"

    # ------------------------------------------------------------------
    # Live preview
    # ------------------------------------------------------------------

    def _connect_live_preview_updates(self) -> None:
        for field in self.findChildren(QLineEdit):
            field.textChanged.connect(self._schedule_live_preview_update)
        for combo in self.findChildren(QComboBox):
            combo.currentTextChanged.connect(self._schedule_live_preview_update)
        for checkbox in self.findChildren(QCheckBox):
            checkbox.stateChanged.connect(self._schedule_live_preview_update)

    def _schedule_live_preview_update(self) -> None:
        if not self.preview_panel_toggle.isChecked():
            return
        self._pending_preview_refresh = True
        self._preview_update_timer.start()

    def _trigger_live_preview_update(self) -> None:
        if not self.preview_panel_toggle.isChecked():
            self._pending_preview_refresh = False
            return
        if self.rendering:
            return
        valid, _ = self.validate_render_settings()
        if not valid:
            self._pending_preview_refresh = False
            return
        self._pending_preview_refresh = False
        self._start_render(
            preview_seconds=5,
            output_path=self._preview_output_path(),
            force_show_output=True,
            show_validation_errors=False,
        )

    def _toggle_preview_panel(self, _checked: int | None) -> None:
        visible = self.preview_panel_toggle.isChecked()
        self.preview_panel_body.setVisible(visible)
        if not visible:
            self._reset_preview_player()

    def _preview_volume_changed(self, value: int) -> None:
        if self._preview_audio_output is not None:
            self._preview_audio_output.setVolume(value / 100)

    def _reset_preview_player(self) -> None:
        if self._preview_player is None:
            return
        try:
            self._preview_player.stop()
        except Exception:
            pass
        try:
            self._preview_player.setSource(QUrl())
        except Exception:
            pass

    def _show_preview_in_panel(self, video_data: VideoData) -> None:
        if not self.preview_panel_toggle.isChecked():
            return
        try:
            self.preview_video_widget.setMaximumSize(QSize(video_data.video_width, video_data.video_height))
        except Exception:
            pass
        self._preview_player.setSource(QUrl.fromLocalFile(video_data.file_path))
        self._preview_player.play()
