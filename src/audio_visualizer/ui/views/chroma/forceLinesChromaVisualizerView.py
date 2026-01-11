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
    QFormLayout, QLineEdit, QHBoxLayout, QPushButton, QColorDialog, QLabel,
    QTabWidget, QWidget
)

from PySide6.QtGui import (
    QIntValidator, QDoubleValidator
)

from audio_visualizer.ui.views.general.generalView import View

class ForceLinesChromaVisualizerSettings:
    line_thickness = 0
    points_count = 0
    smoothness = 0
    tension = 0.0
    damping = 0.0
    force_strength = 0.0
    gravity = 0.0
    band_spacing = 0
    band_colors = None

class ForceLinesChromaVisualizerView(View):
    '''
    Collect settings for force-based chroma lines visualizer.
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

        self.band_spacing = QLineEdit("6")
        self.band_spacing.setValidator(QIntValidator(0, int(1e6)))
        self.layout.addRow("Band Spacing:", self.band_spacing)

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

    def validate_view(self) -> bool:
        try:
            int(self.line_thickness.text())
            int(self.points_count.text())
            int(self.smoothness.text())
            int(self.band_spacing.text())
            float(self.tension.text())
            float(self.damping.text())
            float(self.force_strength.text())
            float(self.gravity.text())
            colors = self._parse_band_colors()
            if len(colors) != 12:
                return False
        except:
            return False
        return True

    def read_view_values(self) -> ForceLinesChromaVisualizerSettings:
        settings = ForceLinesChromaVisualizerSettings()
        settings.line_thickness = int(self.line_thickness.text())
        settings.points_count = int(self.points_count.text())
        settings.smoothness = int(self.smoothness.text())
        settings.band_spacing = int(self.band_spacing.text())
        settings.tension = float(self.tension.text())
        settings.damping = float(self.damping.text())
        settings.force_strength = float(self.force_strength.text())
        settings.gravity = float(self.gravity.text())
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
            color = ForceLinesChromaVisualizerView._parse_color(field.text())
        except Exception:
            swatch.setStyleSheet("border: 1px solid #888; background: transparent;")
            return
        swatch.setStyleSheet(f"border: 1px solid #888; background: rgb({color[0]}, {color[1]}, {color[2]});")


