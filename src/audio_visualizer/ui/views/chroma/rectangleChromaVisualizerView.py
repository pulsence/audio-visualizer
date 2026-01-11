
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
    QFormLayout, QLineEdit, QComboBox, QHBoxLayout, QPushButton, QColorDialog, QLabel
)

from PySide6.QtGui import (
    QIntValidator
)

from audio_visualizer.ui.views.general.generalView import View

class RectangleChromaVisualizerSettings:
    box_height = 0
    corner_radius = 0
    color_mode = "Single"
    gradient_start = (0, 0, 0)
    gradient_end = (0, 0, 0)
    band_colors = []

class RectangleChromaVisualizerView(View):
    '''
    Each Visualizer is to produce a QWidget with an attached Layout that contains all the
    required gui elements to collect require settings for this visualizer.
    '''
    def __init__(self):
        super().__init__()

        self.layout = QFormLayout()

        self.box_height = QLineEdit("50")
        self.box_height.setValidator(QIntValidator(1, int(1e6)))
        self.layout.addRow("Box Height:", self.box_height)

        self.corner_radius = QLineEdit("0")
        self.corner_radius.setValidator(QIntValidator(0, int(1e6)))
        self.layout.addRow("Corner Radius:", self.corner_radius)

        self.color_mode = QComboBox()
        self.color_mode.addItems(["Single", "Gradient", "Per-band"])
        self.layout.addRow("Color Mode:", self.color_mode)

        gradient_start_row = QHBoxLayout()
        self.gradient_start = QLineEdit("227, 209, 169")
        self.gradient_start.setPlaceholderText("R, G, B")
        gradient_start_row.addWidget(self.gradient_start)
        self.gradient_start_button = QPushButton("Select Color")
        self.gradient_start_picker = QColorDialog()
        self.gradient_start_picker.colorSelected.connect(lambda color: self.gradient_start.setText(
            f"{color.red()}, {color.green()}, {color.blue()}"
        ))
        self.gradient_start_button.clicked.connect(self.gradient_start_picker.open)
        gradient_start_row.addWidget(self.gradient_start_button)
        self.gradient_start_swatch = QLabel()
        self.gradient_start_swatch.setFixedSize(18, 18)
        self.gradient_start_swatch.setStyleSheet("border: 1px solid #888; background: rgb(227, 209, 169);")
        gradient_start_row.addWidget(self.gradient_start_swatch)
        self.layout.addRow("Gradient Start:", gradient_start_row)

        gradient_end_row = QHBoxLayout()
        self.gradient_end = QLineEdit("255, 255, 255")
        self.gradient_end.setPlaceholderText("R, G, B")
        gradient_end_row.addWidget(self.gradient_end)
        self.gradient_end_button = QPushButton("Select Color")
        self.gradient_end_picker = QColorDialog()
        self.gradient_end_picker.colorSelected.connect(lambda color: self.gradient_end.setText(
            f"{color.red()}, {color.green()}, {color.blue()}"
        ))
        self.gradient_end_button.clicked.connect(self.gradient_end_picker.open)
        gradient_end_row.addWidget(self.gradient_end_button)
        self.gradient_end_swatch = QLabel()
        self.gradient_end_swatch.setFixedSize(18, 18)
        self.gradient_end_swatch.setStyleSheet("border: 1px solid #888; background: rgb(255, 255, 255);")
        gradient_end_row.addWidget(self.gradient_end_swatch)
        self.layout.addRow("Gradient End:", gradient_end_row)

        self.band_colors = QLineEdit("")
        self.band_colors.setPlaceholderText("12 colors: r,g,b|r,g,b|...")
        self.layout.addRow("Per-band Colors:", self.band_colors)

        self.controler.setLayout(self.layout)
        self.gradient_start.textChanged.connect(lambda _: self._update_swatch(self.gradient_start, self.gradient_start_swatch))
        self.gradient_end.textChanged.connect(lambda _: self._update_swatch(self.gradient_end, self.gradient_end_swatch))
    
    '''
    Verifies the values of the widgets are valid for this visualizer.
    '''
    def validate_view(self) -> bool:
        try:
            box_height = int(self.box_height.text())
            corner_radius = int(self.corner_radius.text())

            if self.color_mode.currentText() == "Gradient":
                self._parse_color(self.gradient_start.text())
                self._parse_color(self.gradient_end.text())
            elif self.color_mode.currentText() == "Per-band":
                self._parse_band_colors(self.band_colors.text())
        except:
            return False
        return True
    '''
    Reads the widget values to prepare the visualizer.
    '''
    def read_view_values(self) -> RectangleChromaVisualizerSettings:
        settings = RectangleChromaVisualizerSettings()

        settings.box_height = int(self.box_height.text())
        settings.corner_radius = int(self.corner_radius.text())
        settings.color_mode = self.color_mode.currentText()
        settings.gradient_start = self._parse_color_optional(self.gradient_start.text())
        settings.gradient_end = self._parse_color_optional(self.gradient_end.text())
        settings.band_colors = self._parse_band_colors(self.band_colors.text())

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

    @staticmethod
    def _parse_color_optional(text: str):
        if not text.strip():
            return (0, 0, 0)
        return RectangleChromaVisualizerView._parse_color(text)

    @staticmethod
    def _parse_band_colors(text: str):
        if not text.strip():
            return []
        colors = []
        for chunk in text.split("|"):
            colors.append(RectangleChromaVisualizerView._parse_color(chunk))
        return colors

    @staticmethod
    def _update_swatch(field: QLineEdit, swatch: QLabel):
        try:
            color = RectangleChromaVisualizerView._parse_color(field.text())
        except Exception:
            swatch.setStyleSheet("border: 1px solid #888; background: transparent;")
            return
        swatch.setStyleSheet(f"border: 1px solid #888; background: rgb({color[0]}, {color[1]}, {color[2]});")



