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

import numpy as np
from PIL import Image, ImageDraw

from visualizers import Visualizer
from visualizers.utilities import AudioData, VideoData, VisualizerAlignment

class WaveformVisualizer(Visualizer):
    '''
    line_thickness: Thickness of the waveform line.
    alignment: 'bottom', or 'center' to align the waveform accordingly.
    '''
    def __init__(self, audio_data: AudioData, video_data: VideoData, x, y,
                 line_thickness = 2, super_sampling = 1,
                 color = (255, 255, 255), alignment = VisualizerAlignment.CENTER):
        super().__init__(audio_data, video_data, x, y, super_sampling)

        self.line_thickness = max(1, line_thickness) * self.super_sampling
        self.color = color
        self.alignment = alignment
        self.waveform_img = None

    def prepare_shapes(self):
        width = self.video_data.video_width * self.super_sampling
        height = self.video_data.video_height * self.super_sampling
        img = Image.new("RGB", (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        if not self.audio_data.audio_frames:
            self.waveform_img = img.resize((self.video_data.video_width, self.video_data.video_height),
                                           resample=Image.Resampling.LANCZOS) if self.super_sampling > 1 else img
            return

        amplitudes = [float(np.max(np.abs(frame))) for frame in self.audio_data.audio_frames]
        max_amp = max(amplitudes) if amplitudes else 0.0
        if max_amp <= 0:
            max_amp = 1.0

        draw_width = max(1, width - self.x)
        frames = len(amplitudes)
        for i in range(draw_width):
            idx = int(i / draw_width * frames)
            amp = amplitudes[idx] / max_amp
            x = self.x + i

            if self.alignment == VisualizerAlignment.CENTER:
                max_extent = min(self.y, height - self.y - 1)
                extent = int(max_extent * amp)
                y1 = self.y - extent
                y2 = self.y + extent
            else:
                max_extent = min(self.y, height - 1)
                extent = int(max_extent * amp)
                y1 = self.y - extent
                y2 = self.y

            draw.line([(x, y1), (x, y2)], fill=self.color, width=self.line_thickness)

        if self.super_sampling > 1:
            img = img.resize((self.video_data.video_width, self.video_data.video_height),
                             resample=Image.Resampling.LANCZOS)
        self.waveform_img = img

    def generate_frame(self, frame_index: int):
        return np.asarray(self.waveform_img)
