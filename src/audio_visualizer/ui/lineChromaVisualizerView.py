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
    QFormLayout, QLineEdit
)

from PySide6.QtGui import (
    QIntValidator
)

from audio_visualizer.ui import View

class LineChromaVisualizerSettings:
    max_height = 0
    line_thickness = 0

class LineChromaVisualizerView(View):
    '''
    Collect settings for smooth line chroma visualizer.
    '''
    def __init__(self):
        super().__init__()

        self.layout = QFormLayout()

        self.max_height = QLineEdit("50")
        self.max_height.setValidator(QIntValidator(1, int(1e6)))
        self.layout.addRow("Max Height:", self.max_height)

        self.line_thickness = QLineEdit("2")
        self.line_thickness.setValidator(QIntValidator(1, int(1e6)))
        self.layout.addRow("Line Thickness:", self.line_thickness)

        self.controler.setLayout(self.layout)

    '''
    Verifies the values of the widgets are valid for this visualizer.
    '''
    def validate_view(self) -> bool:
        try:
            max_height = int(self.max_height.text())
            line_thickness = int(self.line_thickness.text())
        except:
            return False
        return max_height > 0 and line_thickness > 0

    '''
    Reads the widget values to prepare the visualizer.
    '''
    def read_view_values(self) -> LineChromaVisualizerSettings:
        settings = LineChromaVisualizerSettings()
        settings.max_height = int(self.max_height.text())
        settings.line_thickness = int(self.line_thickness.text())
        return settings
