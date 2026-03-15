"""
Blur settle animation implementation.

Text starts blurred and becomes sharp.
"""

from typing import Dict, Any, Optional

import pysubs2

from .base import BaseAnimation
from .registry import AnimationRegistry


@AnimationRegistry.register
class BlurSettleAnimation(BaseAnimation):
    """
    Blur settle animation using ASS \\blur and \\t transform.

    Text starts blurred and smoothly becomes sharp.

    Parameters:
        in_ms: Duration of blur animation (default: 200)
        out_ms: Fade-out duration (default: 120)
        start_blur: Starting blur amount (default: 4)
        end_blur: Ending blur amount (default: 0)
        accel: Acceleration factor for ease (default: 1.0)

    Example preset:
        {
            "animation": {
                "type": "blur_settle",
                "in_ms": 200,
                "out_ms": 120,
                "start_blur": 4,
                "end_blur": 0,
                "accel": 1.0
            }
        }
    """

    animation_type = "blur_settle"

    def validate_params(self) -> None:
        """Validate required parameters."""
        required = ["in_ms", "out_ms"]
        for key in required:
            if key not in self.params:
                raise ValueError(
                    f"BlurSettleAnimation requires '{key}' parameter. "
                    f"Got: {list(self.params.keys())}"
                )

    def generate_ass_override(self, event_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate \\blur and \\t transform tags.

        Uses \\t to animate from start_blur to end_blur over in_ms duration.
        """
        in_ms = self._clamp(int(self.params["in_ms"]), 0, 4000)
        out_ms = self._clamp(int(self.params["out_ms"]), 0, 2000)
        start_blur = int(self.params.get("start_blur", 4))
        end_blur = int(self.params.get("end_blur", 0))
        accel = float(self.params.get("accel", 1.0))

        return (
            rf"\blur{start_blur}"
            rf"\t(0,{in_ms},{accel},\blur{end_blur})"
            rf"\fad({in_ms},{out_ms})"
        )

    def apply_to_event(self, event: pysubs2.SSAEvent, **kwargs) -> None:
        """Apply blur settle animation to the event text."""
        override = self.generate_ass_override()
        event.text = self._inject_override(event.text, override)

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        """Default blur settle parameters."""
        return {
            "in_ms": 200,
            "out_ms": 120,
            "start_blur": 4,
            "end_blur": 0,
            "accel": 1.0
        }
