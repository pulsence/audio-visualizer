"""
Animation plugin registry.

This module provides a centralized registry for animation plugins using
decorator-based registration.
"""

from typing import Dict, Type, List, Any

from .base import BaseAnimation


class AnimationRegistry:
    """
    Central registry for animation plugins.

    This class maintains a registry of all available animation types and
    provides factory methods for creating animation instances.

    Example:
        # Register an animation
        @AnimationRegistry.register
        class FadeAnimation(BaseAnimation):
            animation_type = "fade"
            ...

        # Create an instance
        fade = AnimationRegistry.create("fade", {"in_ms": 120, "out_ms": 120})
    """

    _animations: Dict[str, Type[BaseAnimation]] = {}

    @classmethod
    def register(cls, animation_class: Type[BaseAnimation]) -> Type[BaseAnimation]:
        """
        Register an animation class with the registry.

        This is typically used as a decorator:

            @AnimationRegistry.register
            class MyAnimation(BaseAnimation):
                animation_type = "my_type"
                ...

        Args:
            animation_class: The animation class to register

        Returns:
            The same animation class (for use as decorator)

        Raises:
            ValueError: If animation_type is not defined or already registered
        """
        if not animation_class.animation_type:
            raise ValueError(
                f"{animation_class.__name__} must define 'animation_type' class variable"
            )

        atype = animation_class.animation_type

        if atype in cls._animations:
            existing = cls._animations[atype]
            raise ValueError(
                f"Animation type '{atype}' is already registered "
                f"by {existing.__name__}"
            )

        cls._animations[atype] = animation_class
        return animation_class

    @classmethod
    def get(cls, animation_type: str) -> Type[BaseAnimation]:
        """
        Get an animation class by its type name.

        Args:
            animation_type: The animation type (e.g., "fade", "slide_up")

        Returns:
            The animation class

        Raises:
            ValueError: If the animation type is not registered
        """
        if animation_type not in cls._animations:
            available = ', '.join(sorted(cls.list_types()))
            raise ValueError(
                f"Unknown animation type: '{animation_type}'. "
                f"Available animations: {available}"
            )
        return cls._animations[animation_type]

    @classmethod
    def create(cls, animation_type: str, params: Dict[str, Any]) -> BaseAnimation:
        """
        Factory method to create an animation instance.

        Args:
            animation_type: The type of animation to create
            params: Parameters to pass to the animation constructor

        Returns:
            An instance of the requested animation

        Raises:
            ValueError: If the animation type is not registered or parameters are invalid
        """
        animation_class = cls.get(animation_type)
        return animation_class(params)

    @classmethod
    def list_types(cls) -> List[str]:
        """
        List all registered animation types.

        Returns:
            Sorted list of animation type names
        """
        return sorted(cls._animations.keys())

    @classmethod
    def get_info(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get metadata about all registered animations.

        Returns:
            Dictionary mapping animation types to their metadata:
            {
                "fade": {
                    "class": "FadeAnimation",
                    "default_params": {"in_ms": 120, "out_ms": 120},
                    "doc": "Simple fade animation..."
                },
                ...
            }
        """
        return {
            atype: {
                "class": aclass.__name__,
                "default_params": aclass.get_default_params(),
                "doc": (aclass.__doc__ or "").strip()
            }
            for atype, aclass in cls._animations.items()
        }

    @classmethod
    def list(cls) -> List[str]:
        """
        List all registered animation types (alias for list_types).

        Returns:
            Sorted list of animation type names
        """
        return cls.list_types()

    @classmethod
    def get_defaults(cls, animation_type: str) -> Dict[str, Any]:
        """
        Get default parameters for a specific animation type.

        Args:
            animation_type: The animation type (e.g., "fade", "slide_up")

        Returns:
            Dictionary of default parameter names and values

        Raises:
            ValueError: If the animation type is not registered
        """
        animation_class = cls.get(animation_type)
        return animation_class.get_default_params()

    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered animations.

        This is primarily useful for testing.
        """
        cls._animations.clear()
