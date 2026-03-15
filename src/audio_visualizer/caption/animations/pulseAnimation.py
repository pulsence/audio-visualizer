"""Pulse animation — audio-reactive scale pulsing.

Applies a subtle scale pulse synchronized to audio amplitude.
When event_context contains reactive data, the scale amount is
modulated by the per-frame amplitude at the event's time position.
"""
from typing import Any, Dict, Optional

import pysubs2

from .baseAnimation import BaseAnimation
from .registry import AnimationRegistry


@AnimationRegistry.register
class PulseAnimation(BaseAnimation):
    """Audio-reactive pulse animation using scale transforms.

    Applies a scale pulse at the start of each event that settles
    back to normal size.  When audio-reactive data is available,
    the pulse intensity is proportional to the amplitude at that
    event's start time.

    Parameters:
        in_ms: Duration of the pulse-in phase (default: 150)
        out_ms: Fade-out duration (default: 120)
        min_scale: Minimum scale percentage (default: 100)
        max_scale: Maximum scale percentage at peak amplitude (default: 115)
        accel: Easing acceleration factor (default: 0.8)
    """

    animation_type = "pulse"

    def validate_params(self) -> None:
        required = ["in_ms", "out_ms"]
        for key in required:
            if key not in self.params:
                raise ValueError(
                    f"PulseAnimation requires '{key}' parameter. "
                    f"Got: {list(self.params.keys())}"
                )

    def generate_ass_override(
        self, event_context: Optional[Dict[str, Any]] = None
    ) -> str:
        in_ms = self._clamp(int(self.params["in_ms"]), 0, 2000)
        out_ms = self._clamp(int(self.params["out_ms"]), 0, 2000)
        min_scale = int(self.params.get("min_scale", 100))
        max_scale = int(self.params.get("max_scale", 115))
        accel = float(self.params.get("accel", 0.8))

        # Determine amplitude-driven scale
        amplitude = 1.0
        if event_context and "amplitude" in event_context:
            amplitude = max(0.0, min(1.0, float(event_context["amplitude"])))

        start_scale = min_scale + int((max_scale - min_scale) * amplitude)

        return (
            rf"\fscx{start_scale}\fscy{start_scale}"
            rf"\t(0,{in_ms},{accel},\fscx{min_scale}\fscy{min_scale})"
            rf"\fad({in_ms},{out_ms})"
        )

    def apply_to_event(self, event: pysubs2.SSAEvent, **kwargs) -> None:
        event_context = kwargs.get("event_context")
        override = self.generate_ass_override(event_context)
        event.text = self._inject_override(event.text, override)

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {
            "in_ms": 150,
            "out_ms": 120,
            "min_scale": 100,
            "max_scale": 115,
            "accel": 0.8,
        }
