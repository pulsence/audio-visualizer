"""
Overlay size calculation.

This module computes the tight overlay dimensions needed to render all subtitles
without clipping, based on text measurement and preset configuration.
"""

import math
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Tuple

import pysubs2

from ..text.measurement import measure_multiline
from ..text.utils import normalize_whitespace, strip_ass_tags
from ..text.wrapper import wrap_text_to_width
from .config import PresetConfig

if TYPE_CHECKING:
    from PIL import ImageFont


@dataclass
class OverlaySize:
    """
    Represents the dimensions of an overlay video canvas.

    Attributes:
        width: Width in pixels
        height: Height in pixels
    """

    width: int
    height: int


class SizeCalculator:
    """
    Computes tight overlay dimensions based on subtitle content.

    The calculator measures all subtitle events to determine the maximum
    width and height needed, then adds padding and safety margins.

    Example:
        preset = PresetConfig.from_dict({...})
        calculator = SizeCalculator(preset, safety_scale=1.12)
        size = calculator.compute_size(subtitle_file)
        print(f"Overlay size: {size.width}x{size.height}")
    """

    def __init__(self, preset: PresetConfig, safety_scale: float = 1.12):
        """
        Initialize size calculator.

        Args:
            preset: Preset configuration with font, padding, etc.
            safety_scale: Multiplier to avoid edge clipping (default: 1.12)
        """
        self.preset = preset
        self.safety_scale = safety_scale
        self.font = self._load_font()

    def _load_font(self) -> "ImageFont.FreeTypeFont":
        """Load the font for text measurement."""
        from PIL import ImageFont

        font_file = self.preset.font_file
        font_size = self.preset.font_size

        if font_file:
            font_path = Path(font_file)
            if not font_path.exists():
                raise FileNotFoundError(f"Font file not found: {font_file}")
            return ImageFont.truetype(str(font_path), size=font_size)

        # Try common fallback fonts
        candidates = [
            "arial.ttf",
            "Arial.ttf",
            "DejaVuSans.ttf",
            "LiberationSans-Regular.ttf",
        ]

        for candidate in candidates:
            try:
                return ImageFont.truetype(candidate, size=font_size)
            except Exception:
                continue

        raise RuntimeError(
            "No usable font found. Provide 'font_file' in preset configuration "
            "pointing to a TTF/OTF file for deterministic measurement."
        )

    def compute_size(self, subs: pysubs2.SSAFile) -> OverlaySize:
        """
        Compute the overlay size needed for all subtitle events.

        This method:
        1. Measures each subtitle event's text dimensions
        2. Finds the maximum width and height
        3. Adds padding, outline, and shadow allowances
        4. Applies safety scaling
        5. Ensures even dimensions

        Args:
            subs: Loaded subtitle file

        Returns:
            OverlaySize with width and height in pixels
        """
        max_width_px = self.preset.max_width_px
        line_spacing_px = self.preset.line_spacing
        padding = self.preset.padding

        if len(padding) != 4:
            raise ValueError(
                f"Preset 'padding' must have 4 values [top, right, bottom, left], "
                f"got {len(padding)}"
            )

        pad_t, pad_r, pad_b, pad_l = padding

        outline_px = self.preset.outline_px
        shadow_px = self.preset.shadow_px

        max_w = 0
        max_h = 0

        # Measure all events
        for event in subs.events:
            if not isinstance(event, pysubs2.SSAEvent):
                continue

            # Strip tags and normalize
            text = strip_ass_tags(event.text)
            text = normalize_whitespace(text)

            # Apply wrapping
            text = wrap_text_to_width(text, self.font, max_width_px)

            # Measure dimensions
            w, h, _ = measure_multiline(text, self.font, line_spacing_px)

            max_w = max(max_w, w)
            max_h = max(max_h, h)

        # Add allowances for outline and shadow
        # Outline expands in all directions; shadow expands bottom-right
        # Conservative estimate: (outline * 2) + (shadow * 2)
        extra_w = int(math.ceil(outline_px * 2 + shadow_px * 2))
        extra_h = int(math.ceil(outline_px * 2 + shadow_px * 2))

        # Calculate final dimensions with padding and safety scale
        w_final = int(
            math.ceil((max_w + pad_l + pad_r + extra_w) * self.safety_scale)
        )
        h_final = int(
            math.ceil((max_h + pad_t + pad_b + extra_h) * self.safety_scale)
        )

        # Ensure minimum dimensions
        w_final = max(w_final, 64)
        h_final = max(h_final, 64)

        # Ensure even dimensions (some codecs prefer this)
        if w_final % 2 == 1:
            w_final += 1
        if h_final % 2 == 1:
            h_final += 1

        return OverlaySize(width=w_final, height=h_final)

    def compute_anchor_position(self, size: OverlaySize) -> Tuple[int, int]:
        """
        Compute the anchor position for centered subtitles.

        The anchor is centered within the padded area of the canvas.

        Args:
            size: The overlay size

        Returns:
            Tuple of (x, y) coordinates for the anchor point
        """
        padding = self.preset.padding
        pad_t, pad_r, pad_b, pad_l = padding

        left = pad_l
        right = size.width - pad_r
        top = pad_t
        bottom = size.height - pad_b

        x = (left + right) // 2
        y = (top + bottom) // 2

        return (x, y)
