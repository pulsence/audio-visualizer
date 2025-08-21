import av

from utilities import AudioData, VideoData, Generator
from VolumeShape import RectangleVisualizer, CircleVisualizer

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from ui import MainWindow


def main():
    show_ui()

    fps = 16
    video_width = 480
    video_height = 320

    audio_data = AudioData("sample_audio.mp3")
    audio_data.load_audio_data()
    audio_data.chunk_audio(fps)
    audio_data.analyze_volume()

    video_data = VideoData(video_width, video_height, fps)
    rectangle_visualizer = RectangleVisualizer(audio_data, video_data, 0, video_height - 150, 
                                               box_height = 100, corner_radius = 10,
                                               bg_color = (227, 209, 169), border_color = (227, 209, 169),
                                               alignment = 'center', flow = 'center')

    circle_visualizer = CircleVisualizer(audio_data, video_data, 0, video_height - 150,
                                         max_radius = 20, border_width = 4, spacing = 8, 
                                         bg_color = (227, 209, 169), border_color = (227, 209, 169),
                                         alignment = 'center', flow = 'center')

    preview = False
    #generateVideo(audio_data, video_data, rectangle_visualizer, preview=preview)

    if preview: 
        from os import startfile
        startfile(video_data.file_path)

def show_ui():
    app = QApplication([])
    main_window = MainWindow()
    main_window.show()
    app.exec()

def generateVideo(audio_data: AudioData, video_data: VideoData, generator: Generator, preview=False):
    video_data.prepare_container()
    generator.prepare_shapes()

    ''' If preview is True, limit to 30 seconds of video. '''
    max_frames = min(len(audio_data.audio_frames), video_data.fps * 30 if preview else len(audio_data.audio_frames))

    for i in range(len(audio_data.audio_frames)):
        if i > max_frames:
            break
        img = generator.draw_frame(i)
        frame = av.VideoFrame.from_ndarray(img, format="rgb24")
        for packet in video_data.stream.encode(frame):
            video_data.container.mux(packet)
    
    video_data.finalize()

if __name__=="__main__":
    main()