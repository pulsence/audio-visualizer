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


Parent Class for different visualizer generators.
'''

from PySide6.QtWidgets import (
    QWidget
)

from .utilities import AudioData, VideoData

class Visualizer:
    
    def __init__(self, audio_data: AudioData, video_data: VideoData, x, y, super_sampling):
        self.audio_data = audio_data
        self.video_data = video_data
        self.super_sampling = super_sampling
        self.x = x * self.super_sampling 
        self.y = y * self.super_sampling 

   
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
