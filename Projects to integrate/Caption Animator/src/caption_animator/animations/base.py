"""
Base animation class and interfaces.

This module defines the abstract base class that all animations must inherit from.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple

import pysubs2


class BaseAnimation(ABC):
    """
    Abstract base class for all subtitle animations.

    To create a new animation:
    1. Subclass BaseAnimation
    2. Set the animation_type class variable
    3. Implement the abstract methods
    4. Decorate with @AnimationRegistry.register

    Example:
        @AnimationRegistry.register
        class MyAnimation(BaseAnimation):
            animation_type = "my_animation"

            def validate_params(self) -> None:
                if "required_param" not in self.params:
                    raise ValueError("missing required_param")

            def generate_ass_override(self, event_context=None) -> str:
                return r"\\my_tag"

            def apply_to_event(self, event, **kwargs) -> None:
                event.text = "{" + self.generate_ass_override() + "}" + event.text
    """

    # Subclasses must set this to register the animation type
    animation_type: str = ""

    def __init__(self, params: Dict[str, Any]):
        """
        Initialize animation with parameters from preset.

        Args:
            params: Animation-specific parameters (e.g., in_ms, out_ms, move_px)
        """
        self.params = params
        self.validate_params()

    @abstractmethod
    def validate_params(self) -> None:
        """
        Validate that all required parameters are present and valid.

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        pass

    @abstractmethod
    def generate_ass_override(self, event_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate ASS override tags for this animation.

        Args:
            event_context: Optional context about the event (e.g., duration_ms, position)

        Returns:
            ASS override string without surrounding braces (e.g., r"\\fad(120,120)")
        """
        pass

    @abstractmethod
    def apply_to_event(self, event: pysubs2.SSAEvent, **kwargs) -> None:
        """
        Apply this animation to a subtitle event by modifying its text.

        Args:
            event: The subtitle event to modify
            **kwargs: Additional context (size, position, etc.)
        """
        pass

    def needs_positioning(self) -> bool:
        """
        Whether this animation requires position calculation (e.g., for \\pos or \\move).

        Returns:
            True if position data is needed, False otherwise
        """
        return False

    def supports_placeholder_substitution(self) -> bool:
        """
        Whether this animation uses placeholder values that need substitution.

        Some animations (like slide_up) use placeholders like {X}, {Y} that
        must be replaced with actual coordinates after sizing is computed.

        Returns:
            True if placeholders are used, False otherwise
        """
        return False

    def substitute_placeholders(
        self,
        text: str,
        position: Tuple[int, int],
        **kwargs
    ) -> str:
        """
        Replace placeholders in generated ASS text with actual values.

        Args:
            text: The text containing placeholders
            position: The (x, y) position for the subtitle
            **kwargs: Additional context

        Returns:
            Text with placeholders replaced
        """
        return text

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        """
        Return default parameter values for this animation.

        Returns:
            Dictionary of default parameters
        """
        return {}

    @staticmethod
    def _clamp(val: int, min_val: int, max_val: int) -> int:
        """Clamp a value between min and max."""
        return max(min_val, min(max_val, val))

    @staticmethod
    def _inject_override(text: str, override: str) -> str:
        """
        Inject ASS override tags at the start of text.

        If text already starts with {...}, the override is inserted inside.
        Otherwise, a new {...} block is created at the start.

        Args:
            text: The original subtitle text
            override: The override string (without braces)

        Returns:
            Text with override injected
        """
        if not override:
            return text

        if text.startswith("{") and "}" in text:
            end = text.find("}")
            head = text[1:end]
            rest = text[end + 1:]
            return "{" + override + head + "}" + rest

        return "{" + override + "}" + text
