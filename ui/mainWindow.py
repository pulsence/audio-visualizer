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
    Qt, QRunnable, QThreadPool, QObject, Signal
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

from visualizers.utilities import AudioData, VideoData

from visualizers.volume import (
    RectangleVisualizer, CircleVisualizer
)

from ui import (
    Fonts, RenderDialog,
    RectangleVisualizerView, RectangleVisualizerSettings,
    CircleVisualizerView,
    GeneralSettingsView, GeneralSettings,
    GeneralVisualizerView, GeneralVisualizerSettings
)

import av

import os

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
        self.rectangleVisualizerView = RectangleVisualizerView()
        self.rectangleVisualizerView.get_view_in_widget().show()
        main_layout.addWidget(self.rectangleVisualizerView.get_view_in_widget(), 1, 0)
        self.visualizer_views.append(self.rectangleVisualizerView)
        
        self.circleVisualizerView = CircleVisualizerView()
        self.circleVisualizerView.get_view_in_widget().hide()
        main_layout.addWidget(self.circleVisualizerView.get_view_in_widget(), 1, 0)
        self.visualizer_views.append(self.circleVisualizerView)

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

        self.render_button = QPushButton("Render Video")
        self.render_button.clicked.connect(self.render_video)
        render_section_layout.addWidget(self.render_button, 1, 0, 1, 2)

        layout.addLayout(render_section_layout, r, c)

    def visualizer_selection_changed(self, visualizer):
        for view in self.visualizer_views:
            view.get_view_in_widget().hide()

        if visualizer == "Circle":
            self.circleVisualizerView.get_view_in_widget().show()
        else:
            self.rectangleVisualizerView.get_view_in_widget().show()

    def validate_render_settings(self):
        if not self.generalSettingsView.validate_view():
            return False
        if not self.generalVisualizerView.validate_view():
            return False
        if not self.rectangleVisualizerView.validate_view():
            return False
        if not self.circleVisualizerView.validate_view():
            return False
        
        return True

    def render_video(self):
        if self.rendering:
            return
        
        self.rendering = True
        self.render_button.setText("Rendering...")
        self.render_button.setEnabled(False)

        if not self.validate_render_settings():
            self.rendering = False
            self.render_button.setEnabled(True)
            self.render_button.setText("Render Video")
            message = QMessageBox(QMessageBox.Icon.Critical, "Settings Error",
                                  "One of your settings are invalid. The render cannot run. Please double check the values inputed.")
            message.exec()
            return

        general_settings = self.generalSettingsView.read_view_values()

        preview = self.preview_checkbox.isChecked()

        visualizer_settings = self.generalVisualizerView.read_view_values()

        audio_data = AudioData(general_settings.audio_file_path)
        video_data = VideoData(general_settings.video_width, general_settings.video_height,
                               general_settings.fps, file_path=general_settings.video_file_path)

        visualizer = None
        if visualizer_settings.visualizer_type == "Rectangle":
            settings = self.rectangleVisualizerView.read_view_values()

            visualizer = RectangleVisualizer(
                audio_data, video_data, visualizer_settings.x, visualizer_settings.y, 
                super_sampling=visualizer_settings.super_sampling,
                box_height=settings.box_height, box_width=settings.box_width,
                corner_radius=settings.corner_radius,
                border_width=visualizer_settings.border_width, spacing=visualizer_settings.spacing,
                bg_color=visualizer_settings.bg_color, border_color=visualizer_settings.border_color,
                alignment=visualizer_settings.alignment, flow=visualizer_settings.flow
            )
        elif visualizer_settings.visualizer_type == "Circle":
            settings = self.circleVisualizerView.read_view_values()

            visualizer = CircleVisualizer(
                audio_data, video_data, visualizer_settings.x, visualizer_settings.y,
                super_sampling=visualizer_settings.super_sampling,
                max_radius=settings.radius, border_width=visualizer_settings.border_width, 
                spacing=visualizer_settings.spacing,
                bg_color=visualizer_settings.bg_color, border_color=visualizer_settings.border_color,
                alignment=visualizer_settings.alignment, flow=visualizer_settings.flow
            )
        
        render_worker = RenderWorker(audio_data, video_data, visualizer, preview)
        render_worker.signals.finished.connect(self.render_finished)
        render_worker.signals.error.connect(self.render_failed)
        self.render_thread_pool.start(render_worker)
    
    def render_finished(self, output_path):
        self.rendering = False
        self.render_button.setEnabled(True)
        self.render_button.setText("Render Video")

        if self.show_output_checkbox.isChecked():
            player = RenderDialog(output_path)
            player.exec()
    
    def render_failed(self, msg):
        self.rendering = False
        self.render_button.setEnabled(True)
        self.render_button.setText("Render Video")
        message = QMessageBox(QMessageBox.Icon.Critical, "Error rendering",
                              f"There was an error rendering the video. The error message is: {msg}")
        message.exec()

class RenderWorker(QRunnable):
    def __init__(self, audio_data: AudioData, video_data: VideoData, visualizer: Visualizer, preview: bool):
        super().__init__()
        self.audio_data = audio_data
        self.video_data = video_data
        self.visualizer = visualizer
        self.preview = preview

        class RenderSignals(QObject):
            finished = Signal(str)
            error = Signal(str)
        self.signals = RenderSignals()

    def run(self):
        if not self.audio_data.load_audio_data(self.preview):
            self.signals.error.emit("Error opening audio file.")
        self.audio_data.chunk_audio(self.video_data.fps)
        self.audio_data.analyze_audio()


        if not self.video_data.prepare_container():
            self.signals.error.emit("Error opening video file.")
        self.visualizer.prepare_shapes()

        ''' If preview is True, limit to 30 seconds of video. '''
        max_frames = min(len(self.audio_data.audio_frames), self.video_data.fps * 30 if self.preview else len(self.audio_data.audio_frames))

        for i in range(len(self.audio_data.audio_frames)):
            if i > max_frames:
                break
            img = self.visualizer.generate_frame(i)
            frame = av.VideoFrame.from_ndarray(img, format="rgb24")
            for packet in self.video_data.stream.encode(frame):
                self.video_data.container.mux(packet)
        
        if not self.video_data.finalize():
            self.signals.error.emit("Error closing video file.")
        self.signals.finished.emit(self.video_data.file_path)