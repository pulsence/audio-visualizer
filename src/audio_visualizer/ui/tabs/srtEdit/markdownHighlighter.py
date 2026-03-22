"""Markdown syntax highlighter for SRT Edit text editors.

Highlights **bold**, *italic*, and ==highlight== markers inline while
preserving the underlying raw markdown source text.  Reusable across the
in-table MultilineTextDelegate editor and the sidebar segment editor.
"""
from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextDocument


# Compiled regex patterns for supported markdown constructs.
# Order matters: bold (**) must be tried before italic (*) so greedy
# matching does not consume bold delimiters as two separate italics.
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_HIGHLIGHT_RE = re.compile(r"==(.+?)==")


def _make_bold_format() -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setFontWeight(QFont.Weight.Bold)
    return fmt


def _make_italic_format() -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setFontItalic(True)
    return fmt


def _make_highlight_format() -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setBackground(QColor(255, 255, 100, 90))
    return fmt


def _make_delimiter_format() -> QTextCharFormat:
    """Subdued format applied to the markdown delimiter characters."""
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(150, 150, 150))
    return fmt


class MarkdownHighlighter(QSyntaxHighlighter):
    """QSyntaxHighlighter that decorates **bold**, *italic*, ==highlight==.

    Delimiter characters (``**``, ``*``, ``==``) are rendered in a subdued
    colour so the user can see they are markup, while the enclosed text
    gets the corresponding visual treatment.
    """

    def __init__(self, document: QTextDocument | None = None) -> None:
        super().__init__(document)
        self._bold_fmt = _make_bold_format()
        self._italic_fmt = _make_italic_format()
        self._highlight_fmt = _make_highlight_format()
        self._delim_fmt = _make_delimiter_format()

    # ------------------------------------------------------------------
    # QSyntaxHighlighter interface
    # ------------------------------------------------------------------

    def highlightBlock(self, text: str) -> None:  # noqa: N802 — Qt naming
        """Apply markdown formatting to a single text block."""
        # Bold (**...**)
        for m in _BOLD_RE.finditer(text):
            full_start = m.start()
            full_end = m.end()
            inner_start = m.start(1)
            inner_end = m.end(1)
            # Delimiters
            self.setFormat(full_start, 2, self._delim_fmt)
            self.setFormat(full_end - 2, 2, self._delim_fmt)
            # Content
            self.setFormat(inner_start, inner_end - inner_start, self._bold_fmt)

        # Italic (*...*)  — skip spans already covered by bold
        for m in _ITALIC_RE.finditer(text):
            full_start = m.start()
            full_end = m.end()
            inner_start = m.start(1)
            inner_end = m.end(1)
            # Skip if this overlaps a bold match
            if self._overlaps_bold(text, full_start, full_end):
                continue
            self.setFormat(full_start, 1, self._delim_fmt)
            self.setFormat(full_end - 1, 1, self._delim_fmt)
            self.setFormat(inner_start, inner_end - inner_start, self._italic_fmt)

        # Highlight (==...==)
        for m in _HIGHLIGHT_RE.finditer(text):
            full_start = m.start()
            full_end = m.end()
            inner_start = m.start(1)
            inner_end = m.end(1)
            self.setFormat(full_start, 2, self._delim_fmt)
            self.setFormat(full_end - 2, 2, self._delim_fmt)
            self.setFormat(inner_start, inner_end - inner_start, self._highlight_fmt)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _overlaps_bold(text: str, start: int, end: int) -> bool:
        """Return True if the span [start, end) overlaps any bold match."""
        for bm in _BOLD_RE.finditer(text):
            if start < bm.end() and end > bm.start():
                return True
        return False
