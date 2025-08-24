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

from visualizers.utilities import AudioData, VideoData
from visualizers.volume import (
    RectangleVisualizer, CircleVisualizer
)

from .renderDialog import RenderDialog
from .rectangleVisualizerView import RectangleVisualizerView
from .circleVisualizerView import CircleVisualizerView

import av

import os

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Visualizer")
        self.setGeometry(100, 100, 800, 500)
        
        self.h1_font = QFont()
        self.h1_font.setBold(True)
        self.h1_font.setPointSize(24)

        self.h2_font = QFont()
        self.h2_font.setUnderline(True)
        self.h2_font.setPointSize(16)

        primary_layout = QGridLayout()

        self.heading_label = QLabel("Welcome to the Audio Visualizer!")
        self.heading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.heading_label.setFont(self.h1_font)
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
        main_layout = QGridLayout()
        form_layout = QFormLayout()

        section_label = QLabel("General Settings")
        section_label.setFont(self.h2_font)
        section_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        section_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        main_layout.addWidget(section_label, 0, 0)

        audio_file_row = QHBoxLayout()
        self.audio_file_path = QLineEdit("sample_audio.mp3")
        self.audio_file_path.setPlaceholderText("Path to audio file")
        audio_file_row.addWidget(self.audio_file_path)
        self.audio_file_button = QPushButton("Select Audio File")
        self.audio_file_dialog = QFileDialog()
        self.audio_file_dialog.setWindowTitle("Select Audio File")
        self.audio_file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        self.audio_file_dialog.setNameFilter("Audio Files (*.mp3 *.wav *.flac)")
        self.audio_file_dialog.fileSelected.connect(self.audio_file_path.setText)
        self.audio_file_button.clicked.connect(self.audio_file_dialog.open)
        audio_file_row.addWidget(self.audio_file_button)
        form_layout.addRow("Audio File Path:", audio_file_row)

        video_file_row = QHBoxLayout()
        self.video_file_path = QLineEdit("output.mp4")
        self.video_file_path.setPlaceholderText("Path to output video file")
        video_file_row.addWidget(self.video_file_path)
        self.video_file_button = QPushButton("Select Video File")
        self.video_file_dialog = QFileDialog()
        self.video_file_dialog.setWindowTitle("Select Video File")
        self.video_file_dialog.setFileMode(QFileDialog.FileMode.AnyFile)
        self.video_file_dialog.setNameFilter("Video Files (*.mp4)")
        self.video_file_dialog.fileSelected.connect(self.video_file_path.setText)
        self.video_file_button.clicked.connect(self.video_file_dialog.open)
        video_file_row.addWidget(self.video_file_button)
        form_layout.addRow("Output Video File Path:", video_file_row)

        self.visualizer_fps = QLineEdit("16")
        self.visualizer_fps.setValidator(QIntValidator(1, 60))
        form_layout.addRow("Visual Frames Per Second (FPS):", self.visualizer_fps)

        self.video_width = QLineEdit("480")
        self.video_width.setValidator(QIntValidator(1, 1920))
        form_layout.addRow("Video Width:", self.video_width)

        self.video_height = QLineEdit("100")
        self.video_height.setValidator(QIntValidator(1, 1080))
        form_layout.addRow("Video Height:", self.video_height)

        main_layout.addLayout(form_layout, 1, 0)
        layout.addLayout(main_layout, r, c,)

    '''
    Settings for general visualization items in (1, 1)
    '''
    def _prepare_general_visualizer_elements(self, layout: QGridLayout, r=1, c=1):
        main_layout = QGridLayout()
        form_layout = QFormLayout()

        section_label = QLabel("General Visualization Settings")
        section_label.setFont(self.h2_font)
        section_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        section_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        main_layout.addWidget(section_label, 0, 0)
        
        self.visualizer_x = QLineEdit("0")
        self.visualizer_x.setValidator(QIntValidator(0, 1e6))
        form_layout.addRow("Visualizer X:", self.visualizer_x)

        self.visualizer_y = QLineEdit("50")
        self.visualizer_y.setValidator(QIntValidator(0, 1e6))
        form_layout.addRow("Visualizer Y:", self.visualizer_y)

        self.visualizer = QComboBox()
        self.visualizer.addItems(["Rectangle", "Circle"])
        self.visualizer.currentTextChanged.connect(self.visualizer_selection_changed)
        form_layout.addRow("Visualizer Type:", self.visualizer)

        self.visualizer_alignment = QComboBox()
        self.visualizer_alignment.addItems(["Bottom", "Center"])
        form_layout.addRow("Alignment:", self.visualizer_alignment)

        self.visualizer_flow = QComboBox()
        self.visualizer_flow.addItems(["Left to Right", "Center Outward"])
        form_layout.addRow("Flow:", self.visualizer_flow)

        bg_row = QHBoxLayout()
        self.visualizer_bg_color_field = QLineEdit("227, 209, 169")
        self.visualizer_bg_color_field.setPlaceholderText("R, G, B")
        bg_row.addWidget(self.visualizer_bg_color_field)
        self.visualizer_bg_color_button = QPushButton("Select Color")
        self.visualizer_bg_color = QColorDialog()
        self.visualizer_bg_color.colorSelected.connect(lambda color: self.visualizer_bg_color_field.setText(
            f"{color.red()}, {color.green()}, {color.blue()}"
        ))
        self.visualizer_bg_color_button.clicked.connect(self.visualizer_bg_color.open)
        bg_row.addWidget(self.visualizer_bg_color_button)
        form_layout.addRow("Background Color:", bg_row)

        self.visualizer_border_width = QLineEdit("1")
        self.visualizer_border_width.setValidator(QIntValidator(0, int(1e6)))
        form_layout.addRow("Border Width:", self.visualizer_border_width)

        border_row = QHBoxLayout()
        self.visualizer_border_color_field = QLineEdit("227, 209, 169")
        self.visualizer_border_color_field.setPlaceholderText("R, G, B")   
        border_row.addWidget(self.visualizer_border_color_field)
        self.visualizer_border_color_button = QPushButton("Select Color")
        self.visualizer_border_color = QColorDialog()
        self.visualizer_border_color.colorSelected.connect(lambda color: self.visualizer_border_color_field.setText(
            f"{color.red()}, {color.green()}, {color.blue()}"
        ))
        self.visualizer_border_color_button.clicked.connect(self.visualizer_border_color.open)
        border_row.addWidget(self.visualizer_border_color_button)
        form_layout.addRow("Border Color:", border_row)

        self.visualizer_spacing = QLineEdit("5")
        self.visualizer_spacing.setValidator(QIntValidator(0, int(1e6)))
        form_layout.addRow("Spacing:", self.visualizer_spacing)
        
        main_layout.addLayout(form_layout, 1, 0)
        layout.addLayout(main_layout, r, c)

    '''
    Settings for specific visualizes in (2, 1)
    '''
    def _prepare_specific_visualizer_elements(self, layout: QGridLayout, r=2, c=1):
        main_layout = QGridLayout()
        
        section_label = QLabel("Selected Visualizer Settings")
        section_label.setFont(self.h2_font)
        section_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        section_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        main_layout.addWidget(section_label, 0, 0)

        self.visualizer_views = []
        self.rectangleVisualizerView = RectangleVisualizerView()
        main_layout.addWidget(self.rectangleVisualizerView.get_view_in_widget(), 1, 0)
        self.visualizer_views.append(self.rectangleVisualizerView)
        
        self.circleVisualizerView = CircleVisualizerView(show=False)
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
        try:
            video_width = int(self.video_width.text())
            video_height = int(self.video_height.text())
            fps = int(self.visualizer_fps.text())
            x = int(self.visualizer_x.text())
            y = int(self.visualizer_y.text())

            bg_color = tuple(map(int, self.visualizer_bg_color_field.text().split(',')))
            border_color = tuple(map(int, self.visualizer_border_color_field.text().split(',')))
            border_width = int(self.visualizer_border_width.text())

            spacing = int(self.visualizer_spacing.text())
        except:
            return False

        if not self.rectangleVisualizerView.validate_view():
            return False
        if not self.circleVisualizerView.validate_view():
            return False

        if not os.path.isfile(self.audio_file_path.text()):
            return False
        
        ext = os.path.splitext(self.video_file_path.text())[1]
        if ext == '':
            self.audio_file_button.setText(self.video_file_path.text() + ".mp4")
        elif not ext == ".mp4":
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

        audio_file_path = self.audio_file_path.text()
        video_file_path = self.video_file_path.text()
        preview = self.preview_checkbox.isChecked()

        video_width = int(self.video_width.text())
        video_height = int(self.video_height.text())
        fps = int(self.visualizer_fps.text())
        x = int(self.visualizer_x.text())
        y = int(self.visualizer_y.text())

        visualizer_type = self.visualizer.currentText()
        alignment = self.visualizer_alignment.currentText().lower()

        flow = self.visualizer_flow.currentText()
        if flow == "Left to Right":
            flow = "sideways"
        elif flow == "Center Outward":
            flow = "center"
        
        
        bg_color = tuple(map(int, self.visualizer_bg_color_field.text().split(',')))
        border_color = tuple(map(int, self.visualizer_border_color_field.text().split(',')))
        border_width = int(self.visualizer_border_width.text())

        spacing = int(self.visualizer_spacing.text())

        audio_data = AudioData(audio_file_path)
        video_data = VideoData(video_width, video_height, fps, file_path=video_file_path)

        visualizer = None
        if visualizer_type == "Rectangle":
            box_height = int(self.rectangleVisualizerView.box_height.text())
            box_width = int(self.rectangleVisualizerView.box_width.text())
            corner_radius = int(self.rectangleVisualizerView.corner_radius.text())
            super_sample = int(self.rectangleVisualizerView.super_sampling.text())

            visualizer = RectangleVisualizer(
                audio_data, video_data, x, y, super_sampling=super_sample,
                box_height=box_height, box_width=box_width, corner_radius=corner_radius,
                border_width=border_width, spacing=spacing,
                bg_color=bg_color, border_color=border_color,
                alignment=alignment, flow=flow
            )
        elif visualizer_type == "Circle":
            radius = int(self.circleVisualizerView.radius.text())
            super_sample = int(self.circleVisualizerView.super_sampling.text())

            visualizer = CircleVisualizer(
                audio_data, video_data, x, y, super_sampling=super_sample,
                max_radius=radius, border_width=border_width, spacing=spacing,
                bg_color=bg_color, border_color=border_color,
                alignment=alignment, flow=flow
            )
        
        render_worker = RenderWorker(audio_data, video_data, visualizer, preview)
        render_worker.signals.finished.connect(self.render_finished)
        render_worker.signals.error.connect(self.render_failed)
        self.render_thread_pool.start(render_worker)
    
    def render_finished(self):
        self.rendering = False
        self.render_button.setEnabled(True)
        self.render_button.setText("Render Video")

        if self.show_output_checkbox.isChecked():
            player = RenderDialog(self.video_file_path.text())
            player.exec()
    
    def render_failed(self, msg):
        self.rendering = False
        self.render_button.setEnabled(True)
        self.render_button.setText("Render Video")
        message = QMessageBox(QMessageBox.Icon.Critical, "Error rendering",
                              f"There was an error rendering the video. The error message is: {msg}")
        message.exec()

class RenderWorker(QRunnable):
    def __init__(self, audio_data, video_data, visualizer, preview):
        super().__init__()
        self.audio_data = audio_data
        self.video_data = video_data
        self.visualizer = visualizer
        self.preview = preview

        class RenderSignals(QObject):
            finished = Signal()
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
            img = self.visualizer.draw_frame(i)
            frame = av.VideoFrame.from_ndarray(img, format="rgb24")
            for packet in self.video_data.stream.encode(frame):
                self.video_data.container.mux(packet)
        
        if not self.video_data.finalize():
            self.signals.error.emit("Error closing video file.")
        self.signals.finished.emit()