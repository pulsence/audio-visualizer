from PySide6.QtCore import (
    Qt, QRunnable, QThreadPool, QObject, Signal
)
from PySide6.QtWidgets import (
    QMainWindow, QGridLayout, QFormLayout, QHBoxLayout,
    QWidget, QComboBox, QLabel, QLineEdit, QPushButton, QCheckBox,
    QFileDialog, QColorDialog
)
from PySide6.QtGui import QIntValidator


from utilities import AudioData, VideoData
from VolumeShape import RectangleVisualizer, CircleVisualizer
from ui.renderDialog import RenderDialog

import av

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Visualizer")
        self.setGeometry(100, 100, 600, 400)
        
        self.label = QLabel("Welcome to the Audio Visualizer!")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.adjustSize()

        primary_layout = QGridLayout()
        primary_layout.addWidget(self.label, 0, 0)

        visualizer_settings_layout = QFormLayout()

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
        visualizer_settings_layout.addRow("Audio File Path:", audio_file_row)

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
        visualizer_settings_layout.addRow("Output Video File Path:", video_file_row)

        self.visualizer_fps = QLineEdit("16")
        self.visualizer_fps.setValidator(QIntValidator(1, 60))
        visualizer_settings_layout.addRow("Visual Frames Per Second (FPS):", self.visualizer_fps)

        self.video_width = QLineEdit("480")
        self.video_width.setValidator(QIntValidator(1, 1920))
        visualizer_settings_layout.addRow("Video Width:", self.video_width)

        self.video_height = QLineEdit("320")
        self.video_height.setValidator(QIntValidator(1, 1080))
        visualizer_settings_layout.addRow("Video Height:", self.video_height)

        self.visualizer = QComboBox()
        self.visualizer.addItems(["Rectangle", "Circle"])
        visualizer_settings_layout.addRow("Visualizer Type:", self.visualizer)


        self.rectangle_visualizer_layout = QFormLayout()
        # Insert settings just for rectangles 

        
        self.circle_visualizer_layout = QFormLayout()
        # Insert settings just for circles


        self.visualizer_alignment = QComboBox()
        self.visualizer_alignment.addItems(["Bottom", "Center"])
        visualizer_settings_layout.addRow("Alignment:", self.visualizer_alignment)

        self.visualizer_flow = QComboBox()
        self.visualizer_flow.addItems(["Left to Right", "Center Outward"])
        visualizer_settings_layout.addRow("Flow:", self.visualizer_flow)

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
        visualizer_settings_layout.addRow("Background Color:", bg_row)

        self.visualizer_border_width = QLineEdit("4")
        self.visualizer_border_width.setValidator(QIntValidator(0, int(1e6)))
        visualizer_settings_layout.addRow("Border Width:", self.visualizer_border_width)

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
        visualizer_settings_layout.addRow("Border Color:", border_row)

        render_view_layout = QHBoxLayout()
        self.preview_checkbox = QCheckBox("Preview Video (30 seconds)")
        self.preview_checkbox.setChecked(True)
        render_view_layout.addWidget(self.preview_checkbox)

        self.show_output_checkbox = QCheckBox("Show Rendered Video")
        self.show_output_checkbox.setChecked(True)
        render_view_layout.addWidget(self.show_output_checkbox)

        visualizer_settings_layout.addRow(render_view_layout)

        self.render_button = QPushButton("Render Video")
        self.render_button.clicked.connect(self.render_video)
        visualizer_settings_layout.addRow(self.render_button)

        primary_layout.addLayout(visualizer_settings_layout, 1, 0)

        container = QWidget()
        container.setLayout(primary_layout)
        self.setCentralWidget(container)

        self.render_thread_pool = QThreadPool()
        self.render_thread_pool.setMaxThreadCount(1)
        self.rendering = False

    def render_video(self):
        if self.rendering:
            return
        
        self.rendering = True
        self.render_button.setText("Rendering...")
        self.render_button.setEnabled(False)

        audio_file_path = self.audio_file_path.text()
        video_file_path = self.video_file_path.text()
        preview = self.preview_checkbox.isChecked()

        video_width = int(self.video_width.text())
        video_height = int(self.video_height.text())
        fps = int(self.visualizer_fps.text())

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

        audio_data = AudioData(audio_file_path)
        video_data = VideoData(video_width, video_height, fps, file_path=video_file_path)

        visualizer = None
        if visualizer_type == "Rectangle":
            visualizer = RectangleVisualizer(
                audio_data, video_data, 0, video_height - 150,
                box_height=100, corner_radius=10,
                bg_color=bg_color, border_color=border_color,
                alignment=alignment, flow=flow
            )
        elif visualizer_type == "Circle":
            visualizer = CircleVisualizer(
                audio_data, video_data, 0, video_height - 150,
                max_radius=20, border_width=border_width, spacing=8,
                bg_color=bg_color, border_color=border_color,
                alignment=alignment, flow=flow
            )
        
        render_worker = RenderWorker(audio_data, video_data, visualizer, preview)
        render_worker.signals.finished.connect(self.render_finished)
        self.render_thread_pool.start(render_worker)
    
    def render_finished(self):
        self.rendering = False
        self.render_button.setEnabled(True)
        self.render_button.setText("Render Video")

        if self.show_output_checkbox.isChecked():
            player = RenderDialog(self.video_file_path.text())
            player.exec()

class RenderWorker(QRunnable):
    def __init__(self, audio_data, video_data, visualizer, preview):
        super().__init__()
        self.audio_data = audio_data
        self.video_data = video_data
        self.visualizer = visualizer
        self.preview = preview

        class RenderSignals(QObject):
            finished = Signal()
        self.signals = RenderSignals()

    def run(self):
        self.audio_data.load_audio_data()
        self.audio_data.chunk_audio(self.video_data.fps)
        self.audio_data.analyze_volume()


        self.video_data.prepare_container()
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
        
        self.video_data.finalize()
        self.signals.finished.emit()