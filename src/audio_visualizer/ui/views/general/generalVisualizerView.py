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

from PySide6.QtCore import (
    Qt
)

from PySide6.QtWidgets import (
    QFormLayout, QHBoxLayout,
    QWidget, QComboBox, QLabel, QLineEdit, QPushButton,
    QColorDialog,
    QSizePolicy
)

from PySide6.QtGui import (
    QIntValidator
)

from audio_visualizer.ui.views.general.generalView import View
from audio_visualizer.ui.views.general.utilities import Fonts

from audio_visualizer.visualizers import utilities

class GeneralVisualizerSettings:
    visualizer_type = utilities.VisualizerOptions.VOLUME_RECTANGLE
    alignment = utilities.VisualizerAlignment.BOTTOM

    x = 0
    y = 0

    bg_color = (0,0,0)
    border_color = (0,0,0)
    border_width = 0

    spacing = 0

    super_sampling = 0

class GeneralVisualizerView(View):

    def __init__(self, parent):
        super().__init__()
        
        form_layout = QFormLayout()

        section_label = QLabel("General Visualization Settings")
        section_label.setFont(Fonts.h2_font)
        section_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        section_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.layout.addWidget(section_label, 0, 0)
        
        self.visualizer_x = QLineEdit("0")
        self.visualizer_x.setValidator(QIntValidator(0, 1e6))
        form_layout.addRow("Visualizer X:", self.visualizer_x)

        self.visualizer_y = QLineEdit("50")
        self.visualizer_y.setValidator(QIntValidator(0, 1e6))
        form_layout.addRow("Visualizer Y:", self.visualizer_y)

        self.visualizer = QComboBox()
        self.visualizer.addItems(utilities.VisualizerOptions.list())
        self.visualizer.currentTextChanged.connect(parent.visualizer_selection_changed)
        form_layout.addRow("Visualizer Type:", self.visualizer)

        self.visualizer_alignment = QComboBox()
        self.visualizer_alignment.addItems(utilities.VisualizerAlignment.list())
        form_layout.addRow("Alignment:", self.visualizer_alignment)

        bg_row = QHBoxLayout()
        self.visualizer_bg_color_field = QLineEdit("227, 209, 169")
        self.visualizer_bg_color_field.setPlaceholderText("R, G, B")
        bg_row.addWidget(self.visualizer_bg_color_field)
        self.visualizer_bg_color_button = QPushButton("Select Color")
        self.visualizer_bg_color = QColorDialog()
        self.visualizer_bg_color.colorSelected.connect(lambda color: self.visualizer_bg_color_field.setText(
            f"{color.red()}, {color.green()}, {color.blue()}"
        ))
        self.visualizer_bg_color_button.clicked.connect(self.visualizer_bg_color.open)
        bg_row.addWidget(self.visualizer_bg_color_button)
        self.visualizer_bg_color_swatch = QLabel()
        self.visualizer_bg_color_swatch.setFixedSize(18, 18)
        self.visualizer_bg_color_swatch.setStyleSheet("border: 1px solid #888; background: rgb(227, 209, 169);")
        bg_row.addWidget(self.visualizer_bg_color_swatch)
        form_layout.addRow("Background Color:", bg_row)

        self.visualizer_border_width = QLineEdit("1")
        self.visualizer_border_width.setValidator(QIntValidator(0, int(1e6)))
        form_layout.addRow("Border Width:", self.visualizer_border_width)

        border_row = QHBoxLayout()
        self.visualizer_border_color_field = QLineEdit("227, 209, 169")
        self.visualizer_border_color_field.setPlaceholderText("R, G, B")   
        border_row.addWidget(self.visualizer_border_color_field)
        self.visualizer_border_color_button = QPushButton("Select Color")
        self.visualizer_border_color = QColorDialog()
        self.visualizer_border_color.colorSelected.connect(lambda color: self.visualizer_border_color_field.setText(
            f"{color.red()}, {color.green()}, {color.blue()}"
        ))
        self.visualizer_border_color_button.clicked.connect(self.visualizer_border_color.open)
        border_row.addWidget(self.visualizer_border_color_button)
        self.visualizer_border_color_swatch = QLabel()
        self.visualizer_border_color_swatch.setFixedSize(18, 18)
        self.visualizer_border_color_swatch.setStyleSheet("border: 1px solid #888; background: rgb(227, 209, 169);")
        border_row.addWidget(self.visualizer_border_color_swatch)
        form_layout.addRow("Border Color:", border_row)

        self.visualizer_spacing = QLineEdit("5")
        self.visualizer_spacing.setValidator(QIntValidator(0, int(1e6)))
        form_layout.addRow("Spacing:", self.visualizer_spacing)

        self.super_sampling = QLineEdit("1")
        self.super_sampling.setValidator(QIntValidator(1, 64))
        self.super_sampling.setToolTip("This is used to antialias the individual shapes. This will help smooth rounded corners. It is only applies if value is greater then 1.")
        form_layout.addRow("Supersampling:", self.super_sampling)

        self.layout.addLayout(form_layout, 1, 0)
        self.visualizer_bg_color_field.textChanged.connect(
            lambda _: self._update_swatch(self.visualizer_bg_color_field, self.visualizer_bg_color_swatch)
        )
        self.visualizer_border_color_field.textChanged.connect(
            lambda _: self._update_swatch(self.visualizer_border_color_field, self.visualizer_border_color_swatch)
        )

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
    def _update_swatch(field: QLineEdit, swatch: QLabel):
        try:
            color = GeneralVisualizerView._parse_color(field.text())
        except Exception:
            swatch.setStyleSheet("border: 1px solid #888; background: transparent;")
            return
        swatch.setStyleSheet(f"border: 1px solid #888; background: rgb({color[0]}, {color[1]}, {color[2]});")

    '''
    Verifies that the input values in the view are valide.
    '''
    def validate_view(self) -> bool:
        try:
            x = int(self.visualizer_x.text())
            y = int(self.visualizer_y.text())

            bg_color = self._parse_color(self.visualizer_bg_color_field.text())
            border_color = self._parse_color(self.visualizer_border_color_field.text())
            border_width = int(self.visualizer_border_width.text())

            spacing = int(self.visualizer_spacing.text())
            super_sampling = int(self.super_sampling.text())
        except:
            return False
        return True
    
    '''
    Transforms the input values in the view into a python object.
    '''
    def read_view_values(self) -> GeneralVisualizerSettings:
        settings = GeneralVisualizerSettings()

        settings.visualizer_type = utilities.VisualizerOptions(self.visualizer.currentText())
        settings.alignment = utilities.VisualizerAlignment(self.visualizer_alignment.currentText())

        settings.x = int(self.visualizer_x.text())
        settings.y = int(self.visualizer_y.text())

        settings.bg_color = self._parse_color(self.visualizer_bg_color_field.text())
        settings.border_color = self._parse_color(self.visualizer_border_color_field.text())
        settings.border_width = int(self.visualizer_border_width.text())

        settings.spacing = int(self.visualizer_spacing.text())

        settings.super_sampling = int(self.super_sampling.text())

        return settings




