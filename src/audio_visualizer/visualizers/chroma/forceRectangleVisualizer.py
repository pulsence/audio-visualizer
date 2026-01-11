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

class ForceRectangleVisualizer(Visualizer):
    '''
    Chroma rectangles with force-driven inflation and gravity.
    '''
    def __init__(self, audio_data, video_data: VideoData, x, y,
                 box_height=50, border_width=1,
                 spacing=5, super_sampling=1,
                 corner_radius=0, corners=(True, True, True, True),
                 bg_color=(255, 255, 255), border_color=(255, 255, 255),
                 alignment=VisualizerAlignment.BOTTOM,
                 color_mode="Single", gradient_start=None, gradient_end=None, band_colors=None,
                 gravity=0.05, force_strength=1.0):
        super().__init__(audio_data, video_data, x, y, super_sampling)

        self.border_width = border_width * self.super_sampling
        self.box_height = box_height * self.super_sampling
        self.spacing = spacing * self.super_sampling
        self.box_width = (video_data.video_width - (self.spacing - self.border_width) * 12) * self.super_sampling // 12
        self.corner_radius = corner_radius * self.super_sampling
        self.corners = corners

        self.bg_color = bg_color
        self.border_color = border_color
        self.color_mode = color_mode
        self.gradient_start = gradient_start
        self.gradient_end = gradient_end
        self.band_colors = band_colors or []

        self.number_of_boxes = 12
        self.alignment = alignment
        self.gravity = gravity
        self.force_strength = force_strength
        self.heights = [0.0 for _ in range(self.number_of_boxes)]
        self.velocities = [0.0 for _ in range(self.number_of_boxes)]

    def prepare_shapes(self):
        self.rectangles = []
        for i in range(self.number_of_boxes):
            x1 = self.x + i * (self.box_width + self.spacing)
            x2 = x1 + self.box_width
            y1 = self.y - self.border_width
            y2 = self.y
            self.rectangles.append([x1, y1, x2, y2])

        self.colors = []
        if self.color_mode == "Per-band" and len(self.band_colors) == self.number_of_boxes:
            self.colors = self.band_colors
        elif self.color_mode == "Gradient" and self.gradient_start and self.gradient_end:
            self.colors = self._build_gradient(self.gradient_start, self.gradient_end, self.number_of_boxes)
        else:
            self.colors = [self.bg_color for _ in range(self.number_of_boxes)]

    def generate_frame(self, frame_index):
        img = Image.new("RGB", (self.video_data.video_width * self.super_sampling, self.video_data.video_height * self.super_sampling), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        chroma = self.audio_data.chromagrams[frame_index]
        for i in range(self.number_of_boxes):
            force = chroma[i] * self.box_height * self.force_strength
            accel = force - (self.gravity * self.heights[i])
            self.velocities[i] += accel
            self.heights[i] += self.velocities[i]
            if self.heights[i] < 0:
                self.heights[i] = 0
                self.velocities[i] = 0
            if self.heights[i] > self.box_height:
                self.heights[i] = self.box_height
                self.velocities[i] = 0

            if self.alignment == VisualizerAlignment.CENTER:
                offset = int(self.heights[i] / 2)
                self.rectangles[i][1] = self.y - offset
                self.rectangles[i][3] = self.y + offset
            else:
                self.rectangles[i][1] = self.y - int(self.heights[i])
                self.rectangles[i][3] = self.y

        for i, rect in enumerate(self.rectangles):
            draw.rounded_rectangle(rect, self.corner_radius,
                                   fill=self.colors[i], outline=self.border_color,
                                   width=self.border_width,
                                   corners=self.corners)

        if self.super_sampling > 1:
            img = img.resize((self.video_data.video_width, self.video_data.video_height),
                        resample=Image.Resampling.LANCZOS)

        return np.asarray(img)

    @staticmethod
    def _build_gradient(start, end, steps):
        if steps <= 1:
            return [start]
        colors = []
        for i in range(steps):
            t = i / (steps - 1)
            r = int(start[0] + (end[0] - start[0]) * t)
            g = int(start[1] + (end[1] - start[1]) * t)
            b = int(start[2] + (end[2] - start[2]) * t)
            colors.append((r, g, b))
        return colors
