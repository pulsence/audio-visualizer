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
    QFormLayout, QLineEdit, QComboBox, QHBoxLayout, QPushButton, QColorDialog, QLabel,
    QTabWidget, QWidget
)

from PySide6.QtGui import (
    QIntValidator
)

from audio_visualizer.ui.views.general.generalView import View
from audio_visualizer.visualizers.utilities import VisualizerFlow

class LineChromaBandsVisualizerSettings:
    max_height = 0
    line_thickness = 0
    smoothness = 0
    flow = VisualizerFlow.LEFT_TO_RIGHT
    band_colors = None
    band_spacing = 0

class LineChromaBandsVisualizerView(View):
    '''
    Collect settings for per-band chroma line visualizer.
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

        self.smoothness = QLineEdit("8")
        self.smoothness.setValidator(QIntValidator(2, int(1e6)))
        self.layout.addRow("Curve Smoothness:", self.smoothness)

        self.band_spacing = QLineEdit("6")
        self.band_spacing.setValidator(QIntValidator(0, int(1e6)))
        self.layout.addRow("Band Spacing:", self.band_spacing)

        self.visualizer_flow = QComboBox()
        self.visualizer_flow.addItems(VisualizerFlow.list())
        self.layout.addRow("Flow:", self.visualizer_flow)

        self.band_color_fields = []
        self.band_color_swatches = []
        self.band_color_buttons = []
        self.band_color_pickers = []
        self.band_color_tabs = QTabWidget()

        for tab_index in range(2):
            tab = QWidget()
            tab_layout = QFormLayout()
            for i in range(6):
                band_index = tab_index * 6 + i
                row = QHBoxLayout()
                field = QLineEdit("227, 209, 169")
                field.setPlaceholderText("R, G, B")
                row.addWidget(field)
                button = QPushButton("Select Color")
                picker = QColorDialog(self.controler)
                picker.colorSelected.connect(lambda color, f=field: f.setText(
                    f"{color.red()}, {color.green()}, {color.blue()}"
                ))
                button.clicked.connect(picker.open)
                row.addWidget(button)
                swatch = QLabel()
                swatch.setFixedSize(18, 18)
                swatch.setStyleSheet("border: 1px solid #888; background: rgb(227, 209, 169);")
                row.addWidget(swatch)
                tab_layout.addRow(f"Band {band_index + 1} Color:", row)
                field.textChanged.connect(lambda _, f=field, s=swatch: self._update_swatch(f, s))
                self.band_color_fields.append(field)
                self.band_color_swatches.append(swatch)
                self.band_color_buttons.append(button)
                self.band_color_pickers.append(picker)
            tab.setLayout(tab_layout)
            self.band_color_tabs.addTab(tab, f"Bands {tab_index * 6 + 1}-{tab_index * 6 + 6}")

        self.layout.addRow("Band Colors:", self.band_color_tabs)

        self.controler.setLayout(self.layout)

    '''
    Verifies the values of the widgets are valid for this visualizer.
    '''
    def validate_view(self) -> bool:
        try:
            max_height = int(self.max_height.text())
            line_thickness = int(self.line_thickness.text())
            smoothness = int(self.smoothness.text())
            band_spacing = int(self.band_spacing.text())
        except:
            return False
        if max_height <= 0 or line_thickness <= 0 or smoothness < 2 or band_spacing < 0:
            return False
        try:
            colors = self._parse_band_colors()
            if len(colors) != 12:
                return False
        except Exception:
            return False
        return True

    '''
    Reads the widget values to prepare the visualizer.
    '''
    def read_view_values(self) -> LineChromaBandsVisualizerSettings:
        settings = LineChromaBandsVisualizerSettings()
        settings.max_height = int(self.max_height.text())
        settings.line_thickness = int(self.line_thickness.text())
        settings.smoothness = int(self.smoothness.text())
        settings.band_spacing = int(self.band_spacing.text())
        settings.flow = VisualizerFlow(self.visualizer_flow.currentText())
        settings.band_colors = self._parse_band_colors()
        return settings

    @staticmethod
    def _parse_color(text: str):
        parts = [part.strip() for part in text.split(",")]
        if len(parts) != 3:
            raise ValueError("Color must be three components.")
        values = tuple(int(part) for part in parts)
        for value in values:
            if value < 0 or value > 255:
                raise ValueError("Color components must be 0-255.")
        return values

    def _parse_band_colors(self):
        colors = []
        for field in self.band_color_fields:
            colors.append(self._parse_color(field.text()))
        return colors

    @staticmethod
    def _update_swatch(field: QLineEdit, swatch: QLabel):
        try:
            color = LineChromaBandsVisualizerView._parse_color(field.text())
        except Exception:
            swatch.setStyleSheet("border: 1px solid #888; background: transparent;")
            return
        swatch.setStyleSheet(f"border: 1px solid #888; background: rgb({color[0]}, {color[1]}, {color[2]});")


