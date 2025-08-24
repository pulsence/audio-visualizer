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
    QLayout, QGridLayout, QFormLayout, QHBoxLayout,
    QWidget, QComboBox, QLabel, QLineEdit, QPushButton, QCheckBox,
    QFileDialog, QColorDialog,
    QSizePolicy
)

from PySide6.QtGui import (
    QIntValidator, QFont
)

import os

from .generalView import View
from ui import Fonts

class GeneralSettings:
    video_width = 0
    video_height = 0
    fps = 0

    audio_file_path = ""
    video_file_path = ""

class GeneralSettingsView(View):

    def __init__(self,):
        super().__init__()

        form_layout = QFormLayout()

        section_label = QLabel("General Settings")
        section_label.setFont(Fonts.h2_font)
        section_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        section_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.layout.addWidget(section_label, 0, 0)

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

        self.layout.addLayout(form_layout, 1, 0)

    '''
    Verifies that the input values in the view are valide.
    '''
    def validate_view(self) -> bool:
        try:
            video_width = int(self.video_width.text())
            video_height = int(self.video_height.text())
            fps = int(self.visualizer_fps.text())
        except:
            return False
        
        if not os.path.isfile(self.audio_file_path.text()):
            return False
        
        ext = os.path.splitext(self.video_file_path.text())[1]
        if ext == '':
            self.video_file_path.setText(self.video_file_path.text() + ".mp4")
        elif not ext == ".mp4":
            return False
        return True

    '''
    Transforms the input values in the view into a python object.
    '''
    def read_view_values(self) -> GeneralSettings:
        settings = GeneralSettings()
        settings.video_width = int(self.video_width.text())
        settings.video_height = int(self.video_height.text())
        settings.fps = int(self.visualizer_fps.text())

        settings.audio_file_path = self.audio_file_path.text()
        settings.video_file_path = self.video_file_path.text()

        return settings