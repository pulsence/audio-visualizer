"""
Animation plugin system with lazy loading.

To create a new animation:
1. Create a new file in this directory (e.g., myAnimation.py)
2. Subclass BaseAnimation
3. Decorate with @AnimationRegistry.register
4. Define animation_type class variable
5. Implement required methods (validate_params, generate_ass_override, apply_to_event)

The animation will be automatically discovered and available.

Example:
    from audio_visualizer.caption.animations import AnimationRegistry

    # List available animations
    print(AnimationRegistry.list_types())

    # Create an animation
    fade = AnimationRegistry.create("fade", {"in_ms": 120, "out_ms": 120})

    # Apply to an event
    fade.apply_to_event(subtitle_event)
"""

from .baseAnimation import BaseAnimation
from .registry import AnimationRegistry

# Track whether animations have been loaded
_loaded = False


def _ensure_animations_loaded() -> None:
    """Load all animation modules on first use."""
    global _loaded
    if _loaded:
        return

    # Import animation modules to trigger @register decorators
    from . import (
        blurAnimation,
        fadeAnimation,
        scaleAnimation,
        slideAnimation,
        wordRevealAnimation,
        pulseAnimation,
        beatPopAnimation,
        emphasisGlowAnimation,
    )

    _loaded = True


# Patch AnimationRegistry methods to ensure animations are loaded
_original_get = AnimationRegistry.get.__func__
_original_list_types = AnimationRegistry.list_types.__func__
_original_list = AnimationRegistry.list.__func__
_original_create = AnimationRegistry.create.__func__
_original_get_info = AnimationRegistry.get_info.__func__
_original_get_defaults = AnimationRegistry.get_defaults.__func__


@classmethod
def _lazy_get(cls, animation_type: str):
    _ensure_animations_loaded()
    return _original_get(cls, animation_type)


@classmethod
def _lazy_list_types(cls):
    _ensure_animations_loaded()
    return _original_list_types(cls)


@classmethod
def _lazy_list(cls):
    _ensure_animations_loaded()
    return _original_list(cls)


@classmethod
def _lazy_create(cls, animation_type: str, params=None):
    _ensure_animations_loaded()
    return _original_create(cls, animation_type, params)


@classmethod
def _lazy_get_info(cls):
    _ensure_animations_loaded()
    return _original_get_info(cls)


@classmethod
def _lazy_get_defaults(cls, animation_type: str):
    _ensure_animations_loaded()
    return _original_get_defaults(cls, animation_type)


AnimationRegistry.get = _lazy_get
AnimationRegistry.list_types = _lazy_list_types
AnimationRegistry.list = _lazy_list
AnimationRegistry.create = _lazy_create
AnimationRegistry.get_info = _lazy_get_info
AnimationRegistry.get_defaults = _lazy_get_defaults


# Map class names to their module names for lazy loading
_CLASS_TO_MODULE = {
    "FadeAnimation": "fadeAnimation",
    "SlideUpAnimation": "slideAnimation",
    "ScaleSettleAnimation": "scaleAnimation",
    "BlurSettleAnimation": "blurAnimation",
    "WordRevealAnimation": "wordRevealAnimation",
    "PulseAnimation": "pulseAnimation",
    "BeatPopAnimation": "beatPopAnimation",
    "EmphasisGlowAnimation": "emphasisGlowAnimation",
}


def __getattr__(name: str):
    """Lazy loading of animation classes."""
    if name in _CLASS_TO_MODULE:
        _ensure_animations_loaded()
        import importlib

        module = importlib.import_module(f".{_CLASS_TO_MODULE[name]}", __name__)
        return getattr(module, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Export public API
__all__ = [
    "BaseAnimation",
    "AnimationRegistry",
    "FadeAnimation",
    "SlideUpAnimation",
    "ScaleSettleAnimation",
    "BlurSettleAnimation",
    "WordRevealAnimation",
    "PulseAnimation",
    "BeatPopAnimation",
    "EmphasisGlowAnimation",
]


def list_animations():
    """Convenience function to list all registered animations."""
    return AnimationRegistry.list_types()


def get_animation_info():
    """Get information about all registered animations."""
    return AnimationRegistry.get_info()
