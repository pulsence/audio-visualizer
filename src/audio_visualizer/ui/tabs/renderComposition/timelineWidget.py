"""Timeline widget for Render Composition.

Provides a visual timeline showing visual and audio layers as horizontal
bars on separate tracks. Supports drag-to-move and handle-based trimming.
"""
from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QWidget, QScrollBar, QVBoxLayout

logger = logging.getLogger(__name__)

# Colors for visual and audio tracks
_VISUAL_TRACK_COLOR = QColor(70, 130, 180, 180)  # steel blue
_AUDIO_TRACK_COLOR = QColor(60, 179, 113, 180)   # medium sea green
_SELECTED_BORDER = QColor(255, 255, 0)            # yellow
_HANDLE_WIDTH = 6
_TRACK_HEIGHT = 30
_TRACK_SPACING = 4
_HEADER_WIDTH = 100
_SNAP_THRESHOLD_MS = 200


class TimelineItem:
    """Represents a single item on the timeline."""
    def __init__(self, item_id: str, display_name: str, start_ms: int,
                 end_ms: int, track_type: str = "visual", enabled: bool = True,
                 source_duration_ms: int = 0):
        self.item_id = item_id
        self.display_name = display_name
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.track_type = track_type  # "visual" or "audio"
        self.enabled = enabled
        self.source_duration_ms = source_duration_ms


class TimelineWidget(QWidget):
    """Visual timeline for composition layers.

    Signals
    -------
    item_selected(str)
        Emitted when a timeline item is clicked. Payload is the item_id.
    item_moved(str, int, int)
        Emitted when an item is dragged. (item_id, new_start_ms, new_end_ms)
    item_trimmed(str, str, int)
        Emitted when an item handle is dragged. (item_id, 'start'|'end', new_ms)
    """

    item_selected = Signal(str)
    item_moved = Signal(str, int, int)
    item_trimmed = Signal(str, str, int)
    item_reordered = Signal(str, int)  # (item_id, new_visual_index)
    scroll_state_changed = Signal(int, int, int, int)
    playhead_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(120)
        self.setMouseTracking(True)

        self._items: list[TimelineItem] = []
        self._selected_id: str | None = None
        self._duration_ms: int = 10000  # default 10 seconds
        self._pixels_per_ms: float = 0.1
        self._scroll_offset: int = 0

        self._playhead_ms: int = 0

        # Snap guide state
        self._snap_line_x: float | None = None

        # Drag state
        self._dragging: bool = False
        self._drag_item_id: str | None = None
        self._drag_mode: str = ""  # "move", "trim_start", "trim_end"
        self._drag_start_x: int = 0
        self._drag_start_y: int = 0
        self._drag_original_start: int = 0
        self._drag_original_end: int = 0
        self._drag_original_visual_index: int = -1

    def set_items(self, items: list[TimelineItem]) -> None:
        """Set the timeline items and refresh."""
        self._items = items
        self._recalc_duration()
        self.update()

    def set_selected(self, item_id: str | None) -> None:
        """Set the selected item."""
        self._selected_id = item_id
        self.update()

    def set_playhead_ms(self, ms: int) -> None:
        """Set the playhead position in milliseconds."""
        self._playhead_ms = max(0, ms)
        self.update()

    def _recalc_duration(self) -> None:
        """Recalculate duration from items."""
        if self._items:
            self._duration_ms = max(
                max((item.end_ms for item in self._items), default=10000),
                10000
            )
        else:
            self._duration_ms = 10000
        self._clamp_scroll()

    def _snap_value(self, ms: int, exclude_id: str) -> int:
        """Return *ms* snapped to the nearest start/end edge of another item.

        If no edge is within ``_SNAP_THRESHOLD_MS``, return *ms* unchanged.
        """
        edges: list[int] = []
        for item in self._items:
            if item.item_id == exclude_id:
                continue
            edges.append(item.start_ms)
            edges.append(item.end_ms)

        if not edges:
            return ms

        closest = min(edges, key=lambda e: abs(e - ms))
        if abs(closest - ms) <= _SNAP_THRESHOLD_MS:
            return closest
        return ms

    # ------------------------------------------------------------------
    # Scroll / zoom API
    # ------------------------------------------------------------------

    def set_scroll_offset(self, ms: int) -> None:
        self._scroll_offset = max(0, ms)
        self._clamp_scroll()
        self._emit_scroll_state()
        self.update()

    def scroll_offset(self) -> int:
        return self._scroll_offset

    def set_pixels_per_ms(self, value: float) -> None:
        self._pixels_per_ms = max(0.02, min(2.0, value))
        self._clamp_scroll()
        self._emit_scroll_state()
        self.update()

    def pixels_per_ms(self) -> float:
        return self._pixels_per_ms

    def _visible_duration_ms(self) -> int:
        available = max(1, self.width() - _HEADER_WIDTH)
        if self._pixels_per_ms <= 0:
            return self._duration_ms
        return max(1, int(available / self._pixels_per_ms))

    def _clamp_scroll(self) -> None:
        max_offset = max(0, self._duration_ms - self._visible_duration_ms())
        self._scroll_offset = max(0, min(self._scroll_offset, max_offset))

    def _emit_scroll_state(self) -> None:
        visible = self._visible_duration_ms()
        max_val = max(0, self._duration_ms - visible)
        self.scroll_state_changed.emit(0, max_val, visible, self._scroll_offset)

    def _ms_to_x(self, ms: int) -> float:
        """Convert milliseconds to pixel X coordinate."""
        return _HEADER_WIDTH + (ms - self._scroll_offset) * self._pixels_per_ms

    def _x_to_ms(self, x: float) -> int:
        """Convert pixel X coordinate to milliseconds."""
        if self._pixels_per_ms <= 0:
            return 0
        ms = int((x - _HEADER_WIDTH) / self._pixels_per_ms) + self._scroll_offset
        return max(0, ms)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), QColor(40, 40, 40))

        # Draw time ruler
        self._draw_ruler(painter)

        # Separate items by track type
        visual_items = [i for i in self._items if i.track_type == "visual"]
        audio_items = [i for i in self._items if i.track_type == "audio"]

        y_offset = 25  # After ruler

        # Draw visual track label
        painter.setPen(QPen(QColor(200, 200, 200)))
        painter.drawText(5, y_offset + _TRACK_HEIGHT // 2 + 4, "Visual")

        # Draw visual items
        for i, item in enumerate(visual_items):
            rect = self._get_item_rect(item, y_offset + i * (_TRACK_HEIGHT + _TRACK_SPACING))
            self._draw_item(painter, item, rect)

        y_offset += max(len(visual_items), 1) * (_TRACK_HEIGHT + _TRACK_SPACING) + 10

        # Draw audio track label
        painter.setPen(QPen(QColor(200, 200, 200)))
        painter.drawText(5, y_offset + _TRACK_HEIGHT // 2 + 4, "Audio")

        # Draw audio items
        for i, item in enumerate(audio_items):
            rect = self._get_item_rect(item, y_offset + i * (_TRACK_HEIGHT + _TRACK_SPACING))
            self._draw_item(painter, item, rect)

        # Draw snap guide line
        if self._snap_line_x is not None:
            snap_pen = QPen(QColor(255, 255, 0, 160))
            snap_pen.setStyle(Qt.PenStyle.DashLine)
            snap_pen.setWidth(1)
            painter.setPen(snap_pen)
            painter.drawLine(int(self._snap_line_x), 0,
                             int(self._snap_line_x), self.height())

        # Draw playhead
        playhead_x = self._ms_to_x(self._playhead_ms)
        if _HEADER_WIDTH <= playhead_x <= self.width():
            playhead_pen = QPen(QColor(255, 0, 0))
            playhead_pen.setWidth(2)
            painter.setPen(playhead_pen)
            painter.drawLine(int(playhead_x), 0, int(playhead_x), self.height())

        painter.end()

    def _draw_ruler(self, painter: QPainter) -> None:
        """Draw time ruler at top."""
        painter.setPen(QPen(QColor(150, 150, 150)))
        # Draw ticks every second
        step_ms = max(1000, self._duration_ms // 20)
        for ms in range(0, self._duration_ms + 1, step_ms):
            x = self._ms_to_x(ms)
            painter.drawLine(int(x), 0, int(x), 20)
            secs = ms / 1000
            if secs == int(secs):
                painter.drawText(int(x) + 2, 12, f"{int(secs)}s")
            else:
                painter.drawText(int(x) + 2, 12, f"{secs:.1f}s")

    def _get_item_rect(self, item: TimelineItem, y: int) -> QRectF:
        """Get the screen rectangle for a timeline item."""
        x1 = self._ms_to_x(item.start_ms)
        x2 = self._ms_to_x(item.end_ms)
        return QRectF(x1, y, max(x2 - x1, 4), _TRACK_HEIGHT)

    def _draw_item(self, painter: QPainter, item: TimelineItem, rect: QRectF) -> None:
        """Draw a single timeline item."""
        color = _VISUAL_TRACK_COLOR if item.track_type == "visual" else _AUDIO_TRACK_COLOR
        if not item.enabled:
            color = QColor(color.red(), color.green(), color.blue(), 60)

        painter.setBrush(QBrush(color))
        border = _SELECTED_BORDER if item.item_id == self._selected_id else QColor(100, 100, 100)
        painter.setPen(QPen(border, 2 if item.item_id == self._selected_id else 1))
        painter.drawRoundedRect(rect, 3, 3)

        # Draw name
        painter.setPen(QPen(QColor(255, 255, 255)))
        text_rect = rect.adjusted(4, 0, -4, 0)
        painter.drawText(text_rect.toRect(), Qt.AlignmentFlag.AlignVCenter, item.display_name)

        # Draw loop markers (grey dashed lines at source duration boundaries)
        if item.source_duration_ms > 0:
            span = item.end_ms - item.start_ms
            if span > item.source_duration_ms:
                loop_pen = QPen(QColor(160, 160, 160, 200))
                loop_pen.setStyle(Qt.PenStyle.DashLine)
                loop_pen.setWidth(1)
                painter.setPen(loop_pen)
                n = 1
                while True:
                    boundary_ms = item.start_ms + n * item.source_duration_ms
                    if boundary_ms >= item.end_ms:
                        break
                    bx = self._ms_to_x(boundary_ms)
                    if rect.left() < bx < rect.right():
                        painter.drawLine(int(bx), int(rect.top()), int(bx), int(rect.bottom()))
                    n += 1

        # Draw trim handles
        if item.item_id == self._selected_id:
            painter.setBrush(QBrush(QColor(255, 255, 255, 150)))
            painter.setPen(Qt.PenStyle.NoPen)
            # Left handle
            painter.drawRect(QRectF(rect.left(), rect.top(), _HANDLE_WIDTH, rect.height()))
            # Right handle
            painter.drawRect(QRectF(rect.right() - _HANDLE_WIDTH, rect.top(), _HANDLE_WIDTH, rect.height()))

    def _item_at(self, x: float, y: float) -> tuple[TimelineItem | None, str]:
        """Find item at position. Returns (item, hit_type) where hit_type is 'body', 'handle_start', 'handle_end', or ''."""
        visual_items = [i for i in self._items if i.track_type == "visual"]
        audio_items = [i for i in self._items if i.track_type == "audio"]

        y_offset = 25
        for i, item in enumerate(visual_items):
            rect = self._get_item_rect(item, y_offset + i * (_TRACK_HEIGHT + _TRACK_SPACING))
            if rect.contains(x, y):
                if x <= rect.left() + _HANDLE_WIDTH:
                    return item, "handle_start"
                elif x >= rect.right() - _HANDLE_WIDTH:
                    return item, "handle_end"
                return item, "body"

        y_offset += max(len(visual_items), 1) * (_TRACK_HEIGHT + _TRACK_SPACING) + 10
        for i, item in enumerate(audio_items):
            rect = self._get_item_rect(item, y_offset + i * (_TRACK_HEIGHT + _TRACK_SPACING))
            if rect.contains(x, y):
                if x <= rect.left() + _HANDLE_WIDTH:
                    return item, "handle_start"
                elif x >= rect.right() - _HANDLE_WIDTH:
                    return item, "handle_end"
                return item, "body"

        return None, ""

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)

        if event.position().x() >= _HEADER_WIDTH:
            # Update playhead on any left click in the timeline content area.
            self._playhead_ms = self._x_to_ms(event.position().x())
            self.playhead_changed.emit(self._playhead_ms)

        item, hit_type = self._item_at(event.position().x(), event.position().y())
        if item is not None:
            self._selected_id = item.item_id
            self.item_selected.emit(item.item_id)

            self._dragging = True
            self._drag_item_id = item.item_id
            self._drag_start_x = event.position().x()
            self._drag_start_y = event.position().y()
            self._drag_original_start = item.start_ms
            self._drag_original_end = item.end_ms

            # Record original visual index for reorder detection
            visual_items = [i for i in self._items if i.track_type == "visual"]
            self._drag_original_visual_index = -1
            for vi, vi_item in enumerate(visual_items):
                if vi_item.item_id == item.item_id:
                    self._drag_original_visual_index = vi
                    break

            if hit_type == "handle_start":
                self._drag_mode = "trim_start"
            elif hit_type == "handle_end":
                self._drag_mode = "trim_end"
            else:
                self._drag_mode = "move"
        else:
            self._selected_id = None
            self.item_selected.emit("")

        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self._dragging or self._drag_item_id is None:
            # Update cursor
            item, hit_type = self._item_at(event.position().x(), event.position().y())
            if hit_type in ("handle_start", "handle_end"):
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif hit_type == "body":
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            return

        dx = event.position().x() - self._drag_start_x
        delta_ms = self._x_to_ms(event.position().x()) - self._x_to_ms(self._drag_start_x)

        item = next((i for i in self._items if i.item_id == self._drag_item_id), None)
        if item is None:
            return

        self._snap_line_x = None

        if self._drag_mode == "move":
            new_start = max(0, self._drag_original_start + delta_ms)
            duration = self._drag_original_end - self._drag_original_start
            new_end = new_start + duration

            snapped_start = self._snap_value(new_start, item.item_id)
            snapped_end = self._snap_value(new_end, item.item_id)

            start_changed = snapped_start != new_start
            end_changed = snapped_end != new_end
            dist_start = abs(snapped_start - new_start) if start_changed else _SNAP_THRESHOLD_MS + 1
            dist_end = abs(snapped_end - new_end) if end_changed else _SNAP_THRESHOLD_MS + 1

            if dist_start <= dist_end and dist_start <= _SNAP_THRESHOLD_MS:
                item.start_ms = snapped_start
                item.end_ms = snapped_start + duration
                self._snap_line_x = self._ms_to_x(snapped_start)
            elif dist_end <= _SNAP_THRESHOLD_MS:
                item.end_ms = snapped_end
                item.start_ms = snapped_end - duration
                self._snap_line_x = self._ms_to_x(snapped_end)
            else:
                item.start_ms = new_start
                item.end_ms = new_start + duration

            # Vertical reorder: detect when a visual item is dragged to a different track row
            if item.track_type == "visual" and self._drag_original_visual_index >= 0:
                visual_items = [i for i in self._items if i.track_type == "visual"]
                y = event.position().y()
                y_base = 25  # after ruler
                track_step = _TRACK_HEIGHT + _TRACK_SPACING
                target_index = max(0, min(int((y - y_base) / track_step), len(visual_items) - 1))
                if target_index != self._drag_original_visual_index:
                    # Swap the item in the visual items list
                    old_idx = self._drag_original_visual_index
                    # Find and move in self._items
                    vis_ids = [vi.item_id for vi in visual_items]
                    dragged_id = item.item_id
                    if dragged_id in vis_ids:
                        vis_ids.remove(dragged_id)
                        vis_ids.insert(target_index, dragged_id)
                        # Rebuild self._items: visual in new order, then audio
                        audio_items = [i for i in self._items if i.track_type == "audio"]
                        new_items = []
                        for vid in vis_ids:
                            for it in self._items:
                                if it.item_id == vid:
                                    new_items.append(it)
                                    break
                        new_items.extend(audio_items)
                        self._items = new_items
                        self._drag_original_visual_index = target_index
                        self.item_reordered.emit(dragged_id, target_index)

        elif self._drag_mode == "trim_start":
            new_start = max(0, min(self._drag_original_start + delta_ms, item.end_ms - 100))
            snapped = self._snap_value(new_start, item.item_id)
            snapped = min(snapped, item.end_ms - 100)
            if snapped != new_start and abs(snapped - new_start) <= _SNAP_THRESHOLD_MS:
                item.start_ms = snapped
                self._snap_line_x = self._ms_to_x(snapped)
            else:
                item.start_ms = new_start

        elif self._drag_mode == "trim_end":
            new_end = max(item.start_ms + 100, self._drag_original_end + delta_ms)
            snapped = self._snap_value(new_end, item.item_id)
            snapped = max(snapped, item.start_ms + 100)
            if snapped != new_end and abs(snapped - new_end) <= _SNAP_THRESHOLD_MS:
                item.end_ms = snapped
                self._snap_line_x = self._ms_to_x(snapped)
            else:
                item.end_ms = new_end

        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._dragging and self._drag_item_id:
            item = next((i for i in self._items if i.item_id == self._drag_item_id), None)
            if item:
                if self._drag_mode == "move":
                    self.item_moved.emit(item.item_id, item.start_ms, item.end_ms)
                elif self._drag_mode in ("trim_start", "trim_end"):
                    which = "start" if self._drag_mode == "trim_start" else "end"
                    ms = item.start_ms if which == "start" else item.end_ms
                    self.item_trimmed.emit(item.item_id, which, ms)

        self._dragging = False
        self._drag_item_id = None
        self._drag_mode = ""
        self._snap_line_x = None
        self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Zoom around mouse position
            mouse_ms = self._x_to_ms(event.position().x())
            factor = 1.2 if delta > 0 else 1 / 1.2
            new_ppm = max(0.02, min(2.0, self._pixels_per_ms * factor))
            # Anchor: keep mouse_ms at the same pixel
            mouse_px = event.position().x() - _HEADER_WIDTH
            new_offset = int(mouse_ms - mouse_px / new_ppm)
            self._pixels_per_ms = new_ppm
            self._scroll_offset = max(0, new_offset)
            self._clamp_scroll()
            self._emit_scroll_state()
            self.update()
        else:
            # Pan
            visible = self._visible_duration_ms()
            shift = int(visible * 0.1) * (-1 if delta > 0 else 1)
            self._scroll_offset = max(0, self._scroll_offset + shift)
            self._clamp_scroll()
            self._emit_scroll_state()
            self.update()
        event.accept()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._clamp_scroll()
        self._emit_scroll_state()
