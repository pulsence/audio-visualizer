"""Word highlight animation — per-word emphasis with color, scale, and blur.

Highlights words one-by-one during the subtitle event using per-word
ASS override events.  When ``==word==`` markers are present, those words
receive stronger emphasis treatment (larger scale, brighter color).

Supports three timing modes:
- ``even``: Equal time per word.
- ``weighted``: Time proportional to word length.
- ``word_level``: Uses precise word-level timing from bundle data when
  available (falls back to ``even`` otherwise).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import pysubs2

from .baseAnimation import BaseAnimation
from .registry import AnimationRegistry


@AnimationRegistry.register
class WordHighlightAnimation(BaseAnimation):
    """Per-word highlight animation using ASS override tags.

    Parameters:
        mode: Timing mode — ``even``, ``weighted``, or ``word_level``
              (default: ``even``)
        highlight_color: Highlight color in ``#RRGGBB`` (default: ``#FFFF00``)
        normal_color: Color for non-highlighted words (default: None, keeps
                      style primary color)
        highlight_scale: Scale percentage for highlighted word (default: 110)
        highlight_blur: Extra blur applied during highlight (default: 1)
        emphasis_scale: Scale for ``==...==`` marked words (default: 120)
        emphasis_color: Color for ``==...==`` words (default: ``#FF8800``)
        transition_ms: Per-word transition duration (default: 80)
    """

    animation_type = "word_highlight"

    def validate_params(self) -> None:
        """Word highlight uses all default parameters — always valid."""
        pass

    def generate_ass_override(
        self, event_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Not used — full text transformation happens in apply_to_event."""
        return ""

    def apply_to_event(self, event: pysubs2.SSAEvent, **kwargs) -> None:
        """Transform event text into per-word highlight segments."""
        duration_ms = int(event.end) - int(event.start)
        word_timing = kwargs.get("word_timing")
        event.text = self._build_highlight_text(
            event.text, duration_ms, word_timing=word_timing
        )

    def _build_highlight_text(
        self,
        text: str,
        duration_ms: int,
        word_timing: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Build ASS text with per-word highlight overrides."""
        from ..core.markdownToAss import (
            extract_highlight_words,
            strip_ass_overrides,
            strip_highlight_markers,
        )

        # Identify explicitly highlighted words before stripping markers
        emphasis_words = set(
            w.lower() for w in extract_highlight_words(text)
        )

        # Strip ASS overrides and highlight markers for clean tokenization
        plain = strip_ass_overrides(text)
        plain = strip_highlight_markers(plain)

        # Tokenize
        tokens = self._tokenize(plain)
        if not tokens:
            return text

        word_indices = [
            i for i, t in enumerate(tokens) if self._is_word(t)
        ]
        if not word_indices:
            return text

        # Parameters
        mode = str(self.params.get("mode", "even")).strip().lower()
        hl_color = self.params.get("highlight_color", "#FFFF00")
        normal_color = self.params.get("normal_color")
        hl_scale = int(self.params.get("highlight_scale", 110))
        hl_blur = int(self.params.get("highlight_blur", 1))
        em_scale = int(self.params.get("emphasis_scale", 120))
        em_color = self.params.get("emphasis_color", "#FF8800")
        transition_ms = int(self.params.get("transition_ms", 80))

        # Allocate timing
        token_ms = self._allocate_timing(
            tokens, word_indices, duration_ms, mode, word_timing
        )

        # Build output
        return self._build_output(
            tokens,
            token_ms,
            word_indices,
            emphasis_words,
            hl_color=hl_color,
            normal_color=normal_color,
            hl_scale=hl_scale,
            hl_blur=hl_blur,
            em_scale=em_scale,
            em_color=em_color,
            transition_ms=transition_ms,
        )

    # -- Tokenization helpers ---------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Tokenize text into words, punctuation, and newlines."""
        text = text.replace(r"\N", "\n")
        parts: List[str] = []
        for i, line in enumerate(text.split("\n")):
            words = re.findall(
                r"\w+(?:'\w+)?[^\w\s]*|[^\w\s]+", line, flags=re.UNICODE
            )
            parts.extend(words)
            if i < len(text.split("\n")) - 1:
                parts.append("\n")
        return parts

    @staticmethod
    def _is_word(token: str) -> bool:
        return token != "\n" and bool(re.match(r"^\w", token, re.UNICODE))

    # -- Timing allocation ------------------------------------------------

    def _allocate_timing(
        self,
        tokens: List[str],
        word_indices: List[int],
        duration_ms: int,
        mode: str,
        word_timing: Optional[List[Dict[str, Any]]] = None,
    ) -> List[int]:
        """Distribute duration across tokens."""
        token_ms = [0] * len(tokens)

        if mode == "word_level" and word_timing and len(word_timing) >= len(word_indices):
            # Use precise per-word timing from bundle
            for idx, wi in enumerate(word_indices):
                if idx < len(word_timing):
                    wt = word_timing[idx]
                    token_ms[wi] = int(
                        (wt.get("end", 0) - wt.get("start", 0)) * 1000
                    )
            # Fallback: if total is 0, use even
            if sum(token_ms) == 0:
                mode = "even"
            else:
                return token_ms

        if mode == "weighted":
            lengths = [len(tokens[i]) for i in word_indices]
            total_len = sum(lengths) or 1
            for j, i in enumerate(word_indices):
                token_ms[i] = int(round(duration_ms * (lengths[j] / total_len)))
        else:
            # even (default)
            per_word = duration_ms / max(1, len(word_indices))
            for i in word_indices:
                token_ms[i] = int(round(per_word))

        # Renormalize
        total = sum(token_ms)
        if total > 0:
            scale = duration_ms / total
            token_ms = [int(round(t * scale)) for t in token_ms]

        return token_ms

    # -- Output builder ---------------------------------------------------

    def _build_output(
        self,
        tokens: List[str],
        token_ms: List[int],
        word_indices: List[int],
        emphasis_words: set,
        *,
        hl_color: str,
        normal_color: Optional[str],
        hl_scale: int,
        hl_blur: int,
        em_scale: int,
        em_color: str,
        transition_ms: int,
    ) -> str:
        """Assemble final ASS text with highlight overrides per word."""

        def _to_ass_color(hex_color: str) -> str:
            """Convert #RRGGBB to ASS &HBBGGRR."""
            if hex_color.startswith("#") and len(hex_color) == 7:
                r, g, b = hex_color[1:3], hex_color[3:5], hex_color[5:7]
                return f"&H{b.upper()}{g.upper()}{r.upper()}"
            return hex_color

        def ms_to_cs(ms: int) -> int:
            return max(0, int(round(ms / 10.0)))

        ass_hl = _to_ass_color(hl_color)
        ass_em = _to_ass_color(em_color)

        out = ""
        word_set = set(word_indices)
        cumulative_ms = 0
        prev: Optional[str] = None

        for i, token in enumerate(tokens):
            if token == "\n":
                out += r"\N"
                prev = "\n"
                continue

            # Spacing
            if prev is not None and prev != "\n":
                if token and token[0].isalnum():
                    out += " "

            if i in word_set:
                clean = re.sub(r"[^\w']", "", token, flags=re.UNICODE).lower()
                is_emphasis = clean in emphasis_words

                t_start = cumulative_ms
                t_end = t_start + token_ms[i]
                half_trans = transition_ms // 2

                if is_emphasis:
                    color = ass_em
                    scale = em_scale
                else:
                    color = ass_hl
                    scale = hl_scale

                # Karaoke tag (\kf for smooth fill)
                cs = ms_to_cs(token_ms[i])
                out += (
                    r"{\kf" + str(cs) + r"\1c" + color
                    + r"\fscx" + str(scale) + r"\fscy" + str(scale)
                    + r"\blur" + str(hl_blur)
                    + r"\t(" + str(t_start) + "," + str(t_start + half_trans)
                    + r",\fscx100\fscy100\blur0"
                )
                if normal_color:
                    out += r"\1c" + _to_ass_color(normal_color)
                out += r")}" + token

                cumulative_ms = t_end
            else:
                # Non-word tokens (standalone punctuation)
                out += token

            prev = token

        return out

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        return {
            "mode": "even",
            "highlight_color": "#FFFF00",
            "normal_color": None,
            "highlight_scale": 110,
            "highlight_blur": 1,
            "emphasis_scale": 120,
            "emphasis_color": "#FF8800",
            "transition_ms": 80,
        }
