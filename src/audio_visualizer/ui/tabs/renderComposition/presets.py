"""Layout presets for the Render Composition tab.

Provides built-in presets and user-saved preset persistence.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from audio_visualizer.ui.tabs.renderComposition.model import CompositionLayer

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Built-in preset registry
# ------------------------------------------------------------------

BUILTIN_PRESET_NAMES: tuple[str, ...] = (
    "fullscreen_bg_centered_viz",
    "fullscreen_bg_bottom_captions",
    "pip_overlay",
)


def get_preset(name: str, width: int = 1920, height: int = 1080) -> list[CompositionLayer]:
    """Return layers for the named preset, scaled to *width* x *height*.

    Works for both built-in and user-saved presets.

    Raises
    ------
    ValueError
        If *name* is not a recognized preset.
    """
    factory = _PRESETS.get(name)
    if factory is not None:
        return factory(width, height)

    # Try loading user preset
    user_layers = load_preset(name)
    if user_layers is not None:
        return user_layers

    raise ValueError(
        f"Unknown preset '{name}'. "
        f"Available: {', '.join(list_presets())}"
    )


def list_presets() -> list[str]:
    """Return all available preset names (built-in + user-saved)."""
    names = list(BUILTIN_PRESET_NAMES)
    user_dir = _user_preset_dir()
    if user_dir.is_dir():
        for p in sorted(user_dir.glob("*.yaml")):
            name = p.stem
            if name not in names:
                names.append(name)
    return names


def save_preset(name: str, layers: list[CompositionLayer]) -> Path:
    """Save visual layer layout fields as a user preset.

    Returns the path to the saved file.
    """
    try:
        import yaml
    except ImportError:
        raise RuntimeError("PyYAML is required to save presets")

    preset_dir = _user_preset_dir()
    preset_dir.mkdir(parents=True, exist_ok=True)

    slug = _slugify(name)
    path = preset_dir / f"{slug}.yaml"

    data: list[dict[str, Any]] = []
    for layer in layers:
        data.append({
            "display_name": layer.display_name,
            "x": layer.x,
            "y": layer.y,
            "width": layer.width,
            "height": layer.height,
            "z_order": layer.z_order,
            "start_ms": layer.start_ms,
            "end_ms": layer.end_ms,
            "behavior_after_end": layer.behavior_after_end,
            "enabled": layer.enabled,
            "matte_settings": dict(layer.matte_settings),
        })

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump({"name": name, "layers": data}, f, default_flow_style=False)

    logger.info("Saved user preset '%s' to %s", name, path)
    return path


def load_preset(name: str) -> list[CompositionLayer] | None:
    """Load a user-saved preset by name. Returns None if not found."""
    try:
        import yaml
    except ImportError:
        return None

    slug = _slugify(name)
    path = _user_preset_dir() / f"{slug}.yaml"
    if not path.is_file():
        return None

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "layers" not in data:
        return None

    import copy
    from audio_visualizer.ui.tabs.renderComposition.model import DEFAULT_MATTE_SETTINGS

    layers: list[CompositionLayer] = []
    for ld in data["layers"]:
        layers.append(CompositionLayer(
            display_name=ld.get("display_name", ""),
            x=ld.get("x", 0),
            y=ld.get("y", 0),
            width=ld.get("width", 1920),
            height=ld.get("height", 1080),
            z_order=ld.get("z_order", 0),
            start_ms=ld.get("start_ms", 0),
            end_ms=ld.get("end_ms", 0),
            behavior_after_end=ld.get("behavior_after_end", "freeze_last_frame"),
            enabled=ld.get("enabled", True),
            matte_settings=ld.get("matte_settings", copy.deepcopy(DEFAULT_MATTE_SETTINGS)),
        ))
    return layers


# ------------------------------------------------------------------
# Individual preset factories
# ------------------------------------------------------------------

def _fullscreen_bg_centered_viz(width: int, height: int) -> list[CompositionLayer]:
    viz_w = int(width * 0.8)
    viz_h = int(height * 0.8)
    viz_x = (width - viz_w) // 2
    viz_y = (height - viz_h) // 2
    return [
        CompositionLayer(
            display_name="Background",
            x=0, y=0, width=width, height=height, z_order=0,
        ),
        CompositionLayer(
            display_name="Visualizer",
            x=viz_x, y=viz_y, width=viz_w, height=viz_h, z_order=1,
        ),
    ]


def _fullscreen_bg_bottom_captions(width: int, height: int) -> list[CompositionLayer]:
    cap_h = int(height * 0.2)
    cap_y = height - cap_h
    return [
        CompositionLayer(
            display_name="Background",
            x=0, y=0, width=width, height=height, z_order=0,
        ),
        CompositionLayer(
            display_name="Captions",
            x=0, y=cap_y, width=width, height=cap_h, z_order=1,
        ),
    ]


def _pip_overlay(width: int, height: int) -> list[CompositionLayer]:
    pip_w = int(width * 0.25)
    pip_h = int(height * 0.25)
    margin = int(width * 0.02)
    pip_x = width - pip_w - margin
    pip_y = height - pip_h - margin
    return [
        CompositionLayer(
            display_name="Background",
            x=0, y=0, width=width, height=height, z_order=0,
        ),
        CompositionLayer(
            display_name="PiP Visualizer",
            x=pip_x, y=pip_y, width=pip_w, height=pip_h, z_order=1,
        ),
    ]


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _user_preset_dir() -> Path:
    from audio_visualizer.app_paths import get_data_dir
    return get_data_dir() / "render_composition" / "presets"


def _slugify(name: str) -> str:
    """Convert a preset name to a filesystem-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s-]+', '_', slug)
    return slug or "preset"


_PRESETS = {
    "fullscreen_bg_centered_viz": _fullscreen_bg_centered_viz,
    "fullscreen_bg_bottom_captions": _fullscreen_bg_bottom_captions,
    "pip_overlay": _pip_overlay,
}
