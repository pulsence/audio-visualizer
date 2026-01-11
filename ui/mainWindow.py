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
    Qt, QRunnable, QThreadPool, QObject, Signal, QTimer
)

from PySide6.QtWidgets import (
    QMainWindow, QMessageBox, QGridLayout, QFormLayout, QHBoxLayout,
    QWidget, QComboBox, QLabel, QLineEdit, QPushButton, QCheckBox,
    QFileDialog, QColorDialog,
    QSizePolicy
)

from PySide6.QtGui import (
    QIntValidator, QFont
)

from visualizers import Visualizer

from visualizers.utilities import AudioData, VideoData, VisualizerOptions

from visualizers import (
    volume, chroma, waveform, combined
)

from ui import (
    Fonts, RenderDialog,
    RectangleVolumeVisualizerView, RectangleVolumeVisualizerSettings,
    CircleVolumeVisualizerView, CircleVolumeVisualizerSettings,
    RectangleChromaVisualizerView, RectangleChromaVisualizerSettings,
    CircleChromeVisualizerView, CircleChromeVisualizerSettings,
    WaveformVisualizerView, WaveformVisualizerSettings,
    CombinedVisualizerView, CombinedVisualizerSettings,
    GeneralSettingsView, GeneralSettings,
    GeneralVisualizerView, GeneralVisualizerSettings
)

import av
import json
import time
from fractions import Fraction
from pathlib import Path

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Visualizer")
        self.setGeometry(100, 100, 800, 500)

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
        self._preview_dialog = None
        self._pending_preview_refresh = False
        self._preview_update_timer = QTimer(self)
        self._preview_update_timer.setSingleShot(True)
        self._preview_update_timer.setInterval(400)
        self._preview_update_timer.timeout.connect(self._trigger_live_preview_update)

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

        self.visualizer_views = []
        self.rectangleVolumeVisualizerView = RectangleVolumeVisualizerView()
        self.rectangleVolumeVisualizerView.get_view_in_widget().show()
        main_layout.addWidget(self.rectangleVolumeVisualizerView.get_view_in_widget(), 1, 0)
        self.visualizer_views.append(self.rectangleVolumeVisualizerView)
        
        self.circleVolumeVisualizerView = CircleVolumeVisualizerView()
        self.circleVolumeVisualizerView.get_view_in_widget().hide()
        main_layout.addWidget(self.circleVolumeVisualizerView.get_view_in_widget(), 1, 0)
        self.visualizer_views.append(self.circleVolumeVisualizerView)

        self.rectangleChromaVisualizerView = RectangleChromaVisualizerView()
        self.rectangleChromaVisualizerView.get_view_in_widget().hide()
        main_layout.addWidget(self.rectangleChromaVisualizerView.get_view_in_widget(), 1, 0)
        self.visualizer_views.append(self.rectangleChromaVisualizerView)
        
        self.circleChromaVisualizerView = CircleChromeVisualizerView()
        self.circleChromaVisualizerView.get_view_in_widget().hide()
        main_layout.addWidget(self.circleChromaVisualizerView.get_view_in_widget(), 1, 0)
        self.visualizer_views.append(self.circleChromaVisualizerView)

        self.waveformVisualizerView = WaveformVisualizerView()
        self.waveformVisualizerView.get_view_in_widget().hide()
        main_layout.addWidget(self.waveformVisualizerView.get_view_in_widget(), 1, 0)
        self.visualizer_views.append(self.waveformVisualizerView)

        self.combinedVisualizerView = CombinedVisualizerView()
        self.combinedVisualizerView.get_view_in_widget().hide()
        main_layout.addWidget(self.combinedVisualizerView.get_view_in_widget(), 1, 0)
        self.visualizer_views.append(self.combinedVisualizerView)

        layout.addLayout(main_layout, r, c)

    '''
    UI elements to launch a render in (3, 0)
    '''
    def _prepare_render_elements(self, layout: QGridLayout, r=3, c=0):
        render_section_layout = QGridLayout()

        self.preview_checkbox = QCheckBox("Preview Video (30 seconds)")
        self.preview_checkbox.setChecked(True)
        render_section_layout.addWidget(self.preview_checkbox, 0, 0)

        self.show_output_checkbox = QCheckBox("Show Rendered Video")
        self.show_output_checkbox.setChecked(True)
        render_section_layout.addWidget(self.show_output_checkbox, 0, 1)

        self.preview_button = QPushButton("Live Preview (5s)")
        self.preview_button.clicked.connect(self.render_preview)
        render_section_layout.addWidget(self.preview_button, 1, 0)

        self.render_button = QPushButton("Render Video")
        self.render_button.clicked.connect(self.render_video)
        render_section_layout.addWidget(self.render_button, 1, 1)

        self.save_project_button = QPushButton("Save Project")
        self.save_project_button.clicked.connect(self.save_project)
        render_section_layout.addWidget(self.save_project_button, 2, 0)

        self.load_project_button = QPushButton("Load Project")
        self.load_project_button.clicked.connect(self.load_project)
        render_section_layout.addWidget(self.load_project_button, 2, 1)

        layout.addLayout(render_section_layout, r, c)

        self.render_status_label = QLabel()
        self.render_status_label.hide()
        layout.addWidget(self.render_status_label, r, c+1)


    def visualizer_selection_changed(self, visualizer):
        for view in self.visualizer_views:
            view.get_view_in_widget().hide()

        visualizer = VisualizerOptions(visualizer)

        if visualizer == VisualizerOptions.VOLUME_CIRCLE:
            self.circleVolumeVisualizerView.get_view_in_widget().show()
        elif visualizer == VisualizerOptions.VOLUME_RECTANGLE:
            self.rectangleVolumeVisualizerView.get_view_in_widget().show()
        elif visualizer == VisualizerOptions.CHROMA_RECTANGLE:
            self.rectangleChromaVisualizerView.get_view_in_widget().show()
        elif visualizer == VisualizerOptions.CHROMA_CIRCLE:
            widget = self.circleChromaVisualizerView.get_view_in_widget().show()
        elif visualizer == VisualizerOptions.WAVEFORM:
            self.waveformVisualizerView.get_view_in_widget().show()
        elif visualizer == VisualizerOptions.COMBINED_RECTANGLE:
            self.combinedVisualizerView.get_view_in_widget().show()

    def validate_render_settings(self):
        if not self.generalSettingsView.validate_view():
            return False
        if not self.generalVisualizerView.validate_view():
            return False
        
        selected = VisualizerOptions(self.generalVisualizerView.visualizer.currentText())
        if selected == VisualizerOptions.VOLUME_RECTANGLE and not self.rectangleVolumeVisualizerView.validate_view():
            return False
        elif selected == VisualizerOptions.VOLUME_CIRCLE and not self.circleVolumeVisualizerView.validate_view():
            return False
        elif selected == VisualizerOptions.CHROMA_RECTANGLE and not self.rectangleChromaVisualizerView.validate_view():
            return False
        elif selected == VisualizerOptions.CHROMA_CIRCLE and not self.circleChromaVisualizerView.validate_view():
            return False
        elif selected == VisualizerOptions.WAVEFORM and not self.waveformVisualizerView.validate_view():
            return False
        elif selected == VisualizerOptions.COMBINED_RECTANGLE and not self.combinedVisualizerView.validate_view():
            return False
        
        return True

    def _preview_output_path(self) -> str:
        return str(Path(__file__).resolve().parent.parent / "preview_output.mp4")

    def _create_visualizer(self, audio_data: AudioData, video_data: VideoData, visualizer_settings: GeneralVisualizerSettings):
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
        self.render_button.setEnabled(True)
        self.preview_button.setEnabled(True)
        self.render_button.setText("Render Video")
        self.preview_button.setText("Live Preview (5s)")
        self.render_status_label.hide()
        self._active_preview = False

    def _start_render(self, preview_seconds=None, output_path=None, force_show_output=None, show_validation_errors=True):
        if self.rendering:
            return
        
        self.rendering = True
        self._active_preview = preview_seconds is not None and output_path == self._preview_output_path()
        self.render_button.setEnabled(False)
        self.preview_button.setEnabled(False)
        if self._active_preview:
            self.preview_button.setText("Previewing...")
        else:
            self.render_button.setText("Rendering...")

        self.render_status_label.show()
        self.render_status_label.setText("Setting up render...")

        if not self.validate_render_settings():
            self._reset_render_controls()

            if show_validation_errors:
                message = QMessageBox(QMessageBox.Icon.Critical, "Settings Error",
                                      "One of your settings are invalid. The render cannot run. Please double check the values inputed.")
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
        render_worker.signals.finished.connect(self.render_finished)
        render_worker.signals.error.connect(self.render_failed)
        render_worker.signals.status.connect(self.render_status_update)
        self.render_thread_pool.start(render_worker)

    def render_video(self):
        preview_seconds = 30 if self.preview_checkbox.isChecked() else None
        self._start_render(preview_seconds=preview_seconds)

    def render_preview(self):
        self._start_render(preview_seconds=5, output_path=self._preview_output_path(), force_show_output=True)
    
    def render_finished(self, video_data: VideoData):
        if self._show_output_for_last_render:
            if self._active_preview:
                if self._preview_dialog is not None and self._preview_dialog.isVisible():
                    self._preview_dialog.close()
                self._preview_dialog = RenderDialog(video_data)
                self._preview_dialog.setWindowModality(Qt.WindowModality.NonModal)
                self._preview_dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
                self._preview_dialog.finished.connect(lambda _: setattr(self, "_preview_dialog", None))
                self._preview_dialog.show()
            else:
                player = RenderDialog(video_data)
                player.exec()
        self._reset_render_controls()
        if self._pending_preview_refresh:
            self._trigger_live_preview_update()
    
    def render_failed(self, msg):
        message = QMessageBox(QMessageBox.Icon.Critical, "Error rendering",
                              f"There was an error rendering the video. The error message is: {msg}")
        message.exec()
        self._reset_render_controls()

    def render_status_update(self, msg):
        self.render_status_label.setText(msg)

    def _connect_live_preview_updates(self):
        for field in self.findChildren(QLineEdit):
            field.textChanged.connect(self._schedule_live_preview_update)
        for combo in self.findChildren(QComboBox):
            combo.currentTextChanged.connect(self._schedule_live_preview_update)
        for checkbox in self.findChildren(QCheckBox):
            checkbox.stateChanged.connect(self._schedule_live_preview_update)

    def _schedule_live_preview_update(self):
        if not self._active_preview and (self._preview_dialog is None or not self._preview_dialog.isVisible()):
            return
        self._pending_preview_refresh = True
        self._preview_update_timer.start()

    def _trigger_live_preview_update(self):
        if not self._active_preview and (self._preview_dialog is None or not self._preview_dialog.isVisible()):
            self._pending_preview_refresh = False
            return
        if self.rendering:
            return
        if not self.validate_render_settings():
            self._pending_preview_refresh = False
            return
        self._pending_preview_refresh = False
        self._start_render(
            preview_seconds=5,
            output_path=self._preview_output_path(),
            force_show_output=True,
            show_validation_errors=False,
        )

    def _default_settings_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / "last_settings.json"

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

        if "preview" in ui_state:
            self.preview_checkbox.setChecked(bool(ui_state["preview"]))
        if "show_output" in ui_state:
            self.show_output_checkbox.setChecked(bool(ui_state["show_output"]))

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

        class RenderSignals(QObject):
            finished = Signal(VideoData)
            error = Signal(str)
            status = Signal(str)
        self.signals = RenderSignals()

    def run(self):
        self.signals.status.emit("Opening audio file...")
        if not self.audio_data.load_audio_data(self.preview_seconds):
            self.signals.error.emit("Error opening audio file.")
            return
            
        self.signals.status.emit("Analyzing audio data...")
        self.audio_data.chunk_audio(self.video_data.fps)
        self.audio_data.analyze_audio()

        self.signals.status.emit("Preparing video environment...")
        if not self.video_data.prepare_container():
            self.signals.error.emit("Error opening video file.")
            return

        if self.include_audio:
            self.signals.status.emit("Preparing audio mux...")
            if not self._prepare_audio_mux():
                self.signals.error.emit("Error preparing audio stream.")
                return
        self.visualizer.prepare_shapes()

        frames = len(self.audio_data.audio_frames)
        if self.preview_seconds is not None:
            frames = min(len(self.audio_data.audio_frames), self.video_data.fps * self.preview_seconds)

        self.signals.status.emit("Rendering video (0 %) ...")
        for i in range(frames):
            img = self.visualizer.generate_frame(i)
            frame = av.VideoFrame.from_ndarray(img, format="rgb24")
            for packet in self.video_data.stream.encode(frame):
                self.video_data.container.mux(packet)
            
            if int(time.time()) % 5 == 0:
                prog = int((i / frames) * 100)
                self.signals.status.emit(f"Rendering video ({prog} %) ...")
                
        
        self.signals.status.emit("Render finished, saving file...")
        if self.include_audio:
            self.signals.status.emit("Muxing audio...")
            if not self._mux_audio():
                self.signals.error.emit("Error muxing audio.")
                return
        if not self.video_data.finalize():
            self.signals.error.emit("Error closing video file.")
            return
        self.signals.finished.emit(self.video_data)

    def _prepare_audio_mux(self) -> bool:
        try:
            self.audio_input_container = av.open(self.audio_data.file_path)
        except Exception:
            return False

        for stream in self.audio_input_container.streams:
            if stream.type == "audio":
                self.audio_input_stream = stream
                break
        if self.audio_input_stream is None:
            return False

        try:
            self.audio_output_stream = self.video_data.container.add_stream("aac", rate=self.audio_input_stream.rate)
        except Exception:
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
        return True

    def _mux_audio(self) -> bool:
        if self.audio_input_container is None or self.audio_input_stream is None:
            return False
        if self.audio_output_stream is None or self.audio_resampler is None:
            return False

        samples_written = 0
        stop_at_time = False
        for packet in self.audio_input_container.demux(self.audio_input_stream):
            if stop_at_time:
                break
            for frame in packet.decode():
                if self.preview_seconds is not None and frame.pts is not None:
                    time_seconds = float(frame.pts * frame.time_base)
                    if time_seconds >= self.preview_seconds:
                        stop_at_time = True
                        break
                for resampled in self.audio_resampler.resample(frame):
                    if resampled.pts is None:
                        resampled.pts = samples_written
                        resampled.time_base = self.audio_output_stream.time_base
                    samples_written += resampled.samples
                    for out_packet in self.audio_output_stream.encode(resampled):
                        self.video_data.container.mux(out_packet)

        for out_packet in self.audio_output_stream.encode():
            self.video_data.container.mux(out_packet)

        try:
            self.audio_input_container.close()
        except Exception:
            return False
        return True
