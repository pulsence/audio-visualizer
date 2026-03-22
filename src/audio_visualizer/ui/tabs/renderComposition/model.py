"""Composition model — layer data and layout state.

Provides :class:`CompositionLayer` (a dataclass representing a single
composited layer), :class:`CompositionAudioLayer` (a dataclass for an
audio layer in the composition), and :class:`CompositionModel` (the
mutable container that holds all layers, audio source, and output
settings).
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

VALID_BEHAVIORS: tuple[str, ...] = (
    "freeze_last_frame",
    "hide",
    "loop",
)

RESOLUTION_PRESETS: dict[str, tuple[int, int]] = {
    "hd": (1920, 1080),
    "hd_vertical": (1080, 1920),
    "2k": (2560, 1440),
    "4k": (3840, 2160),
}

RESOLUTION_PRESET_LABELS: list[tuple[str, str]] = [
    ("hd", "HD (1920\u00d71080)"),
    ("hd_vertical", "HD Vertical (1080\u00d71920)"),
    ("2k", "2K (2560\u00d71440)"),
    ("4k", "4K (3840\u00d72160)"),
    ("custom", "Custom"),
]

# ------------------------------------------------------------------
# Coordinate helpers
# ------------------------------------------------------------------


def center_to_ffmpeg(
    center_x: int,
    center_y: int,
    layer_width: int,
    layer_height: int,
    output_width: int,
    output_height: int,
) -> tuple[int, int]:
    """Convert center-origin coordinates to FFmpeg top-left coordinates.

    ``(0, 0)`` in center-origin maps to a perfectly centred layer.
    """
    ffmpeg_x = (output_width // 2) + center_x - (layer_width // 2)
    ffmpeg_y = (output_height // 2) + center_y - (layer_height // 2)
    return ffmpeg_x, ffmpeg_y


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
    source_kind : str
        One of ``""``, ``"image"``, ``"video"``.
    source_duration_ms : int
        Duration of the source media in milliseconds (0 for images/unknown).
    center_x, center_y : int
        Center-origin position.  ``(0, 0)`` means the layer is centred on
        the output canvas.  Positive X is right, positive Y is down.
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
    linked_layer_id : str | None
        ID of the linked counterpart layer (audio for visual, visual for
        audio) created when a video-with-audio file is ingested.
    """

    id: str = ""
    display_name: str = ""
    asset_id: str | None = None
    asset_path: Path | None = None
    source_kind: str = ""  # "", "image", "video"
    source_duration_ms: int = 0
    center_x: int = 0
    center_y: int = 0
    width: int = 1920
    height: int = 1080
    z_order: int = 0
    start_ms: int = 0
    end_ms: int = 0
    behavior_after_end: str = "freeze_last_frame"
    enabled: bool = True
    matte_settings: dict[str, Any] = field(default_factory=lambda: copy.deepcopy(DEFAULT_MATTE_SETTINGS))
    linked_layer_id: str | None = None

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())

    def effective_duration_ms(self) -> int:
        """Return ``max(0, end_ms - start_ms)``."""
        return max(0, self.end_ms - self.start_ms)


# ------------------------------------------------------------------
# CompositionAudioLayer
# ------------------------------------------------------------------

@dataclass
class CompositionAudioLayer:
    """A single audio layer in the composition.

    Attributes
    ----------
    id : str
        Unique identifier for this audio layer (UUID).
    display_name : str
        Human-readable label.
    asset_id : str | None
        Reference to a SessionAsset id, or None for unassigned layers.
    asset_path : Path | None
        Direct file path (used when asset_id is None).
    start_ms : int
        Offset in the composition timeline (milliseconds).
    duration_ms : int
        Trimmed duration in milliseconds. 0 means full length.
    use_full_length : bool
        When True, ignore *duration_ms* and use the full source length.
    volume : float
        Playback volume multiplier (1.0 = unity gain).
    muted : bool
        When True the layer is omitted from the audio mix.
    enabled : bool
        Whether this audio layer participates in the render.
    linked_layer_id : str | None
        ID of the linked visual layer when this audio was extracted
        from a video-with-audio source.
    """

    id: str = ""
    display_name: str = ""
    asset_id: str | None = None
    asset_path: Path | None = None
    start_ms: int = 0
    duration_ms: int = 0  # 0 means full length
    use_full_length: bool = True
    source_duration_ms: int = 0
    volume: float = 1.0
    muted: bool = False
    enabled: bool = True
    linked_layer_id: str | None = None

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())

    def effective_duration_ms(self) -> int:
        """Return the effective duration: source duration when full length, else duration_ms."""
        if self.use_full_length:
            return self.source_duration_ms
        return self.duration_ms

    def effective_end_ms(self) -> int:
        """Return start_ms + effective_duration_ms()."""
        return self.start_ms + self.effective_duration_ms()


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
        self.audio_layers: list[CompositionAudioLayer] = []
        self.output_width: int = 1920
        self.output_height: int = 1080
        self.output_fps: float = 30.0
        self.resolution_preset: str = "hd"  # "hd", "hd_vertical", "2k", "4k", "custom"

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

    def get_audio_layer(self, layer_id: str) -> CompositionAudioLayer | None:
        """Return the audio layer with *layer_id*, or ``None``."""
        for al in self.audio_layers:
            if al.id == layer_id:
                return al
        return None

    def move_layer(self, layer_id: str, center_x: int, center_y: int) -> None:
        """Update center-origin position of the layer with *layer_id*."""
        layer = self.get_layer(layer_id)
        if layer is not None:
            layer.center_x = center_x
            layer.center_y = center_y

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
        """Return the maximum end time of all enabled layers and audio layers."""
        if not self.layers and not self.audio_layers:
            return 0
        max_ms = 0
        for layer in self.layers:
            if layer.enabled:
                max_ms = max(max_ms, layer.start_ms + layer.effective_duration_ms())
        for al in self.audio_layers:
            if al.enabled:
                max_ms = max(max_ms, al.effective_end_ms())
        return max_ms

    def get_layers_sorted(self) -> list[CompositionLayer]:
        """Return layers sorted by z_order (lowest first)."""
        return sorted(self.layers, key=lambda l: l.z_order)

    # -- serialization ---------------------------------------------

    # Composition schema version — must be present in serialized data
    # to prevent loading pre-center-origin payloads.
    COMPOSITION_SCHEMA_VERSION = 2

    def to_dict(self) -> dict[str, Any]:
        """Serialize the model to a plain dictionary."""
        layers_out: list[dict] = []
        for layer in self.layers:
            layer_dict: dict[str, Any] = {
                "id": layer.id,
                "display_name": layer.display_name,
                "asset_id": layer.asset_id,
                "asset_path": str(layer.asset_path) if layer.asset_path else None,
                "source_kind": layer.source_kind,
                "source_duration_ms": layer.source_duration_ms,
                "center_x": layer.center_x,
                "center_y": layer.center_y,
                "width": layer.width,
                "height": layer.height,
                "z_order": layer.z_order,
                "start_ms": layer.start_ms,
                "end_ms": layer.end_ms,
                "behavior_after_end": layer.behavior_after_end,
                "enabled": layer.enabled,
                "matte_settings": copy.deepcopy(layer.matte_settings),
                "linked_layer_id": layer.linked_layer_id,
            }
            layers_out.append(layer_dict)

        audio_layers_out: list[dict] = []
        for al in self.audio_layers:
            audio_layers_out.append({
                "id": al.id,
                "display_name": al.display_name,
                "asset_id": al.asset_id,
                "asset_path": str(al.asset_path) if al.asset_path else None,
                "start_ms": al.start_ms,
                "duration_ms": al.duration_ms,
                "use_full_length": al.use_full_length,
                "source_duration_ms": al.source_duration_ms,
                "volume": al.volume,
                "muted": al.muted,
                "enabled": al.enabled,
                "linked_layer_id": al.linked_layer_id,
            })

        return {
            "composition_schema_version": self.COMPOSITION_SCHEMA_VERSION,
            "layers": layers_out,
            "audio_layers": audio_layers_out,
            "output_width": self.output_width,
            "output_height": self.output_height,
            "output_fps": self.output_fps,
            "resolution_preset": self.resolution_preset,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompositionModel:
        """Restore a model from a dictionary produced by :meth:`to_dict`.

        Raises
        ------
        ValueError
            If the payload was created before the center-origin coordinate
            system (missing or old ``composition_schema_version``).
        """
        schema_ver = data.get("composition_schema_version")
        if schema_ver is None or schema_ver < cls.COMPOSITION_SCHEMA_VERSION:
            raise ValueError(
                "This composition was created with an older coordinate system "
                "(top-left origin) that is incompatible with v0.7.0's center-origin "
                "coordinates. Please recreate the composition."
            )
        model = cls()
        model.output_width = data.get("output_width", 1920)
        model.output_height = data.get("output_height", 1080)
        model.output_fps = data.get("output_fps", 30.0)
        model.resolution_preset = data.get("resolution_preset", "custom")

        for layer_dict in data.get("layers", []):
            asset_path = layer_dict.get("asset_path")
            layer = CompositionLayer(
                id=layer_dict.get("id", ""),
                display_name=layer_dict.get("display_name", ""),
                asset_id=layer_dict.get("asset_id"),
                asset_path=Path(asset_path) if asset_path else None,
                source_kind=layer_dict.get("source_kind", ""),
                source_duration_ms=layer_dict.get("source_duration_ms", 0),
                center_x=layer_dict.get("center_x", 0),
                center_y=layer_dict.get("center_y", 0),
                width=layer_dict.get("width", 1920),
                height=layer_dict.get("height", 1080),
                z_order=layer_dict.get("z_order", 0),
                start_ms=layer_dict.get("start_ms", 0),
                end_ms=layer_dict.get("end_ms", 0),
                behavior_after_end=layer_dict.get("behavior_after_end", "freeze_last_frame"),
                enabled=layer_dict.get("enabled", True),
                matte_settings=layer_dict.get("matte_settings", copy.deepcopy(DEFAULT_MATTE_SETTINGS)),
                linked_layer_id=layer_dict.get("linked_layer_id"),
            )
            model.layers.append(layer)

        for al_dict in data.get("audio_layers", []):
            ap = al_dict.get("asset_path")
            al = CompositionAudioLayer(
                id=al_dict.get("id", ""),
                display_name=al_dict.get("display_name", ""),
                asset_id=al_dict.get("asset_id"),
                asset_path=Path(ap) if ap else None,
                start_ms=al_dict.get("start_ms", 0),
                duration_ms=al_dict.get("duration_ms", 0),
                use_full_length=al_dict.get("use_full_length", True),
                source_duration_ms=al_dict.get("source_duration_ms", 0),
                volume=al_dict.get("volume", 1.0),
                muted=al_dict.get("muted", False),
                enabled=al_dict.get("enabled", True),
                linked_layer_id=al_dict.get("linked_layer_id"),
            )
            model.audio_layers.append(al)

        return model
