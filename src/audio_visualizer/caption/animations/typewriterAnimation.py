"""Typewriter animation — character-by-character text reveal.

Reveals subtitle text one character at a time using ASS karaoke
timing tags, with an optional blinking cursor character.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import pysubs2

from .baseAnimation import BaseAnimation
from .registry import AnimationRegistry


@AnimationRegistry.register
class TypewriterAnimation(BaseAnimation):
    """Character-by-character typewriter reveal animation.

    Text appears one character at a time over the subtitle event
    duration.  An optional cursor character follows the reveal
    position and can blink at a configurable rate.

    Parameters:
        cursor_char: Character to use as the cursor (default: ``|``)
        cursor_blink_ms: Blink cycle duration in ms (default: 500).
                         Set to 0 to disable blinking.
        lead_in_ms: Delay before first character appears (default: 0)
        chars_per_sec: Reveal speed hint.  0 means auto-fit to event
                       duration (default: 0).
        show_cursor: Whether to append a cursor (default: True)
    """

    animation_type = "typewriter"

    def validate_params(self) -> None:
        """Typewriter uses all default parameters — always valid."""
        pass

    def generate_ass_override(
        self, event_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Not used — full text is rebuilt in apply_to_event."""
        return ""

    def apply_to_event(self, event: pysubs2.SSAEvent, **kwargs) -> None:
        """Transform event text into a typewriter reveal sequence."""
        duration_ms = int(event.end) - int(event.start)
        event.text = self._build_typewriter_text(event.text, duration_ms)

    def _build_typewriter_text(
        self, text: str, duration_ms: int
    ) -> str:
        """Build ASS text with per-character karaoke tags."""
        from ..core.markdownToAss import strip_ass_overrides

        # Strip existing ASS overrides for clean character list
        plain = strip_ass_overrides(text)
        # Normalize ASS newlines
        plain = plain.replace(r"\N", "\n")

        chars = list(plain)
        if not chars:
            return text

        # Parameters
        lead_in_ms = int(self.params.get("lead_in_ms", 0))
        chars_per_sec = float(self.params.get("chars_per_sec", 0))
        cursor_char = str(self.params.get("cursor_char", "|"))
        cursor_blink_ms = int(self.params.get("cursor_blink_ms", 500))
        show_cursor = bool(self.params.get("show_cursor", True))

        # Compute per-character timing
        available_ms = max(0, duration_ms - lead_in_ms)
        if available_ms <= 0:
            return text

        if chars_per_sec > 0:
            char_ms = int(round(1000.0 / chars_per_sec))
        else:
            char_ms = max(1, available_ms // max(1, len(chars)))

        def ms_to_cs(ms: int) -> int:
            return max(0, int(round(ms / 10.0)))

        out = ""

        # Lead-in silence
        if lead_in_ms > 0:
            out += r"{\k" + str(ms_to_cs(lead_in_ms)) + "}"

        # Character-by-character karaoke tags
        for ch in chars:
            if ch == "\n":
                out += r"\N"
                continue
            cs = ms_to_cs(char_ms)
            out += r"{\k" + str(cs) + "}" + ch

        # Cursor: render as a final karaoke segment that blinks
        if show_cursor and cursor_char:
            remaining = max(0, available_ms - char_ms * len(chars))
            if cursor_blink_ms > 0 and remaining > cursor_blink_ms:
                # Blink by alternating visible/invisible with \alpha tags
                blinks = max(1, remaining // cursor_blink_ms)
                half = cursor_blink_ms // 2
                out += (
                    r"{\alpha&HFF&\t(0," + str(half) + r",\alpha&H00&)"
                    + r"\t(" + str(half) + "," + str(cursor_blink_ms)
                    + r",\alpha&HFF&)}"
                    + cursor_char
                )
            else:
                # Static cursor for remaining duration
                cs = ms_to_cs(remaining) if remaining > 0 else 1
                out += r"{\k" + str(cs) + "}" + cursor_char

        return out

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {
            "cursor_char": "|",
            "cursor_blink_ms": 500,
            "lead_in_ms": 0,
            "chars_per_sec": 0,
            "show_cursor": True,
        }
