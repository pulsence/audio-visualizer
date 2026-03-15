"""Emphasis glow animation — audio-reactive blur glow effect.

Applies a subtle blur glow that intensifies during high-amplitude
or emphasis regions of the audio.
"""
from typing import Any, Dict, Optional

import pysubs2

from .baseAnimation import BaseAnimation
from .registry import AnimationRegistry


@AnimationRegistry.register
class EmphasisGlowAnimation(BaseAnimation):
    """Audio-reactive emphasis glow animation.

    Applies a blur-based glow effect that starts prominent and
    settles to clean text.  When audio-reactive data is available,
    the glow intensity tracks the amplitude at the event's position.

    Parameters:
        in_ms: Duration of the glow settle phase (default: 200)
        out_ms: Fade-out duration (default: 120)
        min_blur: Minimum blur strength (default: 0)
        max_blur: Maximum blur strength at peak amplitude (default: 6)
        accel: Easing acceleration (default: 1.0)
    """

    animation_type = "emphasis_glow"

    def validate_params(self) -> None:
        required = ["in_ms", "out_ms"]
        for key in required:
            if key not in self.params:
                raise ValueError(
                    f"EmphasisGlowAnimation requires '{key}' parameter. "
                    f"Got: {list(self.params.keys())}"
                )

    def generate_ass_override(
        self, event_context: Optional[Dict[str, Any]] = None
    ) -> str:
        in_ms = self._clamp(int(self.params["in_ms"]), 0, 4000)
        out_ms = self._clamp(int(self.params["out_ms"]), 0, 2000)
        min_blur = int(self.params.get("min_blur", 0))
        max_blur = int(self.params.get("max_blur", 6))
        accel = float(self.params.get("accel", 1.0))

        # Audio-reactive: scale blur based on amplitude
        start_blur = max_blur
        if event_context and "amplitude" in event_context:
            amplitude = max(0.0, min(1.0, float(event_context["amplitude"])))
            start_blur = min_blur + int((max_blur - min_blur) * amplitude)

        return (
            rf"\blur{start_blur}"
            rf"\t(0,{in_ms},{accel},\blur{min_blur})"
            rf"\fad({in_ms},{out_ms})"
        )

    def apply_to_event(self, event: pysubs2.SSAEvent, **kwargs) -> None:
        event_context = kwargs.get("event_context")
        override = self.generate_ass_override(event_context)
        event.text = self._inject_override(event.text, override)

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {
            "in_ms": 200,
            "out_ms": 120,
            "min_blur": 0,
            "max_blur": 6,
            "accel": 1.0,
        }
