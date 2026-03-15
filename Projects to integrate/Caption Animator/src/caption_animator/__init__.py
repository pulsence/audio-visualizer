"""
Caption Animator - Subtitle overlay rendering with animated effects.

A modern Python package for rendering stylized subtitle overlays as transparent
video files for use in video editing software like DaVinci Resolve.

Main features:
- Plugin-based animation system
- Type-safe preset configuration
- Multiple animation types (fade, slide, scale, blur, word-reveal)
- SRT and ASS format support
- Transparent ProRes 4444 video output

Example (Library API):
    from caption_animator import render_subtitle, RenderConfig

    result = render_subtitle(
        "input.srt",
        "output.mov",
        config=RenderConfig(preset="modern_box", quality="large"),
        on_progress=print
    )

    if result.success:
        print(f"Rendered: {result.output_path}")

Example (Low-level API):
    from caption_animator import SubtitleFile, PresetLoader, AnimationRegistry
    from caption_animator import SizeCalculator, FFmpegRenderer
    from caption_animator.core.events import EventEmitter

    # Load subtitle and preset
    sub = SubtitleFile.load("input.srt")
    preset = PresetLoader().load("modern_box")

    # Apply animation
    animation = AnimationRegistry.create("fade", preset.animation.params)
    sub.apply_animation(animation)

    # Render
    emitter = EventEmitter()
    size = SizeCalculator(preset).compute_size(sub.subs)
    renderer = FFmpegRenderer(emitter)
    renderer.render(ass_path, output_path, size, fps="30", duration_sec=120)
"""

__version__ = "0.2.1"
__author__ = "Timothy Eck"
__license__ = "MIT"


def __getattr__(name: str):
    """Lazy loading of submodule exports."""
    # Core config
    if name in ("PresetConfig", "AnimationConfig"):
        from .core.config import AnimationConfig, PresetConfig

        return PresetConfig if name == "PresetConfig" else AnimationConfig

    if name == "SubtitleFile":
        from .core.subtitle import SubtitleFile

        return SubtitleFile

    if name in ("OverlaySize", "SizeCalculator"):
        from .core.sizing import OverlaySize, SizeCalculator

        return OverlaySize if name == "OverlaySize" else SizeCalculator

    if name == "StyleBuilder":
        from .core.style import StyleBuilder

        return StyleBuilder

    # Event system
    if name in ("EventEmitter", "EventType", "RenderEvent"):
        from .core.events import EventEmitter, EventType, RenderEvent

        return {"EventEmitter": EventEmitter, "EventType": EventType, "RenderEvent": RenderEvent}[name]

    # Animation system
    if name in (
        "BaseAnimation",
        "AnimationRegistry",
        "FadeAnimation",
        "SlideUpAnimation",
        "ScaleSettleAnimation",
        "BlurSettleAnimation",
        "WordRevealAnimation",
    ):
        from . import animations

        return getattr(animations, name)

    # Preset system
    if name == "PresetLoader":
        from .presets.loader import PresetLoader

        return PresetLoader

    if name in ("get_builtin_preset", "list_builtin_presets"):
        from .presets import defaults

        return getattr(defaults, name)

    # Rendering
    if name == "FFmpegRenderer":
        from .rendering.ffmpeg import FFmpegRenderer

        return FFmpegRenderer

    if name == "ProgressTracker":
        from .rendering.progress import ProgressTracker

        return ProgressTracker

    # High-level API
    if name in ("render_subtitle", "RenderConfig", "RenderResult", "list_presets", "list_animations"):
        from . import api

        return getattr(api, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__license__",
    # High-level API
    "render_subtitle",
    "RenderConfig",
    "RenderResult",
    "list_presets",
    "list_animations",
    # Core
    "PresetConfig",
    "AnimationConfig",
    "SubtitleFile",
    "OverlaySize",
    "SizeCalculator",
    "StyleBuilder",
    # Events
    "EventEmitter",
    "EventType",
    "RenderEvent",
    # Animations
    "BaseAnimation",
    "AnimationRegistry",
    "FadeAnimation",
    "SlideUpAnimation",
    "ScaleSettleAnimation",
    "BlurSettleAnimation",
    "WordRevealAnimation",
    # Presets
    "PresetLoader",
    "get_builtin_preset",
    "list_builtin_presets",
    # Rendering
    "FFmpegRenderer",
    "ProgressTracker",
]
