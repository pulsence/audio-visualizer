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

from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit
)

from PySide6.QtGui import (
    QIntValidator
)

from .. import Visualizer, VisualizerView


class CircleVisualizer(Visualizer):
    '''
    number_of_cirlces: If set to -1, it will calculate the number of circles based on the video width,
    max radius, and spacing.
    corners: Tuple of booleans indicating which corners should be rounded (top-left, top-right, bottom-right, bottom-left).
    alignment: 'bottom', or 'center' to align the rectangles accordingly.
    flow: 'sideways' or 'center' to determine how the sound visualization flows.
    super_sampling: When value is greater than 1 supersampling anti-aliasing is applied.
    '''
    def __init__(self, audio_data, video_data, x, y, max_radius = 10, border_width = 1, 
                 super_sampling = 1, spacing = 5,
                 number_of_cirles = -1, bg_color = (255, 255, 255), border_color = (255, 255, 255),
                 alignment = 'bottom', flow = 'sideways'):
        super().__init__(audio_data, video_data, x, y, super_sampling)

        self.max_radius = max_radius * self.super_sampling
        self.max_diameter = max_radius * 2 * self.super_sampling
        self.border_width = border_width * self.super_sampling
        self.spacing = spacing * self.super_sampling

        self.bg_color = bg_color
        self.border_color = border_color

        if number_of_cirles != -1:
            self.number_of_cirles = number_of_cirles
        else:
            self.number_of_cirles = video_data.video_width * super_sampling // (self.max_diameter + self.spacing)

        self.alignment = alignment
        self.flow = flow

        if flow == 'center':
            if alignment == 'center':
                self.draw_frame = self._draw_center_aligned_center_flow
            else:
                self.draw_frame = self._draw_bottom_aligned_center_flow
        else:
            if alignment == 'center':
                self.draw_frame = self._draw_center_aligned_side_flow
            else:
                self.draw_frame = self._draw_bottom_aligned_side_flow

    def prepare_shapes(self):
        self.circles = []
        for i in range(self.number_of_cirles):
            x1 = self.x + i * (self.max_diameter + self.spacing)
            x2 = x1 + self.max_radius
            y1 = self.y
            y2 = y1 + self.border_width

            if x2 + self.max_radius + self.border_width >= self.video_data.video_width * self.super_sampling:
                break
            # The last two value are the x of center and radius of circle since y is fixed
            self.circles.append([x1, y1, x2, y2, x2, self.border_width]) 

        if self.flow == 'center' and len(self.circles) % 2 == 0:
            self.circles.pop()
            self.center_index = len(self.circles) // 2
        self.number_of_cirles = len(self.circles)

    '''
    Draws circles aligned to the bottom and flowing from the center outwards.
    '''
    def _draw_bottom_aligned_center_flow(self, frame_index):
        img = Image.new("RGB", (self.video_data.video_width * self.super_sampling, self.video_data.video_height * self.super_sampling), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        volume = self.audio_data.average_volumes[frame_index]
        for i in range(self.number_of_cirles // 2):
            r = self.circles[i+1][5]

            self.circles[i][0] = self.circles[i][4] - r
            self.circles[i][1] = self.y - r * 2
            self.circles[i][2] = self.circles[i][4] + r
            self.circles[i][3] = self.y
            self.circles[i][5] = r

            self.circles[self.number_of_cirles - i - 1][0] = self.circles[self.number_of_cirles - i - 1][4] - r
            self.circles[self.number_of_cirles - i - 1][1] = self.y - r * 2
            self.circles[self.number_of_cirles - i - 1][2] = self.circles[self.number_of_cirles - i - 1][4] + r
            self.circles[self.number_of_cirles - i - 1][3] = self.y
            self.circles[self.number_of_cirles - i - 1][5] = r

        r = int(self.max_radius * (volume / self.audio_data.max_volume))
        self.circles[self.center_index][0] = self.circles[self.center_index][4] - r
        self.circles[self.center_index][1] = self.y - r * 2
        self.circles[self.center_index][2] = self.circles[self.center_index][4] + r
        self.circles[self.center_index][3] = self.y
        self.circles[self.center_index][5] = r
        for circle in self.circles:
            draw.ellipse(circle[:4],
                         fill=self.bg_color, outline=self.border_color,
                         width=self.border_width)
            
        if self.super_sampling > 1:
            img = img.resize((self.video_data.video_width, self.video_data.video_height),
                        resample=Image.Resampling.LANCZOS)
        
        return np.asarray(img)
    
    '''
    Draws circles aligned to the bottom and flowing from the left side to the other.
    '''
    def _draw_bottom_aligned_side_flow(self, frame_index):
        img = Image.new("RGB", (self.video_data.video_width * self.super_sampling, self.video_data.video_height * self.super_sampling), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        volume = self.audio_data.average_volumes[frame_index]
        for i in range(self.number_of_cirles - 1):
            r = self.circles[self.number_of_cirles - i - 2][5]
            
            self.circles[self.number_of_cirles - i - 1][0] = self.circles[self.number_of_cirles - i - 1][4] - r
            self.circles[self.number_of_cirles - i - 1][1] = self.y - r * 2
            self.circles[self.number_of_cirles - i - 1][2] = self.circles[self.number_of_cirles - i - 1][4] + r
            self.circles[self.number_of_cirles - i - 1][3] = self.y
            self.circles[self.number_of_cirles - i - 1][5] = r

        r = int(self.max_radius * (volume / self.audio_data.max_volume))
        self.circles[0][0] = self.circles[0][4] - r
        self.circles[0][1] = self.y - r * 2
        self.circles[0][2] = self.circles[0][4] + r
        self.circles[0][3] = self.y
        self.circles[0][5] = r

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

        volume = self.audio_data.average_volumes[frame_index]
        for i in range(self.number_of_cirles - 1):
            r = self.circles[self.number_of_cirles - i - 2][5]
            
            self.circles[self.number_of_cirles - i - 1][0] = self.circles[self.number_of_cirles - i - 1][4] - r
            self.circles[self.number_of_cirles - i - 1][1] = self.y - r
            self.circles[self.number_of_cirles - i - 1][2] = self.circles[self.number_of_cirles - i - 1][4] + r
            self.circles[self.number_of_cirles - i - 1][3] = self.y + r
            self.circles[self.number_of_cirles - i - 1][5] = r

        r = int(self.max_radius * (volume / self.audio_data.max_volume))
        self.circles[0][0] = self.circles[0][4] - r
        self.circles[0][1] = self.y - r
        self.circles[0][2] = self.circles[0][4] + r
        self.circles[0][3] = self.y + r
        self.circles[0][5] = r

        for circle in self.circles:
            draw.ellipse(circle[:4],
                         fill=self.bg_color, outline=self.border_color,
                         width=self.border_width)
            
        if self.super_sampling > 1:
            img = img.resize((self.video_data.video_width, self.video_data.video_height),
                        resample=Image.Resampling.LANCZOS)
        
        return np.asarray(img)
    
    '''
    Draws circles centered vertically and flowing from the center outwards.
    '''
    def _draw_center_aligned_center_flow(self, frame_index):
        img = Image.new("RGB", (self.video_data.video_width * self.super_sampling, self.video_data.video_height * self.super_sampling), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        volume = self.audio_data.average_volumes[frame_index]
        for i in range(self.number_of_cirles // 2):
            r = self.circles[i+1][5]

            self.circles[i][0] = self.circles[i][4] - r
            self.circles[i][1] = self.y - r
            self.circles[i][2] = self.circles[i][4] + r
            self.circles[i][3] = self.y + r
            self.circles[i][5] = r

            self.circles[self.number_of_cirles - i - 1][0] = self.circles[self.number_of_cirles - i - 1][4] - r
            self.circles[self.number_of_cirles - i - 1][1] = self.y - r
            self.circles[self.number_of_cirles - i - 1][2] = self.circles[self.number_of_cirles - i - 1][4] + r
            self.circles[self.number_of_cirles - i - 1][3] = self.y + r
            self.circles[self.number_of_cirles - i - 1][5] = r
        
        r = int(self.max_radius * (volume / self.audio_data.max_volume))
        self.circles[self.center_index][0] = self.circles[self.center_index][4] - r
        self.circles[self.center_index][1] = self.y - r
        self.circles[self.center_index][2] = self.circles[self.center_index][4] + r
        self.circles[self.center_index][3] = self.y + r
        self.circles[self.center_index][5] = r

        for circle in self.circles:
            draw.ellipse(circle[:4],
                         fill=self.bg_color, outline=self.border_color,
                         width=self.border_width)
            
        if self.super_sampling > 1:
            img = img.resize((self.video_data.video_width, self.video_data.video_height),
                        resample=Image.Resampling.LANCZOS)
        
        return np.asarray(img)
    

    
class CircleVisualizerView(VisualizerView):
    '''
    Each Visualizer is to produce a QWidget with an attached Layout that contains all the
    required gui elements to collect require settings for this visualizer.
    '''
    def setup_setting_widgets(self) -> QWidget:
        self.layout = QFormLayout()
            
        self.radius = QLineEdit("25")
        self.radius.setValidator(QIntValidator(1, int(1e6)))
        self.layout.addRow("Radius:", self.radius)

        self.super_sampling = QLineEdit("4")
        self.super_sampling.setValidator(QIntValidator(1, 64))
        self.super_sampling.setToolTip("This is used to antialias the individual shapes. This will help smooth the circles. It is only applies if value is greater then 1.")
        self.layout.addRow("Super-sampling:", self.super_sampling)

        self.controler = QWidget()
        self.controler.setLayout(self.layout)

        return self.controler

    '''
    Returns the master control widget than embeds the settings widgets returned from set_setting_widgets().
    '''
    def get_controler_widget(self) -> QWidget:
        return self.controler
    
    '''
    Verifies the values of the widgets are valid for this visualizer.
    '''
    def verify_widget_values(self) -> bool:
        try:
            radius = int(self.radius.text())
            super_sample = int(self.super_sampling.text())
        except:
            return False
        return True
    
    '''
    Reads the widget values to prepare the visualizer.
    '''
    def read_widget_values(self):
        raise NotImplementedError("Subclasses should implement this method.")