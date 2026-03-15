"""
Word reveal (karaoke) animation implementation.

Text appears word-by-word with timing control.
"""

from typing import Dict, Any, Optional, List
import re

import pysubs2

from .base import BaseAnimation
from .registry import AnimationRegistry


@AnimationRegistry.register
class WordRevealAnimation(BaseAnimation):
    """
    Karaoke-style word-by-word reveal animation using ASS \\k tags.

    Words appear progressively throughout the event duration.

    Parameters:
        mode: Timing distribution mode - "even" or "weighted" (default: "even")
        lead_in_ms: Delay before first word appears (default: 0)
        min_word_ms: Minimum time per word (default: 60)
        max_word_ms: Maximum time per word (default: 400)
        unrevealed_color: Color for unrevealed text in #RRGGBB format (default: None, uses primary color)

    Note: Words immediately followed by punctuation (e.g., "Hello," or "world!") are
    revealed together as a single unit for more natural appearance.

    Example preset:
        {
            "animation": {
                "type": "word_reveal",
                "mode": "even",
                "lead_in_ms": 0,
                "min_word_ms": 60,
                "max_word_ms": 400,
                "unrevealed_color": "#808080"
            }
        }
    """

    animation_type = "word_reveal"

    def validate_params(self) -> None:
        """Word reveal uses all default parameters, so validation always passes."""
        pass

    def generate_ass_override(self, event_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Word reveal doesn't use simple overrides.

        The entire text is transformed into karaoke segments.
        """
        return ""

    def apply_to_event(self, event: pysubs2.SSAEvent, **kwargs) -> None:
        """
        Transform event text into karaoke segments with \\k tags.

        The text is tokenized into words and punctuation, then timing is allocated
        to each token based on the selected mode.
        """
        duration_ms = int(event.end) - int(event.start)
        event.text = self._build_karaoke_text(event.text, duration_ms)

    def _build_karaoke_text(self, plain_text: str, event_duration_ms: int) -> str:
        """
        Convert plain text into ASS karaoke segments using \\k tags.

        Args:
            plain_text: The subtitle text to convert
            event_duration_ms: Duration of the subtitle event in milliseconds

        Returns:
            ASS-formatted text with \\k tags for each word
        """
        tokens = self._tokenize_with_newlines(plain_text)
        if not tokens:
            return plain_text

        # Extract parameters
        lead_in_ms = int(self.params.get("lead_in_ms", 0))
        min_word_ms = int(self.params.get("min_word_ms", 60))
        max_word_ms = int(self.params.get("max_word_ms", 400))
        mode = str(self.params.get("mode", "even")).strip().lower()

        available_ms = max(0, event_duration_ms - lead_in_ms)
        if available_ms <= 0:
            return plain_text

        # Identify word vs punctuation tokens
        is_word = [self._is_word_token(t) for t in tokens]
        word_indices = [i for i, w in enumerate(is_word) if w]

        if not word_indices:
            return plain_text

        # Allocate timing to each token
        token_ms = self._allocate_timing(
            tokens, word_indices, available_ms, mode,
            min_word_ms, max_word_ms
        )

        # Build output with \\k tags
        return self._build_output(tokens, token_ms, lead_in_ms)

    def _tokenize_with_newlines(self, text: str) -> List[str]:
        r"""
        Tokenize text preserving newlines.

        Handles both real newlines (\n) and ASS escape sequences (\N).

        Returns:
            List of tokens where "\n" represents a line break
        """
        # Split on both real newlines and ASS \N escape sequences
        # Replace \N with actual newline first for consistent processing
        text = text.replace(r"\N", "\n")
        lines = text.split("\n")
        tokens: List[str] = []

        for i, line in enumerate(lines):
            tokens.extend(self._tokenize_words(line))
            if i != len(lines) - 1:
                tokens.append("\n")

        return tokens

    @staticmethod
    def _tokenize_words(text: str) -> List[str]:
        """
        Tokenize into words with trailing punctuation grouped together.

        Words immediately followed by punctuation are kept as single tokens
        so they reveal together.

        Example: "Hello, world!" -> ["Hello,", "world!"]
        Example: "Wait... what?" -> ["Wait...", "what?"]
        """
        # Match: word + optional trailing punctuation, OR standalone punctuation
        return re.findall(r"\w+(?:'\w+)?[^\w\s]*|[^\w\s]+", text, flags=re.UNICODE)

    @staticmethod
    def _is_word_token(token: str) -> bool:
        """Check if token is a word (not newline or punctuation)."""
        return token != "\n" and bool(re.match(r"^\w", token, flags=re.UNICODE))

    def _allocate_timing(
        self,
        tokens: List[str],
        word_indices: List[int],
        available_ms: int,
        mode: str,
        min_word_ms: int,
        max_word_ms: int
    ) -> List[int]:
        """
        Allocate timing to each token.

        Args:
            tokens: List of all tokens
            word_indices: Indices of word tokens
            available_ms: Available time in milliseconds
            mode: "even" or "weighted"
            min_word_ms: Minimum time per word
            max_word_ms: Maximum time per word

        Returns:
            List of milliseconds for each token
        """
        token_ms = [0] * len(tokens)

        # Allocate time to words
        if mode == "even":
            # Evenly distribute across words
            base = available_ms / max(1, len(word_indices))
            for i in word_indices:
                token_ms[i] = int(round(base))

        elif mode == "weighted":
            # Weight by word length
            lengths = [len(tokens[i]) for i in word_indices]
            total = sum(lengths) or 1
            for idx, i in enumerate(word_indices):
                token_ms[i] = int(round(available_ms * (lengths[idx] / total)))

        else:
            raise ValueError(
                f"Unsupported word_reveal mode '{mode}' (use 'even' or 'weighted')"
            )

        # Clamp word times to min/max
        for i in word_indices:
            token_ms[i] = self._clamp(token_ms[i], min_word_ms, max_word_ms)

        # Handle standalone punctuation (not attached to words)
        # These get minimal time as they're just visual
        standalone_punct_indices = [
            i for i, t in enumerate(tokens)
            if t != "\n" and not self._is_word_token(t) and t.strip()
        ]
        for i in standalone_punct_indices:
            token_ms[i] = min(50, available_ms // max(1, len(tokens)))

        # Renormalize to match available_ms
        total_alloc = sum(token_ms)
        if total_alloc > 0:
            scale = available_ms / total_alloc
            token_ms = [int(round(t * scale)) for t in token_ms]

        return token_ms

    def _build_output(self, tokens: List[str], token_ms: List[int], lead_in_ms: int) -> str:
        """
        Build final ASS text with \\k tags.

        Args:
            tokens: List of word/punctuation tokens
            token_ms: Timing in milliseconds for each token
            lead_in_ms: Initial delay before first word

        Returns:
            ASS-formatted text with \\k tags
        """
        def ms_to_cs(ms: int) -> int:
            """Convert milliseconds to centiseconds."""
            return max(0, int(round(ms / 10.0)))

        out = ""

        # Apply unrevealed color if specified
        unrevealed_color = self.params.get("unrevealed_color")
        if unrevealed_color:
            # Convert #RRGGBB to ASS &HBBGGRR format
            if unrevealed_color.startswith("#") and len(unrevealed_color) == 7:
                r = unrevealed_color[1:3]
                g = unrevealed_color[3:5]
                b = unrevealed_color[5:7]
                ass_color = f"&H{b.upper()}{g.upper()}{r.upper()}"
                out += r"{\2c" + ass_color + r"}"

        # Optional lead-in
        if lead_in_ms > 0:
            out += r"{\k" + str(ms_to_cs(lead_in_ms)) + r"}"

        prev_token: Optional[str] = None

        for i, token in enumerate(tokens):
            if token == "\n":
                # Preserve newlines as ASS escape
                out += r"\N"
                prev_token = "\n"
                continue

            cs = ms_to_cs(token_ms[i])

            # Add spacing between tokens
            if prev_token is not None and prev_token != "\n":
                # No space if token starts with punctuation (standalone punctuation)
                if token and not token[0].isalnum() and token[0] not in ("'", '"', "'"):
                    pass
                # No space after opening quotes/parens
                elif prev_token and prev_token[-1] in ("'", '"', "'", "(", "[", "{"):
                    pass
                else:
                    out += " "

            out += r"{\k" + str(cs) + r"}" + token
            prev_token = token

        return out

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        """Default word reveal parameters."""
        return {
            "mode": "even",
            "lead_in_ms": 0,
            "min_word_ms": 60,
            "max_word_ms": 400,
            "unrevealed_color": None
        }
