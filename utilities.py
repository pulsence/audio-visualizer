'''
Parent Class for different visualizer generators.
'''
import librosa
import numpy as np

import av

class AudioData:
    def __init__(self, file_path):
        self.file_path = file_path

        self.audio_samples = None
        self.sample_rate = None

        self.audio_frames = []

        self.average_volumes = []
        self.max_volume = float('-inf')
        self.min_volume = float('inf')

    '''
    Loads the audio data from the set file path.
    Returns True if successful, False otherwise.
    '''
    def load_audio_data(self):
        try:
            self.audio_samples, self.sample_rate = librosa.load(self.file_path)
        except:
            return False
        return True
    
    '''
    Chunks the audio data into frames based on the specified frames per second (fps).
    Each frame contains a number of samples equal to the sample rate divided by fps.
    '''
    def chunk_audio(self, fps):
        samples_per_frame = self.sample_rate // fps
        frames = self.audio_samples.size // samples_per_frame
        for i in range(frames):
            start = i * samples_per_frame
            end = start + samples_per_frame
            self.audio_frames.append(self.audio_samples[start:end])

    def analyze_volume(self):
        for frame in self.audio_frames:
            avg_volume = np.mean(np.abs(frame))
            self.average_volumes.append(avg_volume)
            self.max_volume = max(self.max_volume, avg_volume)
            self.min_volume = min(self.min_volume, avg_volume)

class VideoData:
    def __init__(self, video_width, video_height, fps, file_path="output.mp4"):
        self.video_width = video_width
        self.video_height = video_height
        self.fps = fps
        self.file_path = file_path

    def prepare_container(self):
        self.container = av.open(self.file_path, mode='w')
        self.stream = self.container.add_stream('h264', rate=self.fps)
        self.stream.width = self.video_width
        self.stream.height = self.video_height
        self.stream.pix_fmt = 'yuv420p'

    def finalize(self):
        for packet in self.stream.encode():
            self.container.mux(packet)
        self.container.close()

class Generator:
    
    def __init__(self, audio_data, video_data, x, y):
        self.audio_data = audio_data
        self.video_data = video_data
        self.x = x
        self.y = y

    '''
    Prepares the shapes for the visualizer.
    This method should be implemented by subclasses to define how shapes are prepared.
    '''
    def prepare_shapes(self):
        raise NotImplementedError("Subclasses should implement this method.")

    '''
    Generates a single frame of the video for a specific audio frame.
    This method should be implemented by subclasses to define how each frame is generated.
    '''
    def generate_frame(self, frame_index: int):
        raise NotImplementedError("Subclasses should implement this method.")
