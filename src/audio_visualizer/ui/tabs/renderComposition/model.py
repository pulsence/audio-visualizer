"""Composition model — layer data and layout state.

Provides :class:`CompositionLayer` (a dataclass representing a single
composited layer) and :class:`CompositionModel` (the mutable container
that holds all layers, audio source, and output settings).
"""
from __future__ import annotations

import copy
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

VALID_LAYER_TYPES: tuple[str, ...] = (
    "background",
    "visualizer",
    "caption_overlay",
    "subtitle_direct",
    "custom",
)

VALID_BEHAVIORS: tuple[str, ...] = (
    "freeze_last_frame",
    "hide",
    "loop",
)

DEFAULT_MATTE_SETTINGS: dict[str, Any] = {
    "mode": "none",  # none, colorkey, chromakey, lumakey
    "key_target": "#00FF00",
    "threshold": 0.1,
    "similarity": 0.1,
    "blend": 0.0,
    "softness": 0.0,
    "erode": 0,
    "dilate": 0,
    "feather": 0,
    "despill": False,
    "invert": False,
}


# ------------------------------------------------------------------
# CompositionLayer
# ------------------------------------------------------------------

@dataclass
class CompositionLayer:
    """A single layer in the composition timeline.

    Attributes
    ----------
    id : str
        Unique identifier for this layer (UUID).
    display_name : str
        Human-readable label.
    asset_id : str | None
        Reference to a SessionAsset id, or None for unassigned layers.
    asset_path : Path | None
        Direct file path (used when asset_id is None).
    layer_type : str
        One of :data:`VALID_LAYER_TYPES`.
    x, y : int
        Top-left position in output coordinates.
    width, height : int
        Size in output coordinates.
    z_order : int
        Stacking order (higher = on top).
    start_ms : int
        Start time in the composition timeline.
    end_ms : int
        End time in the composition timeline.
    behavior_after_end : str
        One of :data:`VALID_BEHAVIORS`.
    enabled : bool
        Whether this layer participates in the render.
    matte_settings : dict
        Keying/matte parameters for this layer.
    """

    id: str = ""
    display_name: str = ""
    asset_id: str | None = None
    asset_path: Path | None = None
    layer_type: str = "custom"
    x: int = 0
    y: int = 0
    width: int = 1920
    height: int = 1080
    z_order: int = 0
    start_ms: int = 0
    end_ms: int = 0
    behavior_after_end: str = "freeze_last_frame"
    enabled: bool = True
    matte_settings: dict[str, Any] = field(default_factory=lambda: copy.deepcopy(DEFAULT_MATTE_SETTINGS))

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())


# ------------------------------------------------------------------
# CompositionModel
# ------------------------------------------------------------------

class CompositionModel:
    """Mutable container for the full composition state.

    Holds an ordered list of :class:`CompositionLayer` instances, an
    optional audio source, and output format parameters.
    """

    def __init__(self) -> None:
        self.layers: list[CompositionLayer] = []
        self.audio_source_asset_id: str | None = None
        self.audio_source_path: Path | None = None
        self.output_width: int = 1920
        self.output_height: int = 1080
        self.output_fps: float = 30.0

    # -- layer CRUD ------------------------------------------------

    def add_layer(self, layer: CompositionLayer) -> None:
        """Append a layer to the composition."""
        self.layers.append(layer)
        logger.debug("Layer added: %s (%s)", layer.id, layer.display_name)

    def remove_layer(self, layer_id: str) -> CompositionLayer | None:
        """Remove and return the layer with *layer_id*, or ``None``."""
        for i, layer in enumerate(self.layers):
            if layer.id == layer_id:
                removed = self.layers.pop(i)
                logger.debug("Layer removed: %s", layer_id)
                return removed
        return None

    def get_layer(self, layer_id: str) -> CompositionLayer | None:
        """Return the layer with *layer_id*, or ``None``."""
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        return None

    def move_layer(self, layer_id: str, x: int, y: int) -> None:
        """Update position of the layer with *layer_id*."""
        layer = self.get_layer(layer_id)
        if layer is not None:
            layer.x = x
            layer.y = y

    def resize_layer(self, layer_id: str, width: int, height: int) -> None:
        """Update size of the layer with *layer_id*."""
        layer = self.get_layer(layer_id)
        if layer is not None:
            layer.width = width
            layer.height = height

    def reorder_layer(self, layer_id: str, new_z_order: int) -> None:
        """Update z-order of the layer with *layer_id*."""
        layer = self.get_layer(layer_id)
        if layer is not None:
            layer.z_order = new_z_order

    def update_layer(self, layer_id: str, **kwargs: Any) -> None:
        """Update arbitrary fields on the layer with *layer_id*."""
        layer = self.get_layer(layer_id)
        if layer is None:
            return
        for attr, value in kwargs.items():
            if hasattr(layer, attr):
                setattr(layer, attr, value)

    # -- queries ---------------------------------------------------

    def get_duration_ms(self) -> int:
        """Return the maximum end time of all enabled layers."""
        if not self.layers:
            return 0
        enabled = [l for l in self.layers if l.enabled]
        if not enabled:
            return 0
        return max(l.end_ms for l in enabled)

    def get_layers_sorted(self) -> list[CompositionLayer]:
        """Return layers sorted by z_order (lowest first)."""
        return sorted(self.layers, key=lambda l: l.z_order)

    # -- serialization ---------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize the model to a plain dictionary."""
        layers_out: list[dict] = []
        for layer in self.layers:
            layer_dict: dict[str, Any] = {
                "id": layer.id,
                "display_name": layer.display_name,
                "asset_id": layer.asset_id,
                "asset_path": str(layer.asset_path) if layer.asset_path else None,
                "layer_type": layer.layer_type,
                "x": layer.x,
                "y": layer.y,
                "width": layer.width,
                "height": layer.height,
                "z_order": layer.z_order,
                "start_ms": layer.start_ms,
                "end_ms": layer.end_ms,
                "behavior_after_end": layer.behavior_after_end,
                "enabled": layer.enabled,
                "matte_settings": copy.deepcopy(layer.matte_settings),
            }
            layers_out.append(layer_dict)

        return {
            "layers": layers_out,
            "audio_source_asset_id": self.audio_source_asset_id,
            "audio_source_path": str(self.audio_source_path) if self.audio_source_path else None,
            "output_width": self.output_width,
            "output_height": self.output_height,
            "output_fps": self.output_fps,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompositionModel:
        """Restore a model from a dictionary produced by :meth:`to_dict`."""
        model = cls()
        model.audio_source_asset_id = data.get("audio_source_asset_id")
        audio_path = data.get("audio_source_path")
        model.audio_source_path = Path(audio_path) if audio_path else None
        model.output_width = data.get("output_width", 1920)
        model.output_height = data.get("output_height", 1080)
        model.output_fps = data.get("output_fps", 30.0)

        for layer_dict in data.get("layers", []):
            asset_path = layer_dict.get("asset_path")
            layer = CompositionLayer(
                id=layer_dict.get("id", ""),
                display_name=layer_dict.get("display_name", ""),
                asset_id=layer_dict.get("asset_id"),
                asset_path=Path(asset_path) if asset_path else None,
                layer_type=layer_dict.get("layer_type", "custom"),
                x=layer_dict.get("x", 0),
                y=layer_dict.get("y", 0),
                width=layer_dict.get("width", 1920),
                height=layer_dict.get("height", 1080),
                z_order=layer_dict.get("z_order", 0),
                start_ms=layer_dict.get("start_ms", 0),
                end_ms=layer_dict.get("end_ms", 0),
                behavior_after_end=layer_dict.get("behavior_after_end", "freeze_last_frame"),
                enabled=layer_dict.get("enabled", True),
                matte_settings=layer_dict.get("matte_settings", copy.deepcopy(DEFAULT_MATTE_SETTINGS)),
            )
            model.layers.append(layer)

        return model
