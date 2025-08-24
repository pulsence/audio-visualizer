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

from visualizers.utilities import (
    VideoData, AudioData, VisualizerAlignment,
    VisualizerFlow, VisualizerOptions
)

class CircleVisualizer(Visualizer):
    '''
    number_of_cirlces: If set to -1, it will calculate the number of circles based on the video width,
    max radius, and spacing.
    corners: Tuple of booleans indicating which corners should be rounded (top-left, top-right, bottom-right, bottom-left).
    alignment: 'bottom', or 'center' to align the rectangles accordingly.
    super_sampling: When value is greater than 1 supersampling anti-aliasing is applied.
    '''
    def __init__(self, audio_data: AudioData, video_data: VideoData, x, y, border_width = 1, 
                 super_sampling = 1, spacing = 5,
                 bg_color = (255, 255, 255), border_color = (255, 255, 255),
                 alignment = VisualizerAlignment.BOTTOM):
        super().__init__(audio_data, video_data, x, y, super_sampling)

        self.border_width = border_width * self.super_sampling
        self.spacing = spacing * self.super_sampling

        maxVRadius = (video_data.video_height - border_width * 2) * super_sampling // 2
        maxHRadius = ((video_data.video_width - (self.spacing - self.border_width) * 12) * self.super_sampling // 24) 
        self.max_radius = min(maxVRadius, maxHRadius)
        self.max_diameter = self.max_radius * 2

        self.bg_color = bg_color
        self.border_color = border_color

        self. number_of_cirles = 12

        if alignment == VisualizerAlignment.CENTER:
            self.generate_frame = self._draw_center_aligned_side_flow
        else:
            self.generate_frame = self._draw_bottom_aligned_side_flow

    def prepare_shapes(self):
        self.circles = []
        for i in range(self.number_of_cirles):
            x1 = self.x + i * (self.max_diameter + self.spacing)
            x2 = x1 + self.max_radius
            y1 = self.y - self.border_width
            y2 = self.y 

            # The last value is the x of center since y is fixed
            self.circles.append([x1, y1, x2, y2, x2]) 

    '''
    Draws circles aligned to the bottom and flowing from the left side to the other.
    '''
    def _draw_bottom_aligned_side_flow(self, frame_index):
        img = Image.new("RGB", (self.video_data.video_width * self.super_sampling, self.video_data.video_height * self.super_sampling), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        for i in range(self.number_of_cirles):
            r = self.max_radius * self.audio_data.chromagrams[frame_index][i]
            
            self.circles[i][0] = self.circles[i][4] - r
            self.circles[i][1] = self.y - r * 2
            self.circles[i][2] = self.circles[i][4] + r
            self.circles[i][3] = self.y

        for circle in self.circles:
            draw.ellipse(circle[:4],
                         fill=self.bg_color, outline=self.border_color,
                         width=self.border_width)
            
        if self.super_sampling > 1:
            img = img.resize((self.video_data.video_width, self.video_data.video_height),
                        resample=Image.Resampling.LANCZOS)
        
        return np.asarray(img)

    '''
    Draws circles centered vertically and flowing from the left side to the other.
    '''
    def _draw_center_aligned_side_flow(self, frame_index):
        img = Image.new("RGB", (self.video_data.video_width * self.super_sampling, self.video_data.video_height * self.super_sampling), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        for i in range(self.number_of_cirles):
            r = self.max_radius * self.audio_data.chromagrams[frame_index][i]
            
            self.circles[i][0] = self.circles[i][4] - r
            self.circles[i][1] = self.y - r
            self.circles[i][2] = self.circles[i][4] + r
            self.circles[i][3] = self.y + r

        for circle in self.circles:
            draw.ellipse(circle[:4],
                         fill=self.bg_color, outline=self.border_color,
                         width=self.border_width)
            
        if self.super_sampling > 1:
            img = img.resize((self.video_data.video_width, self.video_data.video_height),
                        resample=Image.Resampling.LANCZOS)
        
        return np.asarray(img)