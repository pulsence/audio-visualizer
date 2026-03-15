"""Waveform display widget using pyqtgraph.

Shows the audio waveform, subtitle timing regions as colored rectangles,
a playback cursor line, and supports click-to-seek and selection
highlighting.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from audio_visualizer.ui.tabs.srtEdit.document import SubtitleEntry

logger = logging.getLogger(__name__)

# Region colour palette (cycles for visual distinction)
_REGION_COLORS = [
    (70, 130, 180, 50),   # steel blue
    (60, 179, 113, 50),   # medium sea green
    (255, 165, 0, 50),    # orange
    (147, 112, 219, 50),  # medium purple
    (240, 128, 128, 50),  # light coral
]

_HIGHLIGHT_COLOR = (255, 255, 0, 80)  # yellow highlight


class WaveformView(QWidget):
    """Audio waveform viewer with subtitle region overlay.

    Signals:
        seek_requested(int): Emitted when the user clicks the waveform.
            Payload is the requested position in milliseconds.
    """

    seek_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._sample_rate: int = 0
        self._duration_ms: int = 0
        self._regions: list[pg.LinearRegionItem] = []
        self._highlight_region: Optional[pg.LinearRegionItem] = None
        self._cursor_line: Optional[pg.InfiniteLine] = None

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setBackground("k")
        self._plot_widget.showGrid(x=True, y=False, alpha=0.3)
        self._plot_widget.setLabel("bottom", "Time (s)")
        self._plot_widget.setLabel("left", "Amplitude")
        self._plot_widget.setMouseEnabled(x=True, y=False)
        self._plot_widget.setDownsampling(auto=True, mode="peak")
        self._plot_widget.setClipToView(True)

        # Waveform plot item
        self._waveform_item: Optional[pg.PlotDataItem] = None

        # Click-to-seek
        self._plot_widget.scene().sigMouseClicked.connect(self._on_mouse_clicked)

        layout.addWidget(self._plot_widget)
        self.setLayout(layout)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_waveform(self, samples: np.ndarray, sample_rate: int) -> None:
        """Load and display an audio waveform.

        Args:
            samples: 1-D numpy array of audio samples (mono).
            sample_rate: Sample rate in Hz.
        """
        self._sample_rate = sample_rate
        num_samples = len(samples)
        self._duration_ms = int((num_samples / sample_rate) * 1000) if sample_rate > 0 else 0

        # Create time axis in seconds
        time_axis = np.linspace(0, num_samples / sample_rate, num_samples, dtype=np.float32)

        # Normalize samples to [-1, 1]
        peak = np.max(np.abs(samples))
        if peak > 0:
            normalized = samples.astype(np.float32) / peak
        else:
            normalized = samples.astype(np.float32)

        # Clear and redraw
        self._plot_widget.clear()
        self._waveform_item = self._plot_widget.plot(
            time_axis, normalized,
            pen=pg.mkPen(color=(0, 180, 230), width=1),
        )
        self._plot_widget.setXRange(0, num_samples / sample_rate)
        self._plot_widget.setYRange(-1.1, 1.1)

        # Restore cursor line
        self._cursor_line = pg.InfiniteLine(
            pos=0, angle=90,
            pen=pg.mkPen(color="r", width=2),
            movable=False,
        )
        self._plot_widget.addItem(self._cursor_line)

        self._regions.clear()
        self._highlight_region = None
        logger.debug(
            "Waveform loaded: %d samples, %d Hz, %.1f s",
            num_samples, sample_rate, num_samples / sample_rate,
        )

    def set_regions(self, entries: list[SubtitleEntry]) -> None:
        """Draw subtitle timing regions on the waveform.

        Args:
            entries: List of SubtitleEntry objects to visualize.
        """
        # Remove existing regions
        for region in self._regions:
            self._plot_widget.removeItem(region)
        self._regions.clear()

        if self._highlight_region is not None:
            self._plot_widget.removeItem(self._highlight_region)
            self._highlight_region = None

        for i, entry in enumerate(entries):
            start_s = entry.start_ms / 1000.0
            end_s = entry.end_ms / 1000.0
            color = _REGION_COLORS[i % len(_REGION_COLORS)]
            region = pg.LinearRegionItem(
                values=(start_s, end_s),
                movable=False,
                brush=pg.mkBrush(*color),
            )
            region.setZValue(-10)
            self._plot_widget.addItem(region)
            self._regions.append(region)

    def set_cursor(self, ms: int) -> None:
        """Move the playback cursor to the given position.

        Args:
            ms: Playback position in milliseconds.
        """
        if self._cursor_line is not None:
            self._cursor_line.setValue(ms / 1000.0)

    def highlight_region(self, index: int) -> None:
        """Highlight the subtitle region at *index*.

        Args:
            index: 0-based index into the current regions list.
        """
        # Remove previous highlight
        if self._highlight_region is not None:
            self._plot_widget.removeItem(self._highlight_region)
            self._highlight_region = None

        if index < 0 or index >= len(self._regions):
            return

        source = self._regions[index]
        lo, hi = source.getRegion()
        self._highlight_region = pg.LinearRegionItem(
            values=(lo, hi),
            movable=False,
            brush=pg.mkBrush(*_HIGHLIGHT_COLOR),
        )
        self._highlight_region.setZValue(-5)
        self._plot_widget.addItem(self._highlight_region)

        # Ensure the highlighted region is visible
        padding = (hi - lo) * 0.5
        self._plot_widget.setXRange(lo - padding, hi + padding, padding=0)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_mouse_clicked(self, event) -> None:
        """Handle click on the plot scene to emit seek_requested."""
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.scenePos()
        mouse_point = self._plot_widget.plotItem.vb.mapSceneToView(pos)
        time_s = mouse_point.x()
        time_ms = max(0, int(time_s * 1000))
        if time_ms <= self._duration_ms:
            self.seek_requested.emit(time_ms)
