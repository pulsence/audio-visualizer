"""
Slide-up animation implementation.

Text slides up from below its final position while fading in.
"""

from typing import Dict, Any, Optional, Tuple

import pysubs2

from .base import BaseAnimation
from .registry import AnimationRegistry


@AnimationRegistry.register
class SlideUpAnimation(BaseAnimation):
    """
    Slide-up animation with fade.

    Text starts below its final position and slides up while fading in.

    Parameters:
        in_ms: Slide-up and fade-in duration (default: 140)
        out_ms: Fade-out duration (default: 120)
        move_px: Distance to move in pixels (default: 26)

    Example preset:
        {
            "animation": {
                "type": "slide_up",
                "in_ms": 140,
                "out_ms": 120,
                "move_px": 26
            }
        }
    """

    animation_type = "slide_up"

    def validate_params(self) -> None:
        """Validate required parameters."""
        required = ["in_ms", "out_ms", "move_px"]
        for key in required:
            if key not in self.params:
                raise ValueError(
                    f"SlideUpAnimation requires '{key}' parameter. "
                    f"Got: {list(self.params.keys())}"
                )

    def needs_positioning(self) -> bool:
        """Slide animation requires position calculation."""
        return True

    def supports_placeholder_substitution(self) -> bool:
        """Uses placeholders for coordinates."""
        return True

    def generate_ass_override(self, event_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate \\move and \\fad tags with placeholders.

        Placeholders {X}, {Y}, {Y_PLUS_DY} will be substituted later.
        """
        in_ms = self._clamp(int(self.params["in_ms"]), 0, 4000)
        out_ms = self._clamp(int(self.params["out_ms"]), 0, 2000)

        # Return with placeholders that will be substituted after sizing
        return (
            rf"\fad({in_ms},{out_ms})"
            rf"\move({{X}},{{Y_PLUS_DY}},{{X}},{{Y}},0,{in_ms})"
        )

    def substitute_placeholders(
        self,
        text: str,
        position: Tuple[int, int],
        **kwargs
    ) -> str:
        """
        Replace {X}, {Y}, {Y_PLUS_DY} with actual coordinates.

        Args:
            text: Text containing placeholders
            position: Final (x, y) position
            **kwargs: Additional context (ignored)

        Returns:
            Text with placeholders replaced
        """
        x, y = position
        move_px = int(self.params["move_px"])
        y_plus_dy = y + move_px

        return (text
                .replace("{X}", str(x))
                .replace("{Y}", str(y))
                .replace("{Y_PLUS_DY}", str(y_plus_dy)))

    def apply_to_event(self, event: pysubs2.SSAEvent, **kwargs) -> None:
        """Apply slide-up animation to the event text."""
        override = self.generate_ass_override()
        event.text = self._inject_override(event.text, override)

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        """Default slide-up parameters."""
        return {
            "in_ms": 140,
            "out_ms": 120,
            "move_px": 26
        }
