"""Beat pop animation — audio-reactive pop-in effect.

Text pops in with a quick scale overshoot synchronized to beat
markers from audio analysis.
"""
from typing import Any, Dict, Optional

import pysubs2

from .baseAnimation import BaseAnimation
from .registry import AnimationRegistry


@AnimationRegistry.register
class BeatPopAnimation(BaseAnimation):
    """Audio-reactive beat pop animation.

    Text pops in with a brief scale overshoot then settles to normal
    size.  The overshoot intensity increases when the event coincides
    with a detected beat or peak in the audio.

    Parameters:
        in_ms: Duration of pop-in phase (default: 100)
        out_ms: Fade-out duration (default: 120)
        pop_scale: Scale percentage during the pop (default: 125)
        settle_scale: Final scale percentage (default: 100)
        accel: Easing acceleration (default: 0.5)
    """

    animation_type = "beat_pop"

    def validate_params(self) -> None:
        required = ["in_ms", "out_ms"]
        for key in required:
            if key not in self.params:
                raise ValueError(
                    f"BeatPopAnimation requires '{key}' parameter. "
                    f"Got: {list(self.params.keys())}"
                )

    def generate_ass_override(
        self, event_context: Optional[Dict[str, Any]] = None
    ) -> str:
        in_ms = self._clamp(int(self.params["in_ms"]), 0, 2000)
        out_ms = self._clamp(int(self.params["out_ms"]), 0, 2000)
        pop_scale = int(self.params.get("pop_scale", 125))
        settle_scale = int(self.params.get("settle_scale", 100))
        accel = float(self.params.get("accel", 0.5))

        # Audio-reactive: boost pop scale based on amplitude
        if event_context and "amplitude" in event_context:
            amplitude = max(0.0, min(1.0, float(event_context["amplitude"])))
            extra = int((pop_scale - settle_scale) * amplitude * 0.3)
            pop_scale += extra

        return (
            rf"\fscx{pop_scale}\fscy{pop_scale}"
            rf"\t(0,{in_ms},{accel},\fscx{settle_scale}\fscy{settle_scale})"
            rf"\fad({in_ms},{out_ms})"
        )

    def apply_to_event(self, event: pysubs2.SSAEvent, **kwargs) -> None:
        event_context = kwargs.get("event_context")
        override = self.generate_ass_override(event_context)
        event.text = self._inject_override(event.text, override)

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {
            "in_ms": 100,
            "out_ms": 120,
            "pop_scale": 125,
            "settle_scale": 100,
            "accel": 0.5,
        }
