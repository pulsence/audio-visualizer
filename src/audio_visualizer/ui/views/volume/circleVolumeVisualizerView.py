
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

from audio_visualizer.ui.views.general.generalView import View
from audio_visualizer.visualizers.utilities import VisualizerFlow

class CircleVolumeVisualizerSettings:
    radius = 0
    flow = VisualizerFlow.LEFT_TO_RIGHT

class CircleVolumeVisualizerView(View):
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

        self.radius = QLineEdit("25")
        self.radius.setValidator(QIntValidator(1, int(1e6)))
        self.layout.addRow("Radius:", self.radius)

        self.controler.setLayout(self.layout)

    '''
    Verifies the values of the widgets are valid for this visualizer.
    '''
    def validate_view(self) -> bool:
        try:
            radius = int(self.radius.text())
        except:
            return False
        return True
    
    '''
    Reads the widget values to prepare the visualizer.
    '''
    def read_view_values(self) -> CircleVolumeVisualizerSettings:
        settings = CircleVolumeVisualizerSettings()

        settings.radius = int(self.radius.text())
        settings.flow = VisualizerFlow(self.visualizer_flow.currentText())

        return settings


