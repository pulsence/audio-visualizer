'''
MIT License

Copyright (c) 2025 Timothy Eck

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''
from PySide6.QtCore import (
    Qt, QRunnable, QThreadPool, QObject, Signal, QTimer, QSize, QUrl
)

from PySide6.QtWidgets import (
    QMainWindow, QMessageBox, QGridLayout, QFormLayout, QHBoxLayout,
    QWidget, QComboBox, QLabel, QLineEdit, QPushButton, QCheckBox,
    QFileDialog, QColorDialog, QProgressBar, QVBoxLayout, QGroupBox, QSlider,
    QSizePolicy
)

from PySide6.QtGui import (
    QDesktopServices, QAction, QIntValidator, QFont
)

from PySide6.QtMultimediaWidgets import (
    QVideoWidget
)

from PySide6.QtMultimedia import (
    QMediaPlayer, QAudioOutput
)

from audio_visualizer.visualizers import Visualizer

from audio_visualizer.visualizers.utilities import AudioData, VideoData, VisualizerOptions

from audio_visualizer.ui.views import Fonts
from audio_visualizer.ui.views.general.generalSettingViews import GeneralSettingsView, GeneralSettings
from audio_visualizer.ui.views.general.generalVisualizerView import GeneralVisualizerView, GeneralVisualizerSettings
import json
import logging
import time
from fractions import Fraction
from pathlib import Path

from audio_visualizer.app_logging import setup_logging
from audio_visualizer.app_paths import get_config_dir, get_data_dir
from audio_visualizer import updater

class MainWindow(QMainWindow):
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

    def __init__(self):
        super().__init__()
        self._log_path = setup_logging()
        self._logger = logging.getLogger(__name__)
        self.setWindowTitle("Audio Visualizer")
        self.setGeometry(100, 100, 800, 500)
        self._visualizer_views = {}
        self._visualizer_view_layout = None

        primary_layout = QGridLayout()

        self.heading_label = QLabel("Welcome to the Audio Visualizer!")
        self.heading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.heading_label.setFont(Fonts.h1_font)
        primary_layout.addWidget(self.heading_label, 0, 0, 1, 2)

        # 1,0
        self._prepare_general_settings_elements(primary_layout)
        # 1,1
        self._prepare_general_visualizer_elements(primary_layout)
        # 2,1
        self._prepare_specific_visualizer_elements(primary_layout)
        # 2,0
        self._prepare_preview_panel_elements(primary_layout)
        # 3,0
        self._prepare_render_elements(primary_layout)


        container = QWidget()
        container.setLayout(primary_layout)
        self.setCentralWidget(container)

        self.render_thread_pool = QThreadPool()
        self.render_thread_pool.setMaxThreadCount(1)
        self.rendering = False
        self._show_output_for_last_render = True
        self._active_preview = False
        self._active_render_worker = None
        self._pending_preview_refresh = False
        self._preview_update_timer = QTimer(self)
        self._preview_update_timer.setSingleShot(True)
        self._preview_update_timer.setInterval(400)
        self._preview_update_timer.timeout.connect(self._trigger_live_preview_update)
        self._background_thread_pool = QThreadPool()

        self._setup_menu()

        self._load_last_settings_if_present()
        self._connect_live_preview_updates()

    '''
    General settings in (1,0)
    '''
    def _prepare_general_settings_elements(self, layout: QGridLayout, r=1, c=0):
        self.generalSettingsView = GeneralSettingsView()
        layout.addLayout(self.generalSettingsView.get_view_in_layout(), r, c,)

    '''
    Settings for general visualization items in (1, 1)
    '''
    def _prepare_general_visualizer_elements(self, layout: QGridLayout, r=1, c=1):
        self.generalVisualizerView = GeneralVisualizerView(self)
        layout.addLayout(self.generalVisualizerView.get_view_in_layout(), r, c)

    '''
    Settings for specific visualizes in (2, 1)
    '''
    def _prepare_specific_visualizer_elements(self, layout: QGridLayout, r=2, c=1): 
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

    def __getattr__(self, name):
        if name in self._VIEW_ATTRIBUTE_MAP:
            view = self._get_visualizer_view(self._VIEW_ATTRIBUTE_MAP[name])
            setattr(self, name, view)
            return view
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def _build_visualizer_view(self, visualizer: VisualizerOptions):
        if visualizer == VisualizerOptions.VOLUME_RECTANGLE:
            from audio_visualizer.ui.views.volume.rectangleVolumeVisualizerView import RectangleVolumeVisualizerView
            return RectangleVolumeVisualizerView()
        if visualizer == VisualizerOptions.VOLUME_CIRCLE:
            from audio_visualizer.ui.views.volume.circleVolumeVisualizerView import CircleVolumeVisualizerView
            return CircleVolumeVisualizerView()
        if visualizer == VisualizerOptions.VOLUME_LINE:
            from audio_visualizer.ui.views.volume.lineVolumeVisualizerView import LineVolumeVisualizerView
            return LineVolumeVisualizerView()
        if visualizer == VisualizerOptions.VOLUME_FORCE_LINE:
            from audio_visualizer.ui.views.volume.forceLineVolumeVisualizerView import ForceLineVolumeVisualizerView
            return ForceLineVolumeVisualizerView()
        if visualizer == VisualizerOptions.CHROMA_RECTANGLE:
            from audio_visualizer.ui.views.chroma.rectangleChromaVisualizerView import RectangleChromaVisualizerView
            return RectangleChromaVisualizerView()
        if visualizer == VisualizerOptions.CHROMA_CIRCLE:
            from audio_visualizer.ui.views.chroma.circleChromaVisualizerView import CircleChromeVisualizerView
            return CircleChromeVisualizerView()
        if visualizer == VisualizerOptions.CHROMA_LINE:
            from audio_visualizer.ui.views.chroma.lineChromaVisualizerView import LineChromaVisualizerView
            return LineChromaVisualizerView()
        if visualizer == VisualizerOptions.CHROMA_LINES:
            from audio_visualizer.ui.views.chroma.lineChromaBandsVisualizerView import LineChromaBandsVisualizerView
            return LineChromaBandsVisualizerView()
        if visualizer == VisualizerOptions.CHROMA_FORCE_RECTANGLE:
            from audio_visualizer.ui.views.chroma.forceRectangleChromaVisualizerView import ForceRectangleChromaVisualizerView
            return ForceRectangleChromaVisualizerView()
        if visualizer == VisualizerOptions.CHROMA_FORCE_CIRCLE:
            from audio_visualizer.ui.views.chroma.forceCircleChromaVisualizerView import ForceCircleChromaVisualizerView
            return ForceCircleChromaVisualizerView()
        if visualizer == VisualizerOptions.CHROMA_FORCE_LINE:
            from audio_visualizer.ui.views.chroma.forceLineChromaVisualizerView import ForceLineChromaVisualizerView
            return ForceLineChromaVisualizerView()
        if visualizer == VisualizerOptions.CHROMA_FORCE_LINES:
            from audio_visualizer.ui.views.chroma.forceLinesChromaVisualizerView import ForceLinesChromaVisualizerView
            return ForceLinesChromaVisualizerView()
        if visualizer == VisualizerOptions.WAVEFORM:
            from audio_visualizer.ui.views.general.waveformVisualizerView import WaveformVisualizerView
            return WaveformVisualizerView()
        if visualizer == VisualizerOptions.COMBINED_RECTANGLE:
            from audio_visualizer.ui.views.general.combinedVisualizerView import CombinedVisualizerView
            return CombinedVisualizerView()
        raise ValueError(f"Unsupported visualizer view: {visualizer}")

    def _get_visualizer_view(self, visualizer: VisualizerOptions):
        view = self._visualizer_views.get(visualizer)
        if view is None:
            view = self._build_visualizer_view(visualizer)
            widget = view.get_view_in_widget()
            widget.hide()
            self._visualizer_view_layout.addWidget(widget, 0, 0)
            self._visualizer_views[visualizer] = view
        return view

    def _show_visualizer_view(self, visualizer: VisualizerOptions):
        for view in self._visualizer_views.values():
            view.get_view_in_widget().hide()
        view = self._get_visualizer_view(visualizer)
        view.get_view_in_widget().show()

    '''
    UI elements to launch a render in (3, 0)
    '''
    def _prepare_preview_panel_elements(self, layout: QGridLayout, r=2, c=0):
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

    def _prepare_render_elements(self, layout: QGridLayout, r=3, c=0):
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

        self.save_project_button = QPushButton("Save Project")
        self.save_project_button.clicked.connect(self.save_project)
        render_section_layout.addWidget(self.save_project_button, 2, 0)

        self.load_project_button = QPushButton("Load Project")
        self.load_project_button.clicked.connect(self.load_project)
        render_section_layout.addWidget(self.load_project_button, 2, 1)

        self.render_progress_bar = QProgressBar()
        self.render_progress_bar.setRange(0, 0)
        self.render_progress_bar.hide()
        render_section_layout.addWidget(self.render_progress_bar, 3, 0, 1, 2)

        self.cancel_button = QPushButton("Cancel Render")
        self.cancel_button.clicked.connect(self.cancel_render)
        self.cancel_button.hide()
        render_section_layout.addWidget(self.cancel_button, 4, 0, 1, 2)

        layout.addLayout(render_section_layout, r, c)

        self.render_status_label = QLabel()
        self.render_status_label.hide()
        layout.addWidget(self.render_status_label, r, c+1)

    def _setup_menu(self):
        menu_bar = self.menuBar()
        menu_bar.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        help_menu = menu_bar.addMenu("Help")
        help_menu.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.check_updates_action = QAction("Check for Updates", self)
        self.check_updates_action.triggered.connect(self.check_for_updates)
        help_menu.addAction(self.check_updates_action)


    def visualizer_selection_changed(self, visualizer):
        if self._visualizer_view_layout is None:
            return
        visualizer = VisualizerOptions(visualizer)
        self._show_visualizer_view(visualizer)

    def validate_render_settings(self):
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

    def _preview_output_path(self) -> str:
        return str(get_data_dir() / "preview_output.mp4")

    def _create_visualizer(self, audio_data: AudioData, video_data: VideoData, visualizer_settings: GeneralVisualizerSettings):
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

    def _reset_render_controls(self):
        self.rendering = False
        self._set_controls_enabled(True)
        self.render_button.setText("Render Video")
        self.render_status_label.hide()
        self.render_progress_bar.hide()
        self.cancel_button.hide()
        self.cancel_button.setEnabled(True)
        self._active_preview = False

    def _start_render(self, preview_seconds=None, output_path=None, force_show_output=None, show_validation_errors=True):
        if self.rendering:
            return
        
        self.rendering = True
        self._active_preview = preview_seconds is not None and output_path == self._preview_output_path()
        if self._active_preview:
            self._reset_preview_player()
        self._set_controls_enabled(False)
        if self._active_preview:
            self.render_button.setText("Previewing...")
        else:
            self.render_button.setText("Rendering...")

        self.render_status_label.show()
        self.render_status_label.setText("Setting up render...")
        self.render_progress_bar.setRange(0, 0)
        self.render_progress_bar.setValue(0)
        self.render_progress_bar.show()
        self.cancel_button.show()
        self.cancel_button.setEnabled(True)

        valid, validation_error = self.validate_render_settings()
        if not valid:
            self._reset_render_controls()

            if show_validation_errors:
                message = QMessageBox(QMessageBox.Icon.Critical, "Settings Error",
                                      f"The render cannot run. {validation_error}")
                message.exec()
            return

        general_settings = self.generalSettingsView.read_view_values()
        visualizer_settings = self.generalVisualizerView.read_view_values()

        audio_data = AudioData(general_settings.audio_file_path)
        file_path = output_path or general_settings.video_file_path
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

        render_worker = RenderWorker(
            audio_data,
            video_data,
            visualizer,
            preview_seconds,
            include_audio=general_settings.include_audio,
        )
        self._active_render_worker = render_worker
        render_worker.signals.finished.connect(self.render_finished)
        render_worker.signals.error.connect(self.render_failed)
        render_worker.signals.status.connect(self.render_status_update)
        render_worker.signals.progress.connect(self.render_progress_update)
        render_worker.signals.canceled.connect(self.render_canceled)
        self.render_thread_pool.start(render_worker)

    def render_video(self):
        preview_seconds = 30 if self.preview_checkbox.isChecked() else None
        self._start_render(preview_seconds=preview_seconds)

    def render_preview(self):
        self._start_render(preview_seconds=5, output_path=self._preview_output_path(), force_show_output=True)
    
    def render_finished(self, video_data: VideoData):
        if self._active_preview:
            self._show_preview_in_panel(video_data)
        elif self._show_output_for_last_render:
            from audio_visualizer.ui.renderDialog import RenderDialog
            player = RenderDialog(video_data)
            player.exec()
        self._active_render_worker = None
        self._reset_render_controls()
        if self._pending_preview_refresh:
            self._trigger_live_preview_update()
    
    def render_failed(self, msg):
        message = QMessageBox(QMessageBox.Icon.Critical, "Error rendering",
                              f"There was an error rendering the video. The error message is: {msg}\n\nLog file: {self._log_path}")
        message.exec()
        self._active_render_worker = None
        self._reset_preview_player()
        self._reset_render_controls()

    def render_status_update(self, msg):
        self.render_status_label.setText(msg)

    def render_progress_update(self, current_frame: int, total_frames: int, elapsed_seconds: float):
        if total_frames > 0:
            if self.render_progress_bar.maximum() != total_frames:
                self.render_progress_bar.setRange(0, total_frames)
            self.render_progress_bar.setValue(current_frame)
        if current_frame > 0 and total_frames > 0:
            eta_seconds = (elapsed_seconds / current_frame) * (total_frames - current_frame)
            eta = self._format_duration(eta_seconds)
            self.render_status_label.setText(
                f"Rendering video ({current_frame}/{total_frames} frames, ETA {eta})"
            )

    def render_canceled(self):
        self._active_render_worker = None
        self.render_status_label.setText("Render canceled.")
        self._reset_render_controls()

    def cancel_render(self):
        if self._active_render_worker is None:
            return
        self.render_status_label.setText("Canceling render...")
        self.cancel_button.setEnabled(False)
        self._active_render_worker.cancel()

    def _set_controls_enabled(self, enabled: bool):
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

    def _connect_live_preview_updates(self):
        for field in self.findChildren(QLineEdit):
            field.textChanged.connect(self._schedule_live_preview_update)
        for combo in self.findChildren(QComboBox):
            combo.currentTextChanged.connect(self._schedule_live_preview_update)
        for checkbox in self.findChildren(QCheckBox):
            checkbox.stateChanged.connect(self._schedule_live_preview_update)

    def _schedule_live_preview_update(self):
        if not self.preview_panel_toggle.isChecked():
            return
        self._pending_preview_refresh = True
        self._preview_update_timer.start()

    def _trigger_live_preview_update(self):
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

    def _toggle_preview_panel(self, _checked):
        visible = self.preview_panel_toggle.isChecked()
        self.preview_panel_body.setVisible(visible)
        if not visible:
            self._reset_preview_player()

    def check_for_updates(self):
        self.check_updates_action.setEnabled(False)
        worker = UpdateCheckWorker()
        worker.signals.finished.connect(self._handle_update_check_result)
        worker.signals.error.connect(self._handle_update_check_error)
        self._background_thread_pool.start(worker)

    def _handle_update_check_result(self, current_version: str, latest_version: str, url: str):
        self.check_updates_action.setEnabled(True)
        if not latest_version:
            QMessageBox.information(self, "Check for Updates", "Unable to determine the latest version.")
            return
        if updater.is_update_available(current_version, latest_version):
            message = QMessageBox(self)
            message.setIcon(QMessageBox.Icon.Information)
            message.setWindowTitle("Update Available")
            message.setText(
                f"A new version is available.\n\nCurrent: {current_version}\nLatest: {latest_version}"
            )
            open_button = message.addButton("Open Release Page", QMessageBox.ButtonRole.AcceptRole)
            message.addButton("Close", QMessageBox.ButtonRole.RejectRole)
            message.exec()
            if message.clickedButton() == open_button and url:
                QDesktopServices.openUrl(QUrl(url))
        else:
            QMessageBox.information(
                self,
                "Check for Updates",
                f"You are up to date.\n\nCurrent: {current_version}\nLatest: {latest_version}",
            )

    def _handle_update_check_error(self, error: str):
        self.check_updates_action.setEnabled(True)
        QMessageBox.warning(self, "Check for Updates", error)

    def _preview_volume_changed(self, value: int):
        if self._preview_audio_output is not None:
            self._preview_audio_output.setVolume(value / 100)

    def _reset_preview_player(self):
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

    def _show_preview_in_panel(self, video_data: VideoData):
        if not self.preview_panel_toggle.isChecked():
            return
        try:
            self.preview_video_widget.setMaximumSize(QSize(video_data.video_width, video_data.video_height))
        except Exception:
            pass
        self._preview_player.setSource(QUrl.fromLocalFile(video_data.file_path))
        self._preview_player.play()

    def _default_settings_path(self) -> Path:
        return get_config_dir() / "last_settings.json"

    def _collect_settings(self) -> dict:
        general = self.generalSettingsView.read_view_values()
        visualizer = self.generalVisualizerView.read_view_values()

        specific = {}
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
            }
        }

    def _apply_settings(self, data: dict) -> None:
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

        if "preview" in ui_state:
            self.preview_checkbox.setChecked(bool(ui_state["preview"]))
        if "show_output" in ui_state:
            self.show_output_checkbox.setChecked(bool(ui_state["show_output"]))
        if "preview_panel_visible" in ui_state:
            self.preview_panel_toggle.setChecked(bool(ui_state["preview_panel_visible"]))
            self._toggle_preview_panel(None)

    def _save_settings_to_path(self, path: Path) -> bool:
        try:
            data = self._collect_settings()
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            return False
        return True

    def _load_settings_from_path(self, path: Path) -> bool:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return False
        self._apply_settings(data)
        return True

    def _load_last_settings_if_present(self):
        path = self._default_settings_path()
        if path.exists():
            self._load_settings_from_path(path)

    def save_project(self):
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Save Project")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setNameFilter("JSON Files (*.json)")
        dialog.setDefaultSuffix("json")
        if dialog.exec():
            path = Path(dialog.selectedFiles()[0])
            if not self._save_settings_to_path(path):
                message = QMessageBox(QMessageBox.Icon.Critical, "Save Failed",
                                      "Unable to save the project file.")
                message.exec()

    def load_project(self):
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Load Project")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        dialog.setNameFilter("JSON Files (*.json)")
        if dialog.exec():
            path = Path(dialog.selectedFiles()[0])
            if not self._load_settings_from_path(path):
                message = QMessageBox(QMessageBox.Icon.Critical, "Load Failed",
                                      "Unable to load the project file.")
                message.exec()

    def closeEvent(self, event):
        self._save_settings_to_path(self._default_settings_path())
        super().closeEvent(event)

class UpdateCheckWorker(QRunnable):
    def __init__(self):
        super().__init__()

        class UpdateSignals(QObject):
            finished = Signal(str, str, str)
            error = Signal(str)

        self.signals = UpdateSignals()

    def run(self):
        try:
            current = updater.get_current_version()
            latest = updater.fetch_latest_release()
            self.signals.finished.emit(current, latest.get("version", ""), latest.get("url", ""))
        except Exception as exc:
            self.signals.error.emit(str(exc))

class RenderWorker(QRunnable):
    def __init__(self, audio_data: AudioData, video_data: VideoData, visualizer: Visualizer,
                 preview_seconds=None, include_audio=False):
        super().__init__()
        self.audio_data = audio_data
        self.video_data = video_data
        self.visualizer = visualizer
        self.preview_seconds = preview_seconds
        self.include_audio = include_audio
        self.audio_input_container = None
        self.audio_input_stream = None
        self.audio_output_stream = None
        self.audio_resampler = None
        self._cancel_requested = False
        self._logger = logging.getLogger(__name__)
        self._av = None

        class RenderSignals(QObject):
            finished = Signal(VideoData)
            error = Signal(str)
            status = Signal(str)
            progress = Signal(int, int, float)
            canceled = Signal()
        self.signals = RenderSignals()

    def _get_av(self):
        if self._av is None:
            import av
            self._av = av
        return self._av

    def cancel(self):
        self._cancel_requested = True

    def _check_canceled(self) -> bool:
        if not self._cancel_requested:
            return False
        self._cleanup_on_cancel()
        self.signals.canceled.emit()
        return True

    def _cleanup_on_cancel(self):
        try:
            if getattr(self.video_data, "container", None) is not None:
                self.video_data.container.close()
        except Exception:
            pass
        try:
            if self.audio_input_container is not None:
                self.audio_input_container.close()
        except Exception:
            pass

    def run(self):
        try:
            self.signals.status.emit("Opening audio file...")
            if not self.audio_data.load_audio_data(self.preview_seconds):
                error = self.audio_data.last_error or "Unknown error."
                self._logger.error("Audio load failed: %s", error)
                self.signals.error.emit(f"Error opening audio file: {error}")
                return
            if self._check_canceled():
                return
                
            self.signals.status.emit("Analyzing audio data...")
            self.audio_data.chunk_audio(self.video_data.fps)
            self.audio_data.analyze_audio()
            if self._check_canceled():
                return

            self.signals.status.emit("Preparing video environment...")
            if not self.video_data.prepare_container():
                error = self.video_data.last_error or "Unknown error."
                self._logger.error("Video container setup failed: %s", error)
                self.signals.error.emit(f"Error opening video file: {error}")
                return
            if self._check_canceled():
                return

            if self.include_audio:
                self.signals.status.emit("Preparing audio mux...")
                if not self._prepare_audio_mux():
                    error = self._last_error or "Unknown error."
                    self._logger.error("Audio mux prep failed: %s", error)
                    self.signals.error.emit(f"Error preparing audio stream: {error}")
                    return
                if self._check_canceled():
                    return
            self.visualizer.prepare_shapes()

            frames = len(self.audio_data.audio_frames)
            if self.preview_seconds is not None:
                frames = min(len(self.audio_data.audio_frames), self.video_data.fps * self.preview_seconds)

            self.signals.status.emit("Rendering video (0 %) ...")
            start_time = time.time()
            last_progress_emit = 0.0
            av = self._get_av()
            for i in range(frames):
                if self._check_canceled():
                    return
                img = self.visualizer.generate_frame(i)
                frame = av.VideoFrame.from_ndarray(img, format="rgb24")
                for packet in self.video_data.stream.encode(frame):
                    self.video_data.container.mux(packet)
                
                now = time.time()
                if now - last_progress_emit >= 0.5 or i == frames - 1:
                    elapsed = now - start_time
                    self.signals.progress.emit(i + 1, frames, elapsed)
                    last_progress_emit = now
                    
            
            self.signals.status.emit("Render finished, saving file...")
            if self._check_canceled():
                return
            if self.include_audio:
                self.signals.status.emit("Muxing audio...")
                mux_result = self._mux_audio()
                if mux_result is None:
                    return
                if mux_result is False:
                    error = self._last_error or "Unknown error."
                    self._logger.error("Audio mux failed: %s", error)
                    self.signals.error.emit(f"Error muxing audio: {error}")
                    return
            if not self.video_data.finalize():
                error = self.video_data.last_error or "Unknown error."
                self._logger.error("Finalize failed: %s", error)
                self.signals.error.emit(f"Error closing video file: {error}")
                return
            self.signals.finished.emit(self.video_data)
        except Exception as exc:
            self._logger.exception("Unhandled error during render.")
            self.signals.error.emit(f"Unexpected error: {exc}")

    def _prepare_audio_mux(self) -> bool:
        self._last_error = ""
        av = self._get_av()
        try:
            self.audio_input_container = av.open(self.audio_data.file_path)
        except Exception as exc:
            self._last_error = str(exc)
            return False

        for stream in self.audio_input_container.streams:
            if stream.type == "audio":
                self.audio_input_stream = stream
                break
        if self.audio_input_stream is None:
            self._last_error = "No audio stream found in input."
            return False

        try:
            self.audio_output_stream = self.video_data.container.add_stream("aac", rate=self.audio_input_stream.rate)
        except Exception as exc:
            self._last_error = str(exc)
            return False

        self.audio_output_stream.layout = self.audio_input_stream.layout.name
        self.audio_output_stream.sample_rate = self.audio_input_stream.rate
        self.audio_output_stream.time_base = Fraction(1, self.audio_output_stream.rate)

        resample_format = "fltp"
        if self.audio_output_stream.format is not None and self.audio_output_stream.format.name:
            resample_format = self.audio_output_stream.format.name
        self.audio_resampler = av.audio.resampler.AudioResampler(
            format=resample_format,
            layout=self.audio_output_stream.layout.name,
            rate=self.audio_output_stream.rate,
        )
        self._last_error = ""
        return True

    def _mux_audio(self) -> bool:
        if self.audio_input_container is None or self.audio_input_stream is None:
            self._last_error = "Missing audio input."
            return False
        if self.audio_output_stream is None or self.audio_resampler is None:
            self._last_error = "Missing audio output."
            return False

        samples_written = 0
        stop_at_time = False
        try:
            for packet in self.audio_input_container.demux(self.audio_input_stream):
                if self._cancel_requested:
                    self._cleanup_on_cancel()
                    self.signals.canceled.emit()
                    return None
                if stop_at_time:
                    break
                for frame in packet.decode():
                    if self._cancel_requested:
                        self._cleanup_on_cancel()
                        self.signals.canceled.emit()
                        return None
                    if self.preview_seconds is not None and frame.pts is not None:
                        time_seconds = float(frame.pts * frame.time_base)
                        if time_seconds >= self.preview_seconds:
                            stop_at_time = True
                            break
                    for resampled in self.audio_resampler.resample(frame):
                        if self._cancel_requested:
                            self._cleanup_on_cancel()
                            self.signals.canceled.emit()
                            return None
                        if resampled.pts is None:
                            resampled.pts = samples_written
                            resampled.time_base = self.audio_output_stream.time_base
                        samples_written += resampled.samples
                        for out_packet in self.audio_output_stream.encode(resampled):
                            self.video_data.container.mux(out_packet)
        except Exception as exc:
            self._last_error = str(exc)
            return False

        for out_packet in self.audio_output_stream.encode():
            self.video_data.container.mux(out_packet)

        try:
            self.audio_input_container.close()
        except Exception as exc:
            self._last_error = str(exc)
            return False
        return True

