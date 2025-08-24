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
    QUrl, QSize
)

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QVBoxLayout
)

from PySide6.QtMultimediaWidgets import (
    QVideoWidget
)

from PySide6.QtMultimedia import (
    QMediaPlayer
)

from visualizers.utilities import VideoData

class RenderDialog(QDialog):
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
        layout.addWidget(self.video_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)
    
    def _media_status(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            self.video_widget.setMaximumSize(QSize(self.video_data.video_width, self.video_data.video_height))
            self.adjustSize()
            self.video.play()