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

from audio_visualizer.visualizers import Visualizer

from audio_visualizer.visualizers.utilities import (
    VideoData, AudioData, VisualizerAlignment,
    VisualizerFlow
)

class LineVisualizer(Visualizer):
    '''
    Smooth line visualizer that flows based on volume.
    '''
    def __init__(self, audio_data: AudioData, video_data: VideoData, x, y,
                 max_height=50, line_thickness=2, spacing=5, super_sampling=1,
                 color=(255, 255, 255), alignment=VisualizerAlignment.BOTTOM,
                 flow=VisualizerFlow.LEFT_TO_RIGHT, smoothness=8):
        super().__init__(audio_data, video_data, x, y, super_sampling)

        self.max_height = max_height * self.super_sampling
        self.line_thickness = max(1, int(line_thickness * self.super_sampling))
        self.spacing = max(1, int(spacing * self.super_sampling))
        self.color = color
        self.alignment = alignment
        self.flow = flow
        self.smoothness = max(2, smoothness)

    def prepare_shapes(self):
        self.x_positions = []
        max_width = self.video_data.video_width * self.super_sampling
        x_pos = self.x
        while x_pos <= max_width:
            self.x_positions.append(x_pos)
            x_pos += self.spacing

        if self.flow == VisualizerFlow.OUT_FROM_CENTER and len(self.x_positions) % 2 == 0:
            self.x_positions.pop()

        self.heights = [0 for _ in self.x_positions]
        if self.flow == VisualizerFlow.OUT_FROM_CENTER:
            self.center_index = len(self.heights) // 2

    def generate_frame(self, frame_index: int):
        img = Image.new(
            "RGB",
            (self.video_data.video_width * self.super_sampling, self.video_data.video_height * self.super_sampling),
            (0, 0, 0),
        )
        draw = ImageDraw.Draw(img)

        volume = self.audio_data.average_volumes[frame_index]
        denom = self.audio_data.max_volume if self.audio_data.max_volume > 0 else 1.0
        new_height = int(self.max_height * (volume / denom))

        if self.flow == VisualizerFlow.OUT_FROM_CENTER:
            for i in range(self.center_index):
                self.heights[i] = self.heights[i + 1]
                self.heights[-i - 1] = self.heights[-i - 2]
            self.heights[self.center_index] = new_height
        else:
            for i in range(len(self.heights) - 1, 0, -1):
                self.heights[i] = self.heights[i - 1]
            self.heights[0] = new_height

        points = []
        for x_pos, height in zip(self.x_positions, self.heights):
            if self.alignment == VisualizerAlignment.CENTER:
                y_pos = self.y - int(height / 2)
            else:
                y_pos = self.y - height
            points.append((x_pos, y_pos))

        smooth_points = self._catmull_rom(points, self.smoothness)
        if len(smooth_points) >= 2:
            draw.line(smooth_points, fill=self.color, width=self.line_thickness)

        if self.super_sampling > 1:
            img = img.resize(
                (self.video_data.video_width, self.video_data.video_height),
                resample=Image.Resampling.LANCZOS,
            )
        return np.asarray(img)

    @staticmethod
    def _catmull_rom(points, samples_per_segment):
        if len(points) < 2:
            return points
        result = []
        for i in range(len(points) - 1):
            p0 = points[i - 1] if i - 1 >= 0 else points[i]
            p1 = points[i]
            p2 = points[i + 1]
            p3 = points[i + 2] if i + 2 < len(points) else points[i + 1]
            for j in range(samples_per_segment):
                t = j / samples_per_segment
                t2 = t * t
                t3 = t2 * t
                x = 0.5 * (
                    (2 * p1[0]) +
                    (-p0[0] + p2[0]) * t +
                    (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
                    (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
                )
                y = 0.5 * (
                    (2 * p1[1]) +
                    (-p0[1] + p2[1]) * t +
                    (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                    (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
                )
                result.append((x, y))
        result.append(points[-1])
        return result
