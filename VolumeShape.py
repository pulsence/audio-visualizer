'''
Code for an audio visualizer that generates rectangles based on the audio's different qualities.
'''
import numpy as np
from PIL import Image, ImageDraw
from utilities import Generator

class RectangleVisualizer(Generator):
    '''
    number_of_boxes: If set to -1, it will calculate the number of boxes based on the video width,
    box width, and box spacing.
    corner_radius: Radius of the rectangle corners.
    corners: Tuple of booleans indicating which corners should be rounded (top-left, top-right, bottom-right, bottom-left).
    alignment: 'bottom', or 'center' to align the rectangles accordingly.
    flow: 'sideways' or 'center' to determine how the sound visualization flows.
    '''
    def __init__(self, audio_data, video_data, x, y, box_height = 50, box_width = 10, border_width = 1, spacing = 5, number_of_boxes = -1, 
                 corner_radius = 0, corners = (True, True, True, True), bg_color = (255, 255, 255), border_color = (255, 255, 255),
                 alignment = 'bottom', flow = 'sideways'):
        super().__init__(audio_data, video_data, x, y)

        self.box_width = box_width
        self.border_width = border_width
        self.box_height = box_height
        self.spacing = spacing
        self.corner_radius = corner_radius
        self.corners = corners

        self.bg_color = bg_color
        self.border_color = border_color

        if number_of_boxes != -1:
            self.number_of_boxes = number_of_boxes
        else:
            self.number_of_boxes = video_data.video_width // (self.box_width + self.spacing)

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
        self.rectangles = []
        for i in range(self.number_of_boxes):
            x1 = self.x + i * (self.box_width + self.spacing)
            x2 = x1 + self.box_width
            y1 = self.y
            y2 = self.y + self.border_width
            if x2 >= self.video_data.video_width:
                break
            self.rectangles.append([x1, y1, x2, y2])

        if self.flow == 'center' and len(self.rectangles) % 2 == 0:
            self.rectangles.pop()  # Remove the last rectangle to keep it odd for centering
            self.center_index = len(self.rectangles) // 2
        self.number_of_boxes = len(self.rectangles)

    '''
    Draws rectangles aligned to the bottom and flowing from the center outwards.
    '''
    def _draw_bottom_aligned_center_flow(self, frame_index):
        img = Image.new("RGB", (self.video_data.video_width, self.video_data.video_height), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        volume = self.audio_data.average_volumes[frame_index]
        for i in range(self.number_of_boxes // 2):
            self.rectangles[i][1] = self.rectangles[i+1][1]
            self.rectangles[self.number_of_boxes - i - 1][1] = self.rectangles[self.number_of_boxes - i - 2][1]
        self.rectangles[self.center_index][1] = self.y - int(self.box_height * (volume / self.audio_data.max_volume))

        for rect in self.rectangles:
            draw.rounded_rectangle(rect, self.corner_radius,
                                   fill=self.bg_color, outline=self.border_color,
                                   width=self.border_width,
                                   corners=(True, True, True, True))
        return np.asarray(img)
    
    '''
    Draws rectangles aligned to the bottom and flowing from the left side to the other.
    '''
    def _draw_bottom_aligned_side_flow(self, frame_index):
        img = Image.new("RGB", (self.video_data.video_width, self.video_data.video_height), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        volume = self.audio_data.average_volumes[frame_index]
        for i in range(self.number_of_boxes - 1):
            self.rectangles[self.number_of_boxes - i - 1][1] = self.rectangles[self.number_of_boxes - i - 2][1]
        self.rectangles[0][1] = self.y - int(self.box_height * (volume / self.audio_data.max_volume))

        for rect in self.rectangles:
            draw.rounded_rectangle(rect, self.corner_radius,
                                   fill=self.bg_color, outline=self.border_color,
                                   width=self.border_width,
                                   corners=(True, True, True, True))
        return np.asarray(img)

    '''
    Draws rectangles centered vertically and flowing from the left side to the other.
    '''
    def _draw_center_aligned_side_flow(self, frame_index):
        img = Image.new("RGB", (self.video_data.video_width, self.video_data.video_height), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        volume = self.audio_data.average_volumes[frame_index]
        for i in range(self.number_of_boxes - 1):
            self.rectangles[self.number_of_boxes - i - 1][1] = self.rectangles[self.number_of_boxes - i - 2][1]
            self.rectangles[self.number_of_boxes - i - 1][3] = self.rectangles[self.number_of_boxes - i - 2][3]
        offset = int(self.box_height * (volume / self.audio_data.max_volume)) // 2
        self.rectangles[0][1] = self.y - offset
        self.rectangles[0][3] = self.y + offset

        for rect in self.rectangles:
            draw.rounded_rectangle(rect, self.corner_radius,
                                   fill=self.bg_color, outline=self.border_color,
                                   width=self.border_width,
                                   corners=(True, True, True, True))
        return np.asarray(img)
    
    '''
    Draws rectangles centered vertically and flowing from the center outwards.
    '''
    def _draw_center_aligned_center_flow(self, frame_index):
        img = Image.new("RGB", (self.video_data.video_width, self.video_data.video_height), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        volume = self.audio_data.average_volumes[frame_index]
        for i in range(self.number_of_boxes // 2):
            self.rectangles[i][1] = self.rectangles[i+1][1]
            self.rectangles[i][3] = self.rectangles[i+1][3]
            self.rectangles[self.number_of_boxes - i - 1][1] = self.rectangles[self.number_of_boxes - i - 2][1]
            self.rectangles[self.number_of_boxes - i - 1][3] = self.rectangles[self.number_of_boxes - i - 2][3]
        offset = int(self.box_height * (volume / self.audio_data.max_volume)) // 2
        self.rectangles[self.center_index][1] = self.y - offset
        self.rectangles[self.center_index][3] = self.y + offset

        for rect in self.rectangles:
            draw.rounded_rectangle(rect, self.corner_radius,
                                   fill=self.bg_color, outline=self.border_color,
                                   width=self.border_width,
                                   corners=(True, True, True, True))
        return np.asarray(img)
    

class CircleVisualizer(Generator):
    '''
    number_of_cirlces: If set to -1, it will calculate the number of circles based on the video width,
    max radius, and spacing.
    corners: Tuple of booleans indicating which corners should be rounded (top-left, top-right, bottom-right, bottom-left).
    alignment: 'bottom', or 'center' to align the rectangles accordingly.
    flow: 'sideways' or 'center' to determine how the sound visualization flows.
    '''
    def __init__(self, audio_data, video_data, x, y, max_radius = 10, border_width = 1, spacing = 5, number_of_cirles = -1, 
                 bg_color = (255, 255, 255), border_color = (255, 255, 255),
                 alignment = 'bottom', flow = 'sideways'):
        super().__init__(audio_data, video_data, x, y)

        self.max_radius = max_radius
        self.max_diameter = max_radius * 2
        self.border_width = border_width
        self.spacing = spacing

        self.bg_color = bg_color
        self.border_color = border_color

        if number_of_cirles != -1:
            self.number_of_cirles = number_of_cirles
        else:
            self.number_of_cirles = video_data.video_width // (self.max_diameter + self.spacing)

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

            if x2 + self.max_radius + self.border_width >= self.video_data.video_width:
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
        img = Image.new("RGB", (self.video_data.video_width, self.video_data.video_height), (0, 0, 0))
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
        return np.asarray(img)
    
    '''
    Draws circles aligned to the bottom and flowing from the left side to the other.
    '''
    def _draw_bottom_aligned_side_flow(self, frame_index):
        img = Image.new("RGB", (self.video_data.video_width, self.video_data.video_height), (0, 0, 0))
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
        return np.asarray(img)

    '''
    Draws circles centered vertically and flowing from the left side to the other.
    '''
    def _draw_center_aligned_side_flow(self, frame_index):
        img = Image.new("RGB", (self.video_data.video_width, self.video_data.video_height), (0, 0, 0))
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
        return np.asarray(img)
    
    '''
    Draws circles centered vertically and flowing from the center outwards.
    '''
    def _draw_center_aligned_center_flow(self, frame_index):
        img = Image.new("RGB", (self.video_data.video_width, self.video_data.video_height), (0, 0, 0))
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
        return np.asarray(img)