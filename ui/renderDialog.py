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

class RenderDialog(QDialog):
    def __init__(self, render_path):
        super().__init__()

        self.setWindowTitle("Viewing Render")

        layout = QVBoxLayout()
        
        self.video = QMediaPlayer(source=QUrl.fromLocalFile(render_path),
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
            self.video_widget.setMaximumSize(QSize(480, 360))
            self.adjustSize()
            self.video.play()