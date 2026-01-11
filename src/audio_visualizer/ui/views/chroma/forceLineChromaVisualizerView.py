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
    QIntValidator, QDoubleValidator
)

from audio_visualizer.ui.views.general.generalView import View

class ForceLineChromaVisualizerSettings:
    line_thickness = 0
    points_count = 0
    tension = 0.0
    damping = 0.0
    force_strength = 0.0
    gravity = 0.0
    smoothness = 0

class ForceLineChromaVisualizerView(View):
    '''
    Collect settings for force-based chroma line visualizer.
    '''
    def __init__(self):
        super().__init__()

        self.layout = QFormLayout()

        self.line_thickness = QLineEdit("2")
        self.line_thickness.setValidator(QIntValidator(1, int(1e6)))
        self.layout.addRow("Line Thickness:", self.line_thickness)

        self.points_count = QLineEdit("80")
        self.points_count.setValidator(QIntValidator(3, int(1e6)))
        self.layout.addRow("Points Count:", self.points_count)

        self.smoothness = QLineEdit("6")
        self.smoothness.setValidator(QIntValidator(2, int(1e6)))
        self.layout.addRow("Curve Smoothness:", self.smoothness)

        self.tension = QLineEdit("0.08")
        self.tension.setValidator(QDoubleValidator(0.0, 10.0, 4))
        self.layout.addRow("Tension:", self.tension)

        self.damping = QLineEdit("0.02")
        self.damping.setValidator(QDoubleValidator(0.0, 10.0, 4))
        self.layout.addRow("Damping:", self.damping)

        self.force_strength = QLineEdit("1.0")
        self.force_strength.setValidator(QDoubleValidator(0.0, 100.0, 4))
        self.layout.addRow("Force Strength:", self.force_strength)

        self.gravity = QLineEdit("0.02")
        self.gravity.setValidator(QDoubleValidator(0.0, 10.0, 4))
        self.layout.addRow("Gravity:", self.gravity)

        self.controler.setLayout(self.layout)

    def validate_view(self) -> bool:
        try:
            int(self.line_thickness.text())
            int(self.points_count.text())
            int(self.smoothness.text())
            float(self.tension.text())
            float(self.damping.text())
            float(self.force_strength.text())
            float(self.gravity.text())
        except:
            return False
        return True

    def read_view_values(self) -> ForceLineChromaVisualizerSettings:
        settings = ForceLineChromaVisualizerSettings()
        settings.line_thickness = int(self.line_thickness.text())
        settings.points_count = int(self.points_count.text())
        settings.smoothness = int(self.smoothness.text())
        settings.tension = float(self.tension.text())
        settings.damping = float(self.damping.text())
        settings.force_strength = float(self.force_strength.text())
        settings.gravity = float(self.gravity.text())
        return settings


