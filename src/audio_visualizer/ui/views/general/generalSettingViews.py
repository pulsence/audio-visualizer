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
    Qt
)

from PySide6.QtWidgets import (
    QLayout, QGridLayout, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QComboBox,
    QFileDialog,
    QSizePolicy
)
from PySide6.QtGui import (
    QIntValidator
)

import os
from pathlib import Path

from audio_visualizer.app_paths import get_data_dir
from .generalView import View
from audio_visualizer.ui.views.general.utilities import Fonts

class GeneralSettings:
    video_width = 0
    video_height = 0
    fps = 0
    codec = ""
    bitrate = None
    crf = None
    hardware_accel = False
    include_audio = False

    audio_file_path = ""
    video_file_path = ""

class GeneralSettingsView(View):

    def __init__(self,):
        super().__init__()
        self.last_error = ""

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
        self.audio_file_button.clicked.connect(self._on_audio_file_button_clicked)
        audio_file_row.addWidget(self.audio_file_button)
        form_layout.addRow("Audio File Path:", audio_file_row)

        video_file_row = QHBoxLayout()
        default_video_path = str(get_data_dir() / "output.mp4")
        self.video_file_path = QLineEdit(default_video_path)
        self.video_file_path.setPlaceholderText("Path to output video file")
        video_file_row.addWidget(self.video_file_path)
        self.video_file_button = QPushButton("Select Video File")
        self.video_file_dialog = QFileDialog()
        self.video_file_dialog.setWindowTitle("Select Video File")
        self.video_file_dialog.setFileMode(QFileDialog.FileMode.AnyFile)
        self.video_file_dialog.setNameFilter("Video Files (*.mp4)")
        self.video_file_dialog.fileSelected.connect(self.video_file_path.setText)
        self.video_file_button.clicked.connect(self._on_video_file_button_clicked)
        video_file_row.addWidget(self.video_file_button)
        form_layout.addRow("Output Video File Path:", video_file_row)

        self.visualizer_fps = QLineEdit("12")
        form_layout.addRow("Visual Frames Per Second (FPS):", self.visualizer_fps)

        self.video_width = QLineEdit("720")
        form_layout.addRow("Video Width:", self.video_width)

        self.video_height = QLineEdit("100")
        form_layout.addRow("Video Height:", self.video_height)

        self.codec = QComboBox()
        self.codec.setEditable(False)
        self.codec.addItems(["h264", "hevc", "vp9", "av1", "mpeg4"])
        self.codec.setCurrentText("h264")
        self.codec.setToolTip("Codec (e.g. h264, hevc, vp9)")
        form_layout.addRow("Video Codec:", self.codec)

        self.bitrate = QLineEdit("")
        self.bitrate.setPlaceholderText("Optional bitrate in bps")
        self.bitrate.setValidator(QIntValidator(1, int(1e9)))
        form_layout.addRow("Video Bitrate (bps):", self.bitrate)

        self.crf = QLineEdit("")
        self.crf.setPlaceholderText("Optional CRF (e.g. 18-28)")
        self.crf.setValidator(QIntValidator(0, 51))
        form_layout.addRow("CRF:", self.crf)

        self.hardware_accel = QCheckBox("Hardware Acceleration (if available)")
        form_layout.addRow("", self.hardware_accel)

        self.include_audio = QCheckBox("Include Audio in Output")
        self.include_audio.setChecked(True)
        form_layout.addRow("", self.include_audio)

        self.layout.addLayout(form_layout, 1, 0)

    @staticmethod
    def _get_initial_directory(current_path: str, fallback_folder: str) -> str:
        if current_path:
            path = Path(current_path)
            parent = path.parent if path.suffix else path
            if parent.exists():
                return str(parent)
        user_folder = Path.home() / fallback_folder
        if user_folder.exists():
            return str(user_folder)
        return str(Path.home())

    def _on_audio_file_button_clicked(self):
        initial_dir = self._get_initial_directory(self.audio_file_path.text(), "Music")
        self.audio_file_dialog.setDirectory(initial_dir)
        self.audio_file_dialog.open()

    def _on_video_file_button_clicked(self):
        initial_dir = self._get_initial_directory(self.video_file_path.text(), "Videos")
        self.video_file_dialog.setDirectory(initial_dir)
        self.video_file_dialog.open()

    '''
    Verifies that the input values in the view are valide.
    '''
    def validate_view(self) -> bool:
        self.last_error = ""
        try:
            video_width = int(self.video_width.text())
            video_height = int(self.video_height.text())
            fps = int(self.visualizer_fps.text())
        except:
            self.last_error = "Video width, height, and FPS must be numbers."
            return False
        
        if video_width < 1 or video_height < 1 or fps < 1:
            self.last_error = "Video width, height, and FPS must be greater than zero."
            return False

        codec = self.codec.currentText().strip()
        if not codec:
            self.last_error = "Video codec is required."
            return False

        if not os.path.isfile(self.audio_file_path.text()):
            self.last_error = "Audio file path does not exist."
            return False

        bitrate_text = self.bitrate.text().strip()
        if bitrate_text:
            try:
                bitrate = int(bitrate_text)
            except:
                self.last_error = "Video bitrate must be a number."
                return False
            if bitrate < 1:
                self.last_error = "Video bitrate must be greater than zero."
                return False

        crf_text = self.crf.text().strip()
        if crf_text:
            try:
                crf = int(crf_text)
            except:
                self.last_error = "CRF must be a number."
                return False
            if crf < 0 or crf > 51:
                self.last_error = "CRF must be between 0 and 51."
                return False
        
        ext = os.path.splitext(self.video_file_path.text())[1]
        if ext == '':
            self.video_file_path.setText(self.video_file_path.text() + ".mp4")
        elif not ext == ".mp4":
            self.last_error = "Output video file must end with .mp4."
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
        settings.codec = self.codec.currentText().strip()

        bitrate_text = self.bitrate.text().strip()
        settings.bitrate = int(bitrate_text) if bitrate_text else None

        crf_text = self.crf.text().strip()
        settings.crf = int(crf_text) if crf_text else None

        settings.hardware_accel = self.hardware_accel.isChecked()
        settings.include_audio = self.include_audio.isChecked()

        settings.audio_file_path = self.audio_file_path.text()
        settings.video_file_path = self.video_file_path.text()

        return settings




