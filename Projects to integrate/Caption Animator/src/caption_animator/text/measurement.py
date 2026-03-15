"""
Text measurement using Pillow.

This module provides utilities for measuring text dimensions using Pillow's
font rendering, which approximates how libass will render the text.
"""

import math
from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from PIL import ImageFont


def measure_multiline(
    text: str,
    font: "ImageFont.FreeTypeFont",
    line_spacing_px: int
) -> Tuple[int, int, int]:
    """
    Measure the dimensions of multi-line text.

    Args:
        text: Text to measure (may contain \\n for line breaks)
        font: Pillow FreeTypeFont to use for measurement
        line_spacing_px: Additional spacing between lines in pixels

    Returns:
        Tuple of (max_line_width_px, total_height_px, line_count)

    Example:
        >>> font = ImageFont.truetype("arial.ttf", 64)
        >>> width, height, lines = measure_multiline("Hello\\nWorld", font, 8)
        >>> print(f"Size: {width}x{height}, Lines: {lines}")
        Size: 120x140, Lines: 2
    """
    lines = text.split("\n") if text else [""]

    # Measure width of each line
    widths = [int(math.ceil(font.getlength(line))) for line in lines]
    max_width = max(widths) if widths else 0

    # Calculate total height
    # Pillow's getmetrics() returns (ascent, descent)
    ascent, descent = font.getmetrics()
    line_height = ascent + descent

    # Total height = (line_height * num_lines) + (spacing * (num_lines - 1))
    total_height = len(lines) * line_height + max(0, len(lines) - 1) * line_spacing_px

    return max_width, total_height, len(lines)


def measure_single_line(text: str, font: "ImageFont.FreeTypeFont") -> int:
    """
    Measure the width of a single line of text.

    Args:
        text: Text to measure (should not contain newlines)
        font: Pillow FreeTypeFont to use for measurement

    Returns:
        Width in pixels

    Example:
        >>> font = ImageFont.truetype("arial.ttf", 64)
        >>> width = measure_single_line("Hello", font)
        >>> print(f"Width: {width}px")
        Width: 85px
    """
    return int(math.ceil(font.getlength(text)))
