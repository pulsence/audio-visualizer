"""
Scale settle animation implementation.

Text starts larger and scales down to normal size.
"""

from typing import Dict, Any, Optional

import pysubs2

from .base import BaseAnimation
from .registry import AnimationRegistry


@AnimationRegistry.register
class ScaleSettleAnimation(BaseAnimation):
    """
    Scale settle animation using ASS \\fscx/\\fscy and \\t transform.

    Text starts at a larger scale and smoothly settles to 100% size.

    Parameters:
        in_ms: Duration of scale animation (default: 200)
        out_ms: Fade-out duration (default: 120)
        start_scale: Starting scale percentage (default: 110)
        end_scale: Ending scale percentage (default: 100)
        accel: Acceleration factor for ease (default: 1.0)

    Example preset:
        {
            "animation": {
                "type": "scale_settle",
                "in_ms": 200,
                "out_ms": 120,
                "start_scale": 110,
                "end_scale": 100,
                "accel": 1.0
            }
        }
    """

    animation_type = "scale_settle"

    def validate_params(self) -> None:
        """Validate required parameters."""
        required = ["in_ms", "out_ms"]
        for key in required:
            if key not in self.params:
                raise ValueError(
                    f"ScaleSettleAnimation requires '{key}' parameter. "
                    f"Got: {list(self.params.keys())}"
                )

    def generate_ass_override(self, event_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate \\fscx/\\fscy and \\t transform tags.

        Uses \\t to animate from start_scale to end_scale over in_ms duration.
        """
        in_ms = self._clamp(int(self.params["in_ms"]), 0, 4000)
        out_ms = self._clamp(int(self.params["out_ms"]), 0, 2000)
        start = int(self.params.get("start_scale", 110))
        end = int(self.params.get("end_scale", 100))
        accel = float(self.params.get("accel", 1.0))

        return (
            rf"\fscx{start}\fscy{start}"
            rf"\t(0,{in_ms},{accel},\fscx{end}\fscy{end})"
            rf"\fad({in_ms},{out_ms})"
        )

    def apply_to_event(self, event: pysubs2.SSAEvent, **kwargs) -> None:
        """Apply scale settle animation to the event text."""
        override = self.generate_ass_override()
        event.text = self._inject_override(event.text, override)

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        """Default scale settle parameters."""
        return {
            "in_ms": 200,
            "out_ms": 120,
            "start_scale": 110,
            "end_scale": 100,
            "accel": 1.0
        }
