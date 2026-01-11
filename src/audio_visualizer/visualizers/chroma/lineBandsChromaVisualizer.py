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
    VideoData, AudioData, VisualizerAlignment, VisualizerFlow
)

class LineBandsVisualizer(Visualizer):
    '''
    Per-band smooth line visualizer driven by chroma (12 bands).
    Each band has its own line and flows over time.
    '''
    def __init__(self, audio_data: AudioData, video_data: VideoData, x, y,
                 max_height=50, line_thickness=2, spacing=5, super_sampling=1,
                 color=(255, 255, 255), alignment=VisualizerAlignment.BOTTOM,
                 flow=VisualizerFlow.LEFT_TO_RIGHT, smoothness=8,
                 band_spacing=0, band_colors=None):
        super().__init__(audio_data, video_data, x, y, super_sampling)

        self.max_height = max_height * self.super_sampling
        self.line_thickness = max(1, int(line_thickness * self.super_sampling))
        self.spacing = max(1, int(spacing * self.super_sampling))
        self.color = color
        self.alignment = alignment
        self.flow = flow
        self.smoothness = max(2, smoothness)
        self.segments = 12
        self.band_colors = band_colors or []
        self.band_spacing = band_spacing * self.super_sampling

    def prepare_shapes(self):
        self.x_positions = []
        max_width = self.video_data.video_width * self.super_sampling
        x_pos = self.x
        while x_pos <= max_width:
            self.x_positions.append(x_pos)
            x_pos += self.spacing

        if self.flow == VisualizerFlow.OUT_FROM_CENTER and len(self.x_positions) % 2 == 0:
            self.x_positions.pop()

        self.points_per_line = len(self.x_positions)
        self.lines = [[0 for _ in range(self.points_per_line)] for _ in range(self.segments)]
        if self.flow == VisualizerFlow.OUT_FROM_CENTER:
            self.center_index = self.points_per_line // 2
        self.colors = self._resolve_colors()

    def generate_frame(self, frame_index: int):
        img = Image.new(
            "RGB",
            (self.video_data.video_width * self.super_sampling, self.video_data.video_height * self.super_sampling),
            (0, 0, 0),
        )
        draw = ImageDraw.Draw(img)

        chroma = self.audio_data.chromagrams[frame_index]
        for band in range(self.segments):
            new_height = int(self.max_height * chroma[band])
            heights = self.lines[band]
            if self.flow == VisualizerFlow.OUT_FROM_CENTER:
                for i in range(self.center_index):
                    heights[i] = heights[i + 1]
                    heights[-i - 1] = heights[-i - 2]
                heights[self.center_index] = new_height
            else:
                for i in range(len(heights) - 1, 0, -1):
                    heights[i] = heights[i - 1]
                heights[0] = new_height

            points = []
            y_offset = band * self.band_spacing
            for x_pos, height in zip(self.x_positions, heights):
                if self.alignment == VisualizerAlignment.CENTER:
                    y_pos = (self.y + y_offset) - int(height / 2)
                else:
                    y_pos = (self.y + y_offset) - height
                points.append((x_pos, y_pos))

            segment_points = self._catmull_rom(points, self.smoothness)
            if len(segment_points) >= 2:
                color = self.colors[band] if band < len(self.colors) else self.color
                draw.line(segment_points, fill=color, width=self.line_thickness)

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
            for j in range(samples_per_segment + 1):
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
        return result

    def _resolve_colors(self):
        if len(self.band_colors) == self.segments:
            return self.band_colors
        return [self.color for _ in range(self.segments)]
