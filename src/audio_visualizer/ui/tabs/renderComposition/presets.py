"""Built-in layout presets for the Render Composition tab.

Each preset function returns a list of :class:`CompositionLayer` templates
configured for common composition layouts.
"""
from __future__ import annotations

from audio_visualizer.ui.tabs.renderComposition.model import CompositionLayer


# ------------------------------------------------------------------
# Preset registry
# ------------------------------------------------------------------

PRESET_NAMES: tuple[str, ...] = (
    "fullscreen_bg_centered_viz",
    "fullscreen_bg_bottom_captions",
    "pip_overlay",
)


def get_preset(name: str, width: int = 1920, height: int = 1080) -> list[CompositionLayer]:
    """Return layers for the named preset, scaled to *width* x *height*.

    Parameters
    ----------
    name : str
        One of :data:`PRESET_NAMES`.
    width, height : int
        Output resolution to scale the preset to.

    Returns
    -------
    list[CompositionLayer]
        Template layers configured for the preset layout.

    Raises
    ------
    ValueError
        If *name* is not a recognized preset.
    """
    factory = _PRESETS.get(name)
    if factory is None:
        raise ValueError(
            f"Unknown preset '{name}'. "
            f"Available: {', '.join(PRESET_NAMES)}"
        )
    return factory(width, height)


# ------------------------------------------------------------------
# Individual preset factories
# ------------------------------------------------------------------

def _fullscreen_bg_centered_viz(width: int, height: int) -> list[CompositionLayer]:
    """Full background + centered visualizer overlay.

    Layer 0: Full-screen background (z=0)
    Layer 1: Centered visualizer at 80% size (z=1)
    """
    viz_w = int(width * 0.8)
    viz_h = int(height * 0.8)
    viz_x = (width - viz_w) // 2
    viz_y = (height - viz_h) // 2

    return [
        CompositionLayer(
            display_name="Background",
            layer_type="background",
            x=0, y=0,
            width=width, height=height,
            z_order=0,
        ),
        CompositionLayer(
            display_name="Visualizer",
            layer_type="visualizer",
            x=viz_x, y=viz_y,
            width=viz_w, height=viz_h,
            z_order=1,
        ),
    ]


def _fullscreen_bg_bottom_captions(width: int, height: int) -> list[CompositionLayer]:
    """Full background + bottom-aligned caption overlay.

    Layer 0: Full-screen background (z=0)
    Layer 1: Caption overlay at bottom 20% of screen (z=1)
    """
    cap_h = int(height * 0.2)
    cap_y = height - cap_h

    return [
        CompositionLayer(
            display_name="Background",
            layer_type="background",
            x=0, y=0,
            width=width, height=height,
            z_order=0,
        ),
        CompositionLayer(
            display_name="Captions",
            layer_type="caption_overlay",
            x=0, y=cap_y,
            width=width, height=cap_h,
            z_order=1,
        ),
    ]


def _pip_overlay(width: int, height: int) -> list[CompositionLayer]:
    """Picture-in-picture with small visualizer in corner.

    Layer 0: Full-screen background (z=0)
    Layer 1: Small visualizer in bottom-right corner at 25% size (z=1)
    """
    pip_w = int(width * 0.25)
    pip_h = int(height * 0.25)
    margin = int(width * 0.02)
    pip_x = width - pip_w - margin
    pip_y = height - pip_h - margin

    return [
        CompositionLayer(
            display_name="Background",
            layer_type="background",
            x=0, y=0,
            width=width, height=height,
            z_order=0,
        ),
        CompositionLayer(
            display_name="PiP Visualizer",
            layer_type="visualizer",
            x=pip_x, y=pip_y,
            width=pip_w, height=pip_h,
            z_order=1,
        ),
    ]


# ------------------------------------------------------------------
# Dispatch table
# ------------------------------------------------------------------

_PRESETS = {
    "fullscreen_bg_centered_viz": _fullscreen_bg_centered_viz,
    "fullscreen_bg_bottom_captions": _fullscreen_bg_bottom_captions,
    "pip_overlay": _pip_overlay,
}
