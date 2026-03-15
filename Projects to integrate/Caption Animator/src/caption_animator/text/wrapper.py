"""
Text wrapping for subtitles.

This module provides text wrapping functionality that respects word boundaries
and maximum line widths.
"""

from typing import TYPE_CHECKING, List

from .utils import normalize_whitespace

if TYPE_CHECKING:
    from PIL import ImageFont


def wrap_text_to_width(
    text: str,
    font: "ImageFont.FreeTypeFont",
    max_width_px: int
) -> str:
    """
    Wrap text to fit within a maximum width.

    Uses greedy word-wrapping algorithm. Existing line breaks are preserved.

    Args:
        text: Text to wrap
        font: Pillow FreeTypeFont for measurement
        max_width_px: Maximum width in pixels (0 = no wrapping)

    Returns:
        Wrapped text with \\n separating lines

    Example:
        >>> font = ImageFont.truetype("arial.ttf", 64)
        >>> text = "This is a very long line that needs wrapping"
        >>> wrapped = wrap_text_to_width(text, font, 400)
        >>> print(wrapped)
        This is a very
        long line that
        needs wrapping
    """
    text = normalize_whitespace(text)

    if max_width_px <= 0:
        return text

    lines_in = text.split("\n")
    lines_out: List[str] = []

    for raw_line in lines_in:
        raw_line = raw_line.strip()

        if not raw_line:
            lines_out.append("")
            continue

        # Split into words
        words = raw_line.split(" ")
        current: List[str] = []

        for word in words:
            if not current:
                # First word always goes on the line
                current = [word]
                continue

            # Try adding this word to the current line
            candidate = " ".join(current + [word])

            if font.getlength(candidate) <= max_width_px:
                # Fits! Add it
                current.append(word)
            else:
                # Doesn't fit - flush current line and start new one
                lines_out.append(" ".join(current))
                current = [word]

        # Don't forget the last line
        if current:
            lines_out.append(" ".join(current))

    return "\n".join(lines_out)
