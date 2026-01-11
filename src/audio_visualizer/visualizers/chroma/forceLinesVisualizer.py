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
    VideoData, AudioData, VisualizerAlignment
)

class ForceLinesVisualizer(Visualizer):
    '''
    Multiple force-driven rope lines, one per chroma band.
    '''
    def __init__(self, audio_data: AudioData, video_data: VideoData, x, y,
                 line_thickness=2, points_count=80, super_sampling=1,
                 color=(255, 255, 255), alignment=VisualizerAlignment.BOTTOM,
                 tension=0.08, damping=0.02, force_strength=1.0, gravity=0.02,
                 smoothness=6, band_spacing=6, band_colors=None):
        super().__init__(audio_data, video_data, x, y, super_sampling)

        self.line_thickness = max(1, int(line_thickness * self.super_sampling))
        self.points_count = max(3, int(points_count))
        self.color = color
        self.alignment = alignment
        self.tension = tension
        self.damping = damping
        self.force_strength = force_strength
        self.gravity = gravity
        self.smoothness = max(2, int(smoothness))
        self.band_spacing = band_spacing * self.super_sampling
        self.segments = 12
        self.band_colors = band_colors or []

    def prepare_shapes(self):
        width = self.video_data.video_width * self.super_sampling
        if self.points_count < 2:
            self.points_count = 2
        step = width / (self.points_count - 1)
        self.x_positions = [self.x + i * step for i in range(self.points_count)]
        self.offsets = [[0.0 for _ in range(self.points_count)] for _ in range(self.segments)]
        self.velocities = [[0.0 for _ in range(self.points_count)] for _ in range(self.segments)]
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
            offsets = self.offsets[band]
            velocities = self.velocities[band]
            force = chroma[band] * self.force_strength
            for i in range(self.points_count):
                left = offsets[i - 1] if i > 0 else offsets[i]
                right = offsets[i + 1] if i < self.points_count - 1 else offsets[i]
                accel = self.tension * (left + right - 2 * offsets[i])
                accel -= self.damping * velocities[i]
                accel -= self.gravity * offsets[i]
                if i == 0:
                    accel += force
                velocities[i] += accel
                offsets[i] += velocities[i]

            points = []
            y_offset = band * self.band_spacing
            for x_pos, offset in zip(self.x_positions, offsets):
                if self.alignment == VisualizerAlignment.CENTER:
                    y_pos = (self.y + y_offset) - offset
                else:
                    y_pos = (self.y + y_offset) - offset
                points.append((x_pos, y_pos))

            smooth_points = self._catmull_rom(points, self.smoothness)
            if len(smooth_points) >= 2:
                color = self.colors[band] if band < len(self.colors) else self.color
                draw.line(smooth_points, fill=color, width=self.line_thickness)

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
