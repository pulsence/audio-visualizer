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
from .generalView import View

from .utilities import Fonts

Fonts.h1_font.setPointSize(24)
Fonts.h1_font.setBold(True)
Fonts.h2_font.setPointSize(16)
Fonts.h2_font.setUnderline(True)

# General UI Views
from .generalSettingViews import GeneralSettingsView, GeneralSettings
from .generalVisualizerView import GeneralVisualizerView, GeneralVisualizerSettings

# Visualizer Specific Views
from .rectangleVolumeVisualizerView import RectangleVolumeVisualizerView, RectangleVolumeVisualizerSettings
from .circleVolumeVisualizerView import CircleVolumeVisualizerView, CircleVolumeVisualizerSettings
from .lineVolumeVisualizerView import LineVolumeVisualizerView, LineVolumeVisualizerSettings
from .rectangleChromaVisualizerView import RectangleChromaVisualizerView, RectangleChromaVisualizerSettings
from .circleChromaVisualizerView import CircleChromeVisualizerView, CircleChromeVisualizerSettings
from .lineChromaVisualizerView import LineChromaVisualizerView, LineChromaVisualizerSettings
from .waveformVisualizerView import WaveformVisualizerView, WaveformVisualizerSettings
from .combinedVisualizerView import CombinedVisualizerView, CombinedVisualizerSettings

from .renderDialog import RenderDialog
from .mainWindow import MainWindow

