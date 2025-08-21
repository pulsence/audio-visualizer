'''
Visualizer Shape:
1. Spikes
2. Rounded corner rectangles
3. Balls
4. Shapes based on frequency bands

Video Settings:
1. Allow user config
2. Choose to include audio

General Improvements:
1. Look into multithreading for audio processing and video generation


Dependencies:
- av
- numpy
- librosa
- matplotlib
- PIL (Pillow)
'''
import av

from utilities import AudioData, VideoData, Generator
from VolumeShape import RectangleVisualizer, CircleVisualizer


def main():
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
    video_data.prepare_container()
    generateVideo(audio_data, video_data, rectangle_visualizer, preview=preview)
    video_data.finalize()

    if preview: 
        from os import startfile
        startfile(video_data.file_path)
    
def generateVideo(audio_data: AudioData, video_data: VideoData, generator: Generator, preview=False):
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
    

if __name__=="__main__":
    main()