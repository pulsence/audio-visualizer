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
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QLabel, QScrollBar, QStackedLayout, QVBoxLayout, QWidget

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
        play_pause_requested(): Emitted when Space is pressed while focused.
        boundary_moved(int, str, int): Emitted when a region boundary is
            dragged. (entry_index, 'start'|'end', new_ms)
    """

    seek_requested = Signal(int)
    play_pause_requested = Signal()
    boundary_moved = Signal(int, str, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._sample_rate: int = 0
        self._duration_ms: int = 0
        self._duration_s: float = 0.0
        self._regions: list[pg.LinearRegionItem] = []
        self._highlight_region: Optional[pg.LinearRegionItem] = None
        self._cursor_line: Optional[pg.InfiniteLine] = None
        self._updating_scrollbar = False

        # Accept focus so Space key works
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

        # Overlay label for loading/error messages
        self._overlay_label = QLabel()
        self._overlay_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._overlay_label.setStyleSheet("color: #aaa; font-size: 14px;")
        self._overlay_label.hide()

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

        # Track range changes for scrollbar sync
        self._plot_widget.sigXRangeChanged.connect(self._on_x_range_changed)

        layout.addWidget(self._overlay_label)
        layout.addWidget(self._plot_widget)

        # Horizontal scrollbar for panned/zoomed waveform
        self._h_scrollbar = QScrollBar(Qt.Orientation.Horizontal)
        self._h_scrollbar.setVisible(False)
        self._h_scrollbar.valueChanged.connect(self._on_scrollbar_moved)
        layout.addWidget(self._h_scrollbar)

        self.setLayout(layout)

        # Install event filter on the plot viewport to intercept Ctrl+wheel
        # before pyqtgraph processes it (the viewport is the actual mouse
        # event target, so WaveformView.wheelEvent never fires for it).
        self._plot_widget.viewport().installEventFilter(self)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def has_regions(self) -> bool:
        """Return True if subtitle regions are currently displayed."""
        return len(self._regions) > 0

    def clear_regions(self) -> None:
        """Remove all subtitle regions from the waveform."""
        for region in self._regions:
            self._plot_widget.removeItem(region)
        self._regions.clear()
        if self._highlight_region is not None:
            self._plot_widget.removeItem(self._highlight_region)
            self._highlight_region = None

    def set_loading_message(self, message: str) -> None:
        """Show a loading message overlay, hiding the plot widget."""
        self._overlay_label.setText(message)
        self._overlay_label.show()
        self._plot_widget.hide()

    def set_error_message(self, message: str) -> None:
        """Show an error message overlay, hiding the plot widget."""
        self._overlay_label.setText(message)
        self._overlay_label.setStyleSheet("color: #e55; font-size: 14px;")
        self._overlay_label.show()
        self._plot_widget.hide()

    def clear_message(self) -> None:
        """Hide the overlay message and show the plot widget."""
        self._overlay_label.hide()
        self._overlay_label.setStyleSheet("color: #aaa; font-size: 14px;")
        self._plot_widget.show()

    def load_waveform(self, samples: np.ndarray, sample_rate: int) -> None:
        """Load and display an audio waveform.

        Args:
            samples: 1-D numpy array of audio samples (mono).
            sample_rate: Sample rate in Hz.
        """
        self._sample_rate = sample_rate
        num_samples = len(samples)
        self._duration_ms = int((num_samples / sample_rate) * 1000) if sample_rate > 0 else 0
        self._duration_s = num_samples / sample_rate if sample_rate > 0 else 0.0

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
        self.clear_message()
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
                movable=True,
                brush=pg.mkBrush(*color),
            )
            region.setZValue(-10)
            # Track boundary drags
            region_idx = i
            region.sigRegionChangeFinished.connect(
                lambda r, idx=region_idx: self._on_region_boundary_moved(idx, r)
            )
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
        """Handle click on the plot scene to emit seek_requested and take focus."""
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.scenePos()
        mouse_point = self._plot_widget.plotItem.vb.mapSceneToView(pos)
        time_s = mouse_point.x()
        time_ms = max(0, int(time_s * 1000))
        if time_ms <= self._duration_ms:
            self.seek_requested.emit(time_ms)

    def _on_region_boundary_moved(self, index: int, region: pg.LinearRegionItem) -> None:
        """Emit boundary_moved when the user finishes dragging a region."""
        lo, hi = region.getRegion()
        start_ms = max(0, int(lo * 1000))
        end_ms = max(start_ms + 1, int(hi * 1000))
        self.boundary_moved.emit(index, "start", start_ms)
        self.boundary_moved.emit(index, "end", end_ms)

    def _on_x_range_changed(self, view_box, range_) -> None:
        """Update the horizontal scrollbar when the visible range changes."""
        if self._duration_s <= 0 or self._updating_scrollbar:
            return
        lo, hi = range_
        visible = hi - lo
        total = self._duration_s
        if visible >= total * 0.99:
            self._h_scrollbar.setVisible(False)
            return
        self._h_scrollbar.setVisible(True)
        self._updating_scrollbar = True
        # Scrollbar range in ms (integer)
        page_ms = int(visible * 1000)
        total_ms = int(total * 1000)
        self._h_scrollbar.setMinimum(0)
        self._h_scrollbar.setMaximum(max(0, total_ms - page_ms))
        self._h_scrollbar.setPageStep(page_ms)
        self._h_scrollbar.setValue(max(0, int(lo * 1000)))
        self._updating_scrollbar = False

    def _on_scrollbar_moved(self, value: int) -> None:
        """Pan the waveform view to match the scrollbar position."""
        if self._updating_scrollbar or self._duration_s <= 0:
            return
        self._updating_scrollbar = True
        vb = self._plot_widget.plotItem.vb
        lo, hi = vb.viewRange()[0]
        visible = hi - lo
        new_lo = value / 1000.0
        vb.setXRange(new_lo, new_lo + visible, padding=0)
        self._updating_scrollbar = False

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle Space to toggle playback."""
        if event.key() == Qt.Key.Key_Space:
            self.play_pause_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, obj, event):
        """Intercept wheel on the plot viewport: normal = pan, Ctrl = zoom (pyqtgraph default)."""
        if obj is self._plot_widget.viewport() and event.type() == event.Type.Wheel:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                # Let pyqtgraph handle zoom
                return False
            else:
                # Horizontal pan
                delta = event.angleDelta().y()
                vb = self._plot_widget.plotItem.vb
                lo, hi = vb.viewRange()[0]
                visible = hi - lo
                shift = visible * 0.1 * (-1 if delta > 0 else 1)
                new_lo = max(0, lo + shift)
                new_hi = new_lo + visible
                if self._duration_s > 0 and new_hi > self._duration_s:
                    new_hi = self._duration_s
                    new_lo = max(0, new_hi - visible)
                vb.setXRange(new_lo, new_hi, padding=0)
                return True  # consume the event
        return super().eventFilter(obj, event)

    def wheelEvent(self, event) -> None:
        """Normal wheel: horizontal pan. Ctrl+wheel: zoom (default)."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Let default handle zoom
            super().wheelEvent(event)
        else:
            # Horizontal pan
            delta = event.angleDelta().y()
            vb = self._plot_widget.plotItem.vb
            lo, hi = vb.viewRange()[0]
            visible = hi - lo
            shift = visible * 0.1 * (-1 if delta > 0 else 1)
            vb.setXRange(lo + shift, hi + shift, padding=0)
            event.accept()
