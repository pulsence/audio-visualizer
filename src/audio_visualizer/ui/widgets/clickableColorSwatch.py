"""Reusable clickable color swatch widget.

A QLabel that opens a QColorDialog when clicked, providing the same
behavior as the adjacent 'Select Color' button.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QLabel


class ClickableColorSwatch(QLabel):
    """A colored swatch label that emits ``clicked`` when pressed."""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("border: 1px solid #888; background: transparent;")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
        else:
            super().mousePressEvent(event)

    def set_color(self, r: int, g: int, b: int) -> None:
        """Update the swatch background color."""
        self.setStyleSheet(f"border: 1px solid #888; background: rgb({r}, {g}, {b});")

    def clear_color(self) -> None:
        """Reset to transparent."""
        self.setStyleSheet("border: 1px solid #888; background: transparent;")
