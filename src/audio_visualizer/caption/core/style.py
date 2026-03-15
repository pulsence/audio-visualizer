"""
ASS style generation and color utilities.

This module provides utilities for building pysubs2 SSAStyle objects from preset
configurations and parsing color values.
"""

import re
from typing import Tuple

import pysubs2

from .config import PresetConfig


class StyleBuilder:
    """
    Builds pysubs2.SSAStyle from PresetConfig.

    This class encapsulates the logic for converting preset configuration
    into ASS subtitle styles that can be used by pysubs2.

    Example:
        preset = PresetConfig.from_dict({"font_name": "Arial", "font_size": 64, ...})
        builder = StyleBuilder(preset)
        style = builder.build("Default")
    """

    def __init__(self, preset: PresetConfig):
        """
        Initialize StyleBuilder with a preset configuration.

        Args:
            preset: The preset configuration to use for building styles
        """
        self.preset = preset

    def build(self, style_name: str = "Default") -> pysubs2.SSAStyle:
        """
        Build a pysubs2 SSAStyle from the preset configuration.

        Args:
            style_name: Name for the style (default: "Default")

        Returns:
            Configured pysubs2.SSAStyle object
        """
        preset = self.preset

        # Parse colors
        primary_rgb = self.parse_color(preset.primary_color)
        outline_rgb = self.parse_color(preset.outline_color)
        shadow_rgb = self.parse_color(preset.shadow_color)

        # Create style object
        style = pysubs2.SSAStyle()
        style.fontname = preset.font_name
        style.fontsize = preset.font_size
        style.bold = -1 if preset.bold else 0
        style.italic = -1 if preset.italic else 0

        # Set colors
        style.primarycolor = self.make_pysubs2_color(primary_rgb, alpha=0)
        style.outlinecolor = self.make_pysubs2_color(outline_rgb, alpha=0)
        style.backcolor = self.make_pysubs2_color(shadow_rgb, alpha=0)

        # Set styling
        style.outline = preset.outline_px
        style.shadow = preset.shadow_px
        style.spacing = 0

        # Set alignment and margins
        style.alignment = preset.alignment
        style.marginl = preset.margin_l
        style.marginr = preset.margin_r
        style.marginv = preset.margin_v

        # Note: blur_px is handled at the event level via \blur override tag,
        # not in the style definition

        return style

    @staticmethod
    def parse_color(color: str) -> Tuple[int, int, int]:
        """
        Parse hex color string to RGB tuple.

        Accepts formats:
        - "#RRGGBB"
        - "RRGGBB"

        Args:
            color: Hex color string

        Returns:
            Tuple of (r, g, b) integers in range 0-255

        Raises:
            ValueError: If color format is invalid
        """
        m = re.fullmatch(r"#?([0-9a-fA-F]{6})", color.strip())
        if not m:
            raise ValueError(f"Invalid color '{color}'. Use #RRGGBB format.")

        hex_str = m.group(1)
        r = int(hex_str[0:2], 16)
        g = int(hex_str[2:4], 16)
        b = int(hex_str[4:6], 16)

        return (r, g, b)

    @staticmethod
    def make_pysubs2_color(rgb: Tuple[int, int, int], alpha: int = 0) -> pysubs2.Color:
        """
        Create a pysubs2 Color object from RGB values.

        Args:
            rgb: Tuple of (r, g, b) integers
            alpha: Alpha value (0=opaque, 255=fully transparent, ASS convention)

        Returns:
            pysubs2.Color object
        """
        r, g, b = rgb
        return pysubs2.Color(r, g, b, alpha)
