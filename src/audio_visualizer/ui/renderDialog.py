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
    QUrl, QSize, Qt
)

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QLabel, QSlider
)

from PySide6.QtMultimediaWidgets import (
    QVideoWidget
)

from PySide6.QtMultimedia import (
    QMediaPlayer, QAudioOutput
)

from audio_visualizer.visualizers.utilities import VideoData

class RenderDialog(QDialog):
    _last_volume = 100

    def __init__(self, video_data: VideoData):
        super().__init__()

        self.video_data = video_data
        self.setWindowTitle("Viewing Render")

        layout = QVBoxLayout()
        
        self.video = QMediaPlayer(source=QUrl.fromLocalFile(video_data.file_path),
                                    loops=QMediaPlayer.Loops.Infinite)
        self.video.mediaStatusChanged.connect(self._media_status)

        self.video_widget = QVideoWidget()
        self.video.setVideoOutput(self.video_widget)
        self.audio_output = QAudioOutput()
        self.video.setAudioOutput(self.audio_output)
        layout.addWidget(self.video_widget)

        volume_row = QHBoxLayout()
        volume_label = QLabel("Volume")
        volume_row.addWidget(volume_label)
        self.volume_slider = QSlider()
        self.volume_slider.setOrientation(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(RenderDialog._last_volume)
        self.audio_output.setVolume(RenderDialog._last_volume / 100)
        self.volume_slider.valueChanged.connect(self._volume_changed)
        volume_row.addWidget(self.volume_slider)
        layout.addLayout(volume_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)
    
    def _media_status(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            self.video_widget.setMaximumSize(QSize(self.video_data.video_width, self.video_data.video_height))
            self.adjustSize()
            self.video.play()

    def _cleanup_player(self):
        try:
            self.video.stop()
        except Exception:
            pass
        try:
            self.video.setSource(QUrl())
        except Exception:
            pass
        try:
            self.video.setVideoOutput(None)
        except Exception:
            pass
        try:
            self.video.setAudioOutput(None)
        except Exception:
            pass

    def _volume_changed(self, value: int):
        RenderDialog._last_volume = value
        self.audio_output.setVolume(value / 100)

    def reject(self):
        self._cleanup_player()
        super().reject()

    def closeEvent(self, event):
        self._cleanup_player()
        event.accept()

