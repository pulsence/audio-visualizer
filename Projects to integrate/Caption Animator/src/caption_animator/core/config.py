"""
Configuration management and preset handling.

This module defines dataclasses for managing preset configurations
in a type-safe manner.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List
import json


@dataclass
class AnimationConfig:
    """
    Animation configuration extracted from preset.

    Attributes:
        type: Animation type name (e.g., "fade", "slide_up")
        params: Animation-specific parameters
    """
    type: str
    params: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnimationConfig":
        """
        Create AnimationConfig from dictionary.

        Args:
            data: Dictionary with 'type' and optional other parameters

        Returns:
            AnimationConfig instance
        """
        if not isinstance(data, dict):
            raise ValueError(f"Animation config must be a dict, got {type(data)}")

        if "type" not in data:
            raise ValueError("Animation config must have 'type' field")

        # Extract type and use everything else as params
        atype = data["type"]
        params = {k: v for k, v in data.items() if k != "type"}

        return cls(type=atype, params=params)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        result = {"type": self.type}
        result.update(self.params)
        return result


@dataclass
class PresetConfig:
    """
    Complete preset configuration.

    This replaces the nested dictionaries used in the original implementation
    with a type-safe dataclass.
    """

    # Font settings
    font_file: str = ""
    font_name: str = "Arial"
    font_size: int = 64
    bold: bool = False
    italic: bool = False

    # Color settings (hex format: #RRGGBB)
    primary_color: str = "#FFFFFF"
    outline_color: str = "#000000"
    shadow_color: str = "#000000"

    # Styling (pixels/floats)
    outline_px: float = 4.0
    shadow_px: float = 2.0
    blur_px: float = 0.0

    # Layout
    line_spacing: int = 8
    max_width_px: int = 1200
    padding: List[int] = field(default_factory=lambda: [40, 60, 50, 60])  # [top, right, bottom, left]
    alignment: int = 2  # ASS alignment (2 = bottom-center)
    margin_l: int = 0
    margin_r: int = 0
    margin_v: int = 0
    wrap_style: int = 2  # 2 = smart wrapping

    # Animation
    animation: Optional[AnimationConfig] = None

    # Video codec settings
    video_codec: str = "libx264"  # Default to H.264 for smaller files
    video_quality: str = "small"  # small (H.264), medium (ProRes 422 HQ), large (ProRes 4444)
    h264_crf: int = 18  # 18 = visually lossless for H.264
    prores_profile: int = 3  # 3 = ProRes 422 HQ, 4 = ProRes 4444

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PresetConfig":
        """
        Create PresetConfig from dictionary.

        Args:
            data: Dictionary with preset fields

        Returns:
            PresetConfig instance with all fields populated
        """
        # Handle animation separately
        animation = None
        if "animation" in data and data["animation"]:
            animation = AnimationConfig.from_dict(data["animation"])

        # Extract known fields
        config_data = {
            k: v for k, v in data.items()
            if k in cls.__dataclass_fields__ and k != "animation"
        }

        return cls(animation=animation, **config_data)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary format.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        result = asdict(self)

        # Convert animation to dict if present
        if self.animation:
            result["animation"] = self.animation.to_dict()

        return result

    def merge_with(self, other: "PresetConfig") -> "PresetConfig":
        """
        Merge this preset with another, with other taking precedence.

        Args:
            other: Preset to merge with (values from other override this)

        Returns:
            New PresetConfig with merged values
        """
        # Start with this preset's values
        merged_dict = self.to_dict()

        # Update with other's values (excluding None)
        other_dict = other.to_dict()
        for key, value in other_dict.items():
            if value is not None:
                merged_dict[key] = value

        return PresetConfig.from_dict(merged_dict)

    def to_json(self, indent: int = 2, sort_keys: bool = True) -> str:
        """
        Convert to JSON string.

        Args:
            indent: Number of spaces for indentation
            sort_keys: Whether to sort keys alphabetically

        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), indent=indent, sort_keys=sort_keys)

    @classmethod
    def from_json(cls, json_str: str) -> "PresetConfig":
        """
        Create from JSON string.

        Args:
            json_str: JSON string representation

        Returns:
            PresetConfig instance
        """
        data = json.loads(json_str)
        return cls.from_dict(data)
