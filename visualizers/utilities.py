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


Utility functions
'''
import librosa
import numpy as np

import av

from enum import Enum

class VisualizerFlow(Enum):
    LEFT_TO_RIGHT = "Left to Right"
    OUT_FROM_CENTER = "Out from Center"

    @staticmethod
    def list():
        return list(map(lambda v: v.value, VisualizerFlow))

class VisualizerAlignment(Enum):
    BOTTOM = "Bottom"
    CENTER = "Center"

    @staticmethod
    def list():
        return list(map(lambda v: v.value, VisualizerAlignment))

class VisualizerOptions(Enum):
    VOLUME_RECTANGLE = "Volume: Rectangle"
    VOLUME_CIRCLE = "Volume: Circle"
    CHROMA_RECTANGLE = "Chroma: Rectangle"
    CHROMA_CIRCLE = "Chroma: Circle"

    @staticmethod
    def list():
        return list(map(lambda v: v.value, VisualizerOptions))

class AudioData:
    def __init__(self, file_path):
        self.file_path = file_path

        self.audio_samples = None
        self.sample_rate = None

        self.audio_frames = []

        self.average_volumes = []
        self.max_volume = float('-inf')
        self.min_volume = float('inf')

        self.chromagrams = []

    '''
    Loads the audio data from the set file path.
    Returns True if successful, False otherwise.
    '''
    def load_audio_data(self, preview=False):
        try:
            if not preview:
                self.audio_samples, self.sample_rate = librosa.load(self.file_path)
            else:
                self.audio_samples, self.sample_rate = librosa.load(self.file_path, duration=30)
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

    def analyze_audio(self):
        for frame in self.audio_frames:
            avg_volume = np.mean(np.abs(frame))
            self.average_volumes.append(avg_volume)
            self.max_volume = max(self.max_volume, avg_volume)
            self.min_volume = min(self.min_volume, avg_volume)

            raw_chromagram = librosa.feature.chroma_stft(y=frame, sr=self.sample_rate)
            chromagram = []
            for row in raw_chromagram:
                chromagram.append(np.mean(row))
            self.chromagrams.append(chromagram)

class VideoData:
    def __init__(self, video_width, video_height, fps, file_path="output.mp4"):
        self.video_width = video_width
        self.video_height = video_height
        self.fps = fps
        self.file_path = file_path

    def prepare_container(self):
        try:
            self.container = av.open(self.file_path, mode='w')
        except:
            return False
        self.stream = self.container.add_stream('h264', rate=self.fps)
        self.stream.width = self.video_width
        self.stream.height = self.video_height
        self.stream.pix_fmt = 'yuv420p'
        return True

    def finalize(self):
        for packet in self.stream.encode():
            self.container.mux(packet)
        try:
            self.container.close()
        except:
            return False
        return True