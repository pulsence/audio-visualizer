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

class RectangleVisualizer(Visualizer):
    '''
    number_of_boxes: If set to -1, it will calculate the number of boxes based on the video width,
    box width, and box spacing.
    corner_radius: Radius of the rectangle corners.
    corners: Tuple of booleans indicating which corners should be rounded (top-left, top-right, bottom-right, bottom-left).
    alignment: 'bottom', or 'center' to align the rectangles accordingly.
    flow: 'sideways' or 'center' to determine how the sound visualization flows.
    super_sampling: When value is greater than 1 supersampling anti-aliasing is applied.
    '''
    def __init__(self, audio_data: AudioData, video_data: VideoData, x, y,
                 box_height = 50, box_width = 10, border_width = 1, 
                 spacing = 5, super_sampling = 1, number_of_boxes = -1, 
                 corner_radius = 0, corners = (True, True, True, True),
                 bg_color = (255, 255, 255), border_color = (255, 255, 255),
                 alignment = VisualizerAlignment.BOTTOM, flow = VisualizerFlow.LEFT_TO_RIGHT):
        super().__init__(audio_data, video_data, x, y, super_sampling)

        self.box_width = box_width * self.super_sampling
        self.border_width = border_width * self.super_sampling
        self.box_height = box_height * self.super_sampling
        self.spacing = spacing * self.super_sampling
        self.corner_radius = corner_radius * self.super_sampling
        self.corners = corners

        self.bg_color = bg_color
        self.border_color = border_color

        if number_of_boxes != -1:
            self.number_of_boxes = number_of_boxes
        else:
            self.number_of_boxes = video_data.video_width * self.super_sampling // (self.box_width + self.spacing)

        self.alignment = alignment
        self.flow = flow

        if flow == VisualizerFlow.OUT_FROM_CENTER:
            if alignment == VisualizerAlignment.CENTER:
                self.generate_frame = self._draw_center_aligned_center_flow
            else:
                self.generate_frame = self._draw_bottom_aligned_center_flow
        else:
            if alignment == VisualizerAlignment.CENTER:
                self.generate_frame = self._draw_center_aligned_side_flow
            else:
                self.generate_frame = self._draw_bottom_aligned_side_flow

    def prepare_shapes(self):
        self.rectangles = []
        for i in range(self.number_of_boxes):
            x1 = self.x + i * (self.box_width + self.spacing)
            x2 = x1 + self.box_width
            y1 = self.y - self.border_width
            y2 = self.y 
            if x2 + self.border_width >= self.video_data.video_width * self.super_sampling:
                break
            self.rectangles.append([x1, y1, x2, y2])

        if self.flow == VisualizerFlow.OUT_FROM_CENTER and len(self.rectangles) % 2 == 0:
            self.rectangles.pop()  # Remove the last rectangle to keep it odd for centering
            self.center_index = len(self.rectangles) // 2
        self.number_of_boxes = len(self.rectangles)

    '''
    Draws rectangles aligned to the bottom and flowing from the center outwards.
    '''
    def _draw_bottom_aligned_center_flow(self, frame_index):
        img = Image.new("RGB", (self.video_data.video_width * self.super_sampling, self.video_data.video_height * self.super_sampling), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        for i in range(self.number_of_boxes // 2):
            self.rectangles[i][1] = self.rectangles[i+1][1]
            self.rectangles[self.number_of_boxes - i - 1][1] = self.rectangles[self.number_of_boxes - i - 2][1]
        volume = self.audio_data.average_volumes[frame_index]
        self.rectangles[self.center_index][1] = self.y - int(self.box_height * (volume / self.audio_data.max_volume))

        for rect in self.rectangles:
            draw.rounded_rectangle(rect, self.corner_radius,
                                   fill=self.bg_color, outline=self.border_color,
                                   width=self.border_width,
                                   corners=(True, True, True, True))
            
        if self.super_sampling > 1:
            img = img.resize((self.video_data.video_width, self.video_data.video_height),
                        resample=Image.Resampling.LANCZOS)
        
        return np.asarray(img)
    
    '''
    Draws rectangles aligned to the bottom and flowing from the left side to the other.
    '''
    def _draw_bottom_aligned_side_flow(self, frame_index):
        img = Image.new("RGB", (self.video_data.video_width * self.super_sampling, self.video_data.video_height * self.super_sampling), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        for i in range(self.number_of_boxes - 1):
            self.rectangles[self.number_of_boxes - i - 1][1] = self.rectangles[self.number_of_boxes - i - 2][1]
        volume = self.audio_data.average_volumes[frame_index]
        self.rectangles[0][1] = self.y - int(self.box_height * (volume / self.audio_data.max_volume))

        for rect in self.rectangles:
            draw.rounded_rectangle(rect, self.corner_radius,
                                   fill=self.bg_color, outline=self.border_color,
                                   width=self.border_width,
                                   corners=(True, True, True, True))
        
        if self.super_sampling > 1:
            img = img.resize((self.video_data.video_width, self.video_data.video_height),
                        resample=Image.Resampling.LANCZOS)
        
        return np.asarray(img)

    '''
    Draws rectangles centered vertically and flowing from the left side to the other.
    '''
    def _draw_center_aligned_side_flow(self, frame_index):
        img = Image.new("RGB", (self.video_data.video_width * self.super_sampling, self.video_data.video_height * self.super_sampling), (0, 0, 0))
        draw = ImageDraw.Draw(img)


        for i in range(self.number_of_boxes - 1):
            self.rectangles[self.number_of_boxes - i - 1][1] = self.rectangles[self.number_of_boxes - i - 2][1]
            self.rectangles[self.number_of_boxes - i - 1][3] = self.rectangles[self.number_of_boxes - i - 2][3]
        volume = self.audio_data.average_volumes[frame_index]
        offset = int(self.box_height * (volume / self.audio_data.max_volume)) // 2
        self.rectangles[0][1] = self.y - offset
        self.rectangles[0][3] = self.y + offset

        for rect in self.rectangles:
            draw.rounded_rectangle(rect, self.corner_radius,
                                   fill=self.bg_color, outline=self.border_color,
                                   width=self.border_width,
                                   corners=(True, True, True, True))
            
        if self.super_sampling > 1:
            img = img.resize((self.video_data.video_width, self.video_data.video_height),
                        resample=Image.Resampling.LANCZOS)
        
        return np.asarray(img)
    
    '''
    Draws rectangles centered vertically and flowing from the center outwards.
    '''
    def _draw_center_aligned_center_flow(self, frame_index):
        img = Image.new("RGB", (self.video_data.video_width * self.super_sampling, self.video_data.video_height * self.super_sampling), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        for i in range(self.number_of_boxes // 2):
            self.rectangles[i][1] = self.rectangles[i+1][1]
            self.rectangles[i][3] = self.rectangles[i+1][3]
            self.rectangles[self.number_of_boxes - i - 1][1] = self.rectangles[self.number_of_boxes - i - 2][1]
            self.rectangles[self.number_of_boxes - i - 1][3] = self.rectangles[self.number_of_boxes - i - 2][3]
        volume = self.audio_data.average_volumes[frame_index]
        offset = int(self.box_height * (volume / self.audio_data.max_volume)) // 2
        self.rectangles[self.center_index][1] = self.y - offset
        self.rectangles[self.center_index][3] = self.y + offset

        for rect in self.rectangles:
            draw.rounded_rectangle(rect, self.corner_radius,
                                   fill=self.bg_color, outline=self.border_color,
                                   width=self.border_width,
                                   corners=(True, True, True, True))
            
        if self.super_sampling > 1:
            img = img.resize((self.video_data.video_width, self.video_data.video_height),
                        resample=Image.Resampling.LANCZOS)
        
        return np.asarray(img)
    