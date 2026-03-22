"""Waveform display widget using pyqtgraph.

Shows the audio waveform, subtitle timing regions as colored rectangles,
a playback cursor line, and supports click-to-seek and selection
highlighting.  Supports both segment and word view modes, hover-based
border expansion, pan-to-segment navigation, context menus, and
drag-to-select for new segment creation.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollBar,
    QVBoxLayout,
    QWidget,
)

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

_WORD_REGION_COLORS = [
    (100, 180, 255, 40),  # light blue
    (100, 220, 160, 40),  # light green
    (255, 200, 80, 40),   # light amber
    (180, 150, 255, 40),  # light purple
    (255, 160, 160, 40),  # light pink
]

_HIGHLIGHT_COLOR = (255, 255, 0, 80)  # yellow highlight

_NORMAL_BORDER_WIDTH = 1
_HOVER_BORDER_WIDTH = 4

_DRAG_SELECT_COLOR = (255, 255, 255, 30)


class _HoverableRegionItem(pg.LinearRegionItem):
    """LinearRegionItem with hover border expansion.

    Widens boundaries on hover for easier grab targeting.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptHoverEvents(True)

    def hoverEnterEvent(self, ev):
        for line in self.lines:
            pen = line.pen()
            pen.setWidth(_HOVER_BORDER_WIDTH)
            line.setPen(pen)
        super().hoverEnterEvent(ev)

    def hoverLeaveEvent(self, ev):
        for line in self.lines:
            pen = line.pen()
            pen.setWidth(_NORMAL_BORDER_WIDTH)
            line.setPen(pen)
        super().hoverLeaveEvent(ev)


class WaveformView(QWidget):
    """Audio waveform viewer with subtitle region overlay.

    Signals:
        seek_requested(int): Emitted when the user clicks the waveform.
            Payload is the requested position in milliseconds.
        play_pause_requested(): Emitted when Space is pressed while focused.
        boundary_moved(int, str, int): Emitted when a segment region boundary
            is dragged. (entry_index, 'start'|'end', new_ms)
        word_boundary_moved(int, int, float, float): Emitted when a word
            region boundary is dragged.
            (entry_index, word_index, new_start_s, new_end_s)
        context_action(str, int): Emitted for context menu actions.
            (action_name, entry_index)
        drag_select_region(float, float): Emitted when user completes a
            drag selection in empty space. (start_s, end_s)
        word_region_clicked(int, int): Emitted when a word region is clicked.
            (entry_index, word_index)
    """

    seek_requested = Signal(int)
    play_pause_requested = Signal()
    boundary_moved = Signal(int, str, int)
    word_boundary_moved = Signal(int, int, float, float)
    context_action = Signal(str, int)
    drag_select_region = Signal(float, float)
    word_region_clicked = Signal(int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._sample_rate: int = 0
        self._duration_ms: int = 0
        self._duration_s: float = 0.0
        self._regions: list[_HoverableRegionItem] = []
        self._word_regions: list[_HoverableRegionItem] = []
        self._word_region_map: list[tuple[int, int]] = []  # (entry_idx, word_idx)
        self._highlight_region: Optional[pg.LinearRegionItem] = None
        self._cursor_line: Optional[pg.InfiniteLine] = None
        self._updating_scrollbar = False
        self._show_words = False
        self._entries: list[SubtitleEntry] = []

        # Drag-to-select state
        self._drag_selecting = False
        self._drag_start_s: float = 0.0
        self._drag_region: Optional[pg.LinearRegionItem] = None

        # Accept focus so Space key works
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

        # Overlay label for loading/error messages
        self._overlay_label = QLabel()
        self._overlay_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._overlay_label.setStyleSheet("color: #aaa; font-size: 14px;")
        self._overlay_label.hide()

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)

        # Toggle bar for word view
        toggle_layout = QHBoxLayout()
        toggle_layout.setContentsMargins(4, 2, 4, 2)
        self._word_toggle = QCheckBox("Show Words")
        self._word_toggle.setChecked(False)
        self._word_toggle.toggled.connect(self._on_word_toggle)
        toggle_layout.addWidget(self._word_toggle)
        toggle_layout.addStretch()
        root_layout.addLayout(toggle_layout)

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

        # Click-to-seek and context menu
        self._plot_widget.scene().sigMouseClicked.connect(self._on_mouse_clicked)

        # Track range changes for scrollbar sync
        self._plot_widget.sigXRangeChanged.connect(self._on_x_range_changed)

        root_layout.addWidget(self._overlay_label)
        root_layout.addWidget(self._plot_widget)

        # Horizontal scrollbar for panned/zoomed waveform
        self._h_scrollbar = QScrollBar(Qt.Orientation.Horizontal)
        self._h_scrollbar.setVisible(False)
        self._h_scrollbar.valueChanged.connect(self._on_scrollbar_moved)
        root_layout.addWidget(self._h_scrollbar)

        self.setLayout(root_layout)

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
        self._clear_word_regions()
        if self._highlight_region is not None:
            self._plot_widget.removeItem(self._highlight_region)
            self._highlight_region = None
        self._dismiss_drag_selection()

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
        self._word_regions.clear()
        self._word_region_map.clear()
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
        self._entries = entries

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
            region = _HoverableRegionItem(
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

        # Refresh word regions if word view is active
        if self._show_words:
            self._rebuild_word_regions()

    def set_cursor(self, ms: int) -> None:
        """Move the playback cursor to the given position.

        Args:
            ms: Playback position in milliseconds.
        """
        if self._cursor_line is not None:
            self._cursor_line.setValue(ms / 1000.0)

    def get_cursor_ms(self) -> int:
        """Return the current playback cursor position in milliseconds."""
        if self._cursor_line is not None:
            return max(0, int(self._cursor_line.value() * 1000))
        return 0

    def highlight_region(self, index: int) -> None:
        """Highlight the subtitle region at *index* with pan-to-segment.

        Preserves the current zoom level when the segment fits in view.
        Centers the segment when it fits.  Only zooms out when the
        segment is wider than the visible window.

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

        # Pan-to-segment logic: preserve zoom when possible
        vb = self._plot_widget.plotItem.vb
        current_lo, current_hi = vb.viewRange()[0]
        visible_width = current_hi - current_lo
        segment_width = hi - lo

        if segment_width <= visible_width:
            # Segment fits: center it in view without changing zoom
            center = (lo + hi) / 2.0
            new_lo = center - visible_width / 2.0
            new_hi = center + visible_width / 2.0
            # Clamp to waveform bounds
            if new_lo < 0:
                new_lo = 0
                new_hi = visible_width
            if new_hi > self._duration_s and self._duration_s > 0:
                new_hi = self._duration_s
                new_lo = max(0, new_hi - visible_width)
            vb.setXRange(new_lo, new_hi, padding=0)
        else:
            # Segment wider than view: zoom out to show it
            padding = segment_width * 0.5
            self._plot_widget.setXRange(lo - padding, hi + padding, padding=0)

    def highlight_word(self, entry_index: int, word_index: int) -> None:
        """Visually select the word region for the given entry/word pair."""
        for i, (ei, wi) in enumerate(self._word_region_map):
            if ei == entry_index and wi == word_index:
                region = self._word_regions[i]
                lo, hi = region.getRegion()
                # Flash the region with brighter color
                region.setBrush(pg.mkBrush(255, 255, 100, 60))
                break

    # ------------------------------------------------------------------
    # Word view
    # ------------------------------------------------------------------

    def _on_word_toggle(self, checked: bool) -> None:
        """Toggle between segment and word view."""
        self._show_words = checked
        if checked:
            self._rebuild_word_regions()
        else:
            self._clear_word_regions()

    def _rebuild_word_regions(self) -> None:
        """Create word-level LinearRegionItems for all visible entries."""
        self._clear_word_regions()
        if not self._entries:
            return

        for entry_idx, entry in enumerate(self._entries):
            if not entry.words:
                continue
            for word_idx, word in enumerate(entry.words):
                color = _WORD_REGION_COLORS[(entry_idx + word_idx) % len(_WORD_REGION_COLORS)]
                region = _HoverableRegionItem(
                    values=(word.start, word.end),
                    movable=True,
                    brush=pg.mkBrush(*color),
                )
                region.setZValue(-8)
                ei, wi = entry_idx, word_idx
                region.sigRegionChangeFinished.connect(
                    lambda r, _ei=ei, _wi=wi: self._on_word_region_moved(_ei, _wi, r)
                )
                # Click tracking for selection sync
                region.sigRegionChanged.connect(
                    lambda r, _ei=ei, _wi=wi: None  # drag tracking
                )
                self._plot_widget.addItem(region)
                self._word_regions.append(region)
                self._word_region_map.append((entry_idx, word_idx))

    def _clear_word_regions(self) -> None:
        """Remove all word regions from the plot."""
        for region in self._word_regions:
            self._plot_widget.removeItem(region)
        self._word_regions.clear()
        self._word_region_map.clear()

    def _on_word_region_moved(
        self, entry_index: int, word_index: int, region: _HoverableRegionItem
    ) -> None:
        """Emit word_boundary_moved when user finishes dragging a word region."""
        lo, hi = region.getRegion()
        self.word_boundary_moved.emit(entry_index, word_index, lo, hi)

    # ------------------------------------------------------------------
    # Drag-to-select for new segment creation
    # ------------------------------------------------------------------

    def _start_drag_select(self, pos_s: float) -> None:
        """Begin a drag-selection region at the given time."""
        self._dismiss_drag_selection()
        self._drag_selecting = True
        self._drag_start_s = pos_s
        self._drag_region = pg.LinearRegionItem(
            values=(pos_s, pos_s),
            movable=False,
            brush=pg.mkBrush(*_DRAG_SELECT_COLOR),
        )
        self._drag_region.setZValue(-3)
        self._plot_widget.addItem(self._drag_region)

    def _update_drag_select(self, pos_s: float) -> None:
        """Update the drag-selection endpoint."""
        if self._drag_region is not None:
            lo = min(self._drag_start_s, pos_s)
            hi = max(self._drag_start_s, pos_s)
            self._drag_region.setRegion((lo, hi))

    def _finish_drag_select(self, pos_s: float) -> None:
        """Finish drag-selection and keep the region visible."""
        self._drag_selecting = False
        if self._drag_region is not None:
            lo = min(self._drag_start_s, pos_s)
            hi = max(self._drag_start_s, pos_s)
            if hi - lo < 0.05:
                # Too small, dismiss
                self._dismiss_drag_selection()
                return
            self._drag_region.setRegion((lo, hi))

    def _dismiss_drag_selection(self) -> None:
        """Remove the temporary drag-selection region."""
        self._drag_selecting = False
        if self._drag_region is not None:
            self._plot_widget.removeItem(self._drag_region)
            self._drag_region = None

    def _is_in_empty_space(self, time_s: float) -> bool:
        """Return True if time_s does not fall inside any segment region."""
        for region in self._regions:
            lo, hi = region.getRegion()
            if lo <= time_s <= hi:
                return False
        return True

    def _region_index_at(self, time_s: float) -> int:
        """Return the index of the region containing time_s, or -1."""
        for i, region in enumerate(self._regions):
            lo, hi = region.getRegion()
            if lo <= time_s <= hi:
                return i
        return -1

    # ------------------------------------------------------------------
    # Context menus
    # ------------------------------------------------------------------

    def _show_segment_context_menu(self, index: int, global_pos) -> None:
        """Show context menu for a segment region."""
        menu = QMenu(self)
        menu.addAction("Split at Playhead", lambda: self.context_action.emit("split_at_playhead", index))
        menu.addAction("Merge with Next", lambda: self.context_action.emit("merge_next", index))
        menu.addAction("Merge with Previous", lambda: self.context_action.emit("merge_prev", index))
        menu.addSeparator()
        menu.addAction("Delete Segment", lambda: self.context_action.emit("delete", index))
        menu.addAction("Edit Text", lambda: self.context_action.emit("edit_text", index))
        menu.exec(global_pos)

    def _show_drag_select_context_menu(self, global_pos) -> None:
        """Show context menu for a drag-selection region."""
        if self._drag_region is None:
            return
        lo, hi = self._drag_region.getRegion()
        menu = QMenu(self)
        menu.addAction("Create Blank Segment", lambda: self._emit_drag_create(lo, hi))
        menu.addAction("Create from Clipboard", lambda: self._emit_drag_create(lo, hi, from_clipboard=True))
        menu.addSeparator()
        menu.addAction("Cancel", self._dismiss_drag_selection)
        menu.exec(global_pos)

    def _emit_drag_create(self, lo: float, hi: float, from_clipboard: bool = False) -> None:
        """Emit the drag_select_region signal and dismiss the selection."""
        self.drag_select_region.emit(lo, hi)
        self._dismiss_drag_selection()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_mouse_clicked(self, event) -> None:
        """Handle click on the plot scene."""
        self.setFocus(Qt.FocusReason.MouseFocusReason)

        pos = event.scenePos()
        mouse_point = self._plot_widget.plotItem.vb.mapSceneToView(pos)
        time_s = mouse_point.x()
        time_ms = max(0, int(time_s * 1000))

        # Right-click context menu
        if event.button() == Qt.MouseButton.RightButton:
            global_pos = self._plot_widget.mapToGlobal(
                self._plot_widget.mapFromScene(event.scenePos())
            )
            # Check for drag selection first
            if self._drag_region is not None:
                lo, hi = self._drag_region.getRegion()
                if lo <= time_s <= hi:
                    self._show_drag_select_context_menu(global_pos)
                    return
            # Check if right-click is on a segment
            seg_idx = self._region_index_at(time_s)
            if seg_idx >= 0:
                self._show_segment_context_menu(seg_idx, global_pos)
                return
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        # Dismiss drag selection on click outside it
        if self._drag_region is not None:
            lo, hi = self._drag_region.getRegion()
            if not (lo <= time_s <= hi):
                self._dismiss_drag_selection()

        # Check for word region click
        for i, (ei, wi) in enumerate(self._word_region_map):
            if i < len(self._word_regions):
                wlo, whi = self._word_regions[i].getRegion()
                if wlo <= time_s <= whi:
                    self.word_region_clicked.emit(ei, wi)

        # Seek
        if time_ms <= self._duration_ms:
            self.seek_requested.emit(time_ms)

    def _on_region_boundary_moved(self, index: int, region: _HoverableRegionItem) -> None:
        """Emit boundary_moved when the user finishes dragging a region.

        Applies overlap clamping before emitting.
        """
        lo, hi = region.getRegion()
        start_ms = max(0, int(lo * 1000))
        end_ms = max(start_ms + 1, int(hi * 1000))

        # Clamp against neighbors to prevent overlap
        if index > 0 and index - 1 < len(self._regions):
            prev_lo, prev_hi = self._regions[index - 1].getRegion()
            prev_end_ms = int(prev_hi * 1000)
            if start_ms < prev_end_ms:
                start_ms = prev_end_ms
        if index < len(self._regions) - 1:
            next_lo, next_hi = self._regions[index + 1].getRegion()
            next_start_ms = int(next_lo * 1000)
            if end_ms > next_start_ms:
                end_ms = next_start_ms
        if end_ms <= start_ms:
            end_ms = start_ms + 1

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

    def _pan_horizontal(self, delta: int) -> None:
        """Pan the visible waveform range left/right by one wheel step."""
        if self._duration_s <= 0:
            return
        vb = self._plot_widget.plotItem.vb
        lo, hi = vb.viewRange()[0]
        visible = hi - lo
        shift = visible * 0.1 * (-1 if delta > 0 else 1)
        new_lo = max(0.0, lo + shift)
        new_hi = new_lo + visible
        if new_hi > self._duration_s:
            new_hi = self._duration_s
            new_lo = max(0.0, new_hi - visible)
        vb.setXRange(new_lo, new_hi, padding=0)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle Space to toggle playback and Escape to dismiss selection."""
        if event.key() == Qt.Key.Key_Space:
            self.play_pause_requested.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self._dismiss_drag_selection()
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, obj, event):
        """Intercept wheel on the plot viewport: normal = pan, Ctrl = zoom (pyqtgraph default)."""
        if obj is self._plot_widget.viewport() and event.type() == event.Type.Wheel:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                # Let pyqtgraph handle zoom
                return False
            self._pan_horizontal(event.angleDelta().y())
            return True  # consume the event

        # Drag-to-select detection on the plot viewport
        if obj is self._plot_widget.viewport():
            if event.type() == event.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    pos = self._plot_widget.plotItem.vb.mapSceneToView(
                        self._plot_widget.mapToScene(event.pos())
                    )
                    time_s = pos.x()
                    if self._is_in_empty_space(time_s) and self._drag_region is None:
                        self._start_drag_select(time_s)
                        # Don't consume - let click-to-seek still work

            elif event.type() == event.Type.MouseMove:
                if self._drag_selecting:
                    pos = self._plot_widget.plotItem.vb.mapSceneToView(
                        self._plot_widget.mapToScene(event.pos())
                    )
                    self._update_drag_select(pos.x())

            elif event.type() == event.Type.MouseButtonRelease:
                if self._drag_selecting:
                    pos = self._plot_widget.plotItem.vb.mapSceneToView(
                        self._plot_widget.mapToScene(event.pos())
                    )
                    self._finish_drag_select(pos.x())

        return super().eventFilter(obj, event)

    def wheelEvent(self, event) -> None:
        """Normal wheel: horizontal pan. Ctrl+wheel: zoom (default)."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Let default handle zoom
            super().wheelEvent(event)
        else:
            self._pan_horizontal(event.angleDelta().y())
            event.accept()
