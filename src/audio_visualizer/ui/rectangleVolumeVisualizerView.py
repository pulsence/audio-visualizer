
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

from PySide6.QtWidgets import (
    QFormLayout, QLineEdit, QComboBox
)

from PySide6.QtGui import (
    QIntValidator
)

from audio_visualizer.ui import View

from audio_visualizer.visualizers.utilities import VisualizerFlow

class RectangleVolumeVisualizerSettings:
    box_height = 0
    box_width = 0
    corner_radius = 0
    flow = VisualizerFlow.LEFT_TO_RIGHT

class RectangleVolumeVisualizerView(View):
    '''
    Each Visualizer is to produce a QWidget with an attached Layout that contains all the
    required gui elements to collect require settings for this visualizer.
    '''
    def __init__(self):
        super().__init__()

        self.layout = QFormLayout()
    
        self.visualizer_flow = QComboBox()
        self.visualizer_flow.addItems(VisualizerFlow.list())
        self.layout.addRow("Flow:", self.visualizer_flow)

        self.box_height = QLineEdit("50")
        self.box_height.setValidator(QIntValidator(1, int(1e6)))
        self.layout.addRow("Box Height:", self.box_height)

        self.box_width = QLineEdit("10")
        self.box_width.setValidator(QIntValidator(1, int(1e6)))
        self.layout.addRow("Box Width:", self.box_width)

        self.corner_radius = QLineEdit("0")
        self.corner_radius.setValidator(QIntValidator(0, int(1e6)))
        self.layout.addRow("Corner Radius:", self.corner_radius)
        
        self.controler.setLayout(self.layout)
    
    '''
    Verifies the values of the widgets are valid for this visualizer.
    '''
    def validate_view(self) -> bool:
        try:
            box_height = int(self.box_height.text())
            box_width = int(self.box_width.text())
            corner_radius = int(self.corner_radius.text())
        except:
            return False
        return True
    '''
    Reads the widget values to prepare the visualizer.
    '''
    def read_view_values(self) -> RectangleVolumeVisualizerSettings:
        settings = RectangleVolumeVisualizerSettings()

        settings.box_height = int(self.box_height.text())
        settings.box_width = int(self.box_width.text())
        settings.corner_radius = int(self.corner_radius.text())

        settings.flow = VisualizerFlow(self.visualizer_flow.currentText())

        return settings

