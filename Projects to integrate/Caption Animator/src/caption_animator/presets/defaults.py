"""
Built-in default presets.

This module defines the default presets that ship with the application.
"""

from typing import Dict, Any


# Built-in preset configurations
BUILTIN_PRESETS: Dict[str, Dict[str, Any]] = {
    "clean_outline": {
        "font_file": "",  # Empty = use system font
        "font_name": "Arial",
        "font_size": 64,
        "bold": False,
        "italic": False,
        "primary_color": "#FFFFFF",
        "outline_color": "#000000",
        "shadow_color": "#000000",
        "outline_px": 5,
        "shadow_px": 2,
        "blur_px": 0,
        "line_spacing": 8,
        "max_width_px": 1200,
        "padding": [40, 60, 50, 60],  # [top, right, bottom, left]
        "alignment": 2,  # Bottom-center
        "margin_l": 0,
        "margin_r": 0,
        "margin_v": 0,
        "wrap_style": 2,  # Smart wrapping
        "animation": {
            "type": "fade",
            "in_ms": 120,
            "out_ms": 120,
        },
    },
    "modern_box": {
        "font_file": "",
        "font_name": "Arial",
        "font_size": 62,
        "bold": True,
        "italic": False,
        "primary_color": "#FFFFFF",
        "outline_color": "#000000",
        "shadow_color": "#000000",
        "outline_px": 6,
        "shadow_px": 3,
        "blur_px": 0,
        "line_spacing": 10,
        "max_width_px": 1100,
        "padding": [44, 70, 56, 70],
        "alignment": 2,
        "margin_l": 0,
        "margin_r": 0,
        "margin_v": 0,
        "wrap_style": 2,
        "animation": {
            "type": "slide_up",
            "in_ms": 140,
            "out_ms": 120,
            "move_px": 26,
        },
    },
}


def get_builtin_preset(name: str) -> Dict[str, Any]:
    """
    Get a built-in preset by name.

    Args:
        name: Preset name (e.g., "modern_box", "clean_outline")

    Returns:
        Copy of the preset dictionary

    Raises:
        KeyError: If preset name is not found
    """
    if name not in BUILTIN_PRESETS:
        available = ", ".join(sorted(BUILTIN_PRESETS.keys()))
        raise KeyError(
            f"Unknown built-in preset: '{name}'. "
            f"Available: {available}"
        )

    # Return a copy to prevent modification
    return dict(BUILTIN_PRESETS[name])


def list_builtin_presets() -> list:
    """
    List all built-in preset names.

    Returns:
        Sorted list of preset names
    """
    return sorted(BUILTIN_PRESETS.keys())
