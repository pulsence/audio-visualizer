"""
Fade animation implementation.

Simple fade-in and fade-out animation using ASS \\fad tag.
"""

from typing import Dict, Any, Optional

import pysubs2

from .base import BaseAnimation
from .registry import AnimationRegistry


@AnimationRegistry.register
class FadeAnimation(BaseAnimation):
    """
    Simple fade-in/fade-out animation using ASS \\fad tag.

    Parameters:
        in_ms: Fade-in duration in milliseconds (default: 120)
        out_ms: Fade-out duration in milliseconds (default: 120)

    Example preset:
        {
            "animation": {
                "type": "fade",
                "in_ms": 150,
                "out_ms": 100
            }
        }
    """

    animation_type = "fade"

    def validate_params(self) -> None:
        """Validate that in_ms and out_ms are present."""
        required = ["in_ms", "out_ms"]
        for key in required:
            if key not in self.params:
                raise ValueError(
                    f"FadeAnimation requires '{key}' parameter. "
                    f"Got: {list(self.params.keys())}"
                )

    def generate_ass_override(self, event_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate \\fad(in,out) override tag.

        Values are clamped to [0, 2000] range for safety.
        """
        in_ms = self._clamp(int(self.params["in_ms"]), 0, 2000)
        out_ms = self._clamp(int(self.params["out_ms"]), 0, 2000)
        return rf"\fad({in_ms},{out_ms})"

    def apply_to_event(self, event: pysubs2.SSAEvent, **kwargs) -> None:
        """Apply fade animation to the event text."""
        override = self.generate_ass_override()
        event.text = self._inject_override(event.text, override)

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        """Default fade parameters."""
        return {
            "in_ms": 120,
            "out_ms": 120
        }
