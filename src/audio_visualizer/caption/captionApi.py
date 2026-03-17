"""
Public API for Caption Animator library usage.

This module provides the recommended high-level API for programmatic use.
Import from here for stable, documented interfaces.

Example:
    from audio_visualizer.caption.captionApi import render_subtitle, RenderConfig

    result = render_subtitle(
        input_path="input.srt",
        output_path="output.mov",
        config=RenderConfig(preset="modern_box", quality="large"),
        on_progress=lambda msg: print(msg)
    )

    if result.success:
        print(f"Rendered to {result.output_path}")
        print(f"Size: {result.width}x{result.height}")
"""

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Union

from audio_visualizer.events import AppEvent, AppEventEmitter, EventLevel, EventType

from .animations import AnimationRegistry
from .core.sizing import SizeCalculator
from .core.style import StyleBuilder
from .core.subtitle import SubtitleFile
from .presets.loader import PresetLoader
from .rendering.ffmpegRenderer import FFmpegRenderer
from .rendering.progressTracker import ProgressTracker


@dataclass
class RenderConfig:
    """Configuration for rendering operations."""

    preset: str = "modern_box"
    fps: str = "30"
    quality: str = "small"  # small, medium, large
    safety_scale: float = 1.12
    apply_animation: bool = True
    reskin: bool = False  # For ASS files: apply preset style
    max_duration_sec: float = 0.0  # 0 = no limit; >0 clamps render duration


@dataclass
class RenderResult:
    """Result of a render operation."""

    success: bool
    output_path: Optional[Path] = None
    width: int = 0
    height: int = 0
    duration_ms: int = 0
    error: Optional[str] = None


def render_subtitle(
    input_path: Union[str, Path],
    output_path: Union[str, Path],
    config: Optional[RenderConfig] = None,
    on_progress: Optional[Callable[[str], None]] = None,
    on_event: Optional[Callable[[AppEvent], None]] = None,
    emitter: Optional[AppEventEmitter] = None,
    preset_override: Optional["PresetConfig"] = None,
) -> RenderResult:
    """
    Render a subtitle file to transparent video overlay.

    This is the main entry point for library usage. It handles:
    - Loading and parsing subtitle files (SRT/ASS)
    - Applying preset styling
    - Computing optimal overlay size
    - Applying animations
    - Rendering via FFmpeg

    Args:
        input_path: Path to input subtitle file (.srt or .ass)
        output_path: Path for output video file (.mov recommended)
        config: Render configuration (uses defaults if None)
        on_progress: Simple callback for progress messages
        on_event: Full event callback for detailed progress
        emitter: Optional shared AppEventEmitter used for host-level integration

    Returns:
        RenderResult with success status and output details

    Example:
        result = render_subtitle(
            "input.srt",
            "output.mov",
            config=RenderConfig(preset="modern_box", quality="large"),
            on_progress=lambda msg: print(f"Progress: {msg}")
        )

        if result.success:
            print(f"Rendered: {result.output_path}")
            print(f"Size: {result.width}x{result.height}")
    """
    config = config or RenderConfig()
    input_path = Path(input_path)
    output_path = Path(output_path)

    # Setup event emitter
    event_emitter = emitter or AppEventEmitter()

    if on_event:
        event_emitter.subscribe(on_event)

    if on_progress:

        def progress_adapter(event: AppEvent) -> None:
            if event.event_type == EventType.STAGE:
                on_progress(event.message)

        event_emitter.subscribe(progress_adapter)

    try:
        # Validate input
        ext = input_path.suffix.lower().lstrip(".")
        if ext not in ("srt", "ass"):
            return RenderResult(
                success=False, error=f"Unsupported format: {ext}. Use .srt or .ass"
            )

        if not input_path.exists():
            return RenderResult(success=False, error=f"Input file not found: {input_path}")

        # Load preset (use override if provided)
        if preset_override is not None:
            preset = preset_override
        else:
            loader = PresetLoader()
            preset = loader.load(config.preset)

        # Setup progress tracker
        progress = ProgressTracker(event_emitter)

        progress.step(f"Loading: {input_path.name}")

        # Load subtitle
        subtitle = SubtitleFile.load(input_path)
        progress.step(f"Loaded {len(subtitle.subs.events)} subtitle events")

        # Determine if we should apply animation
        apply_animation = config.apply_animation

        with tempfile.TemporaryDirectory(prefix="audio_visualizer_caption_") as temp_dir:
            temp_path = Path(temp_dir)
            ass_path = temp_path / "work.ass"

            # Build and apply style
            progress.step("Building ASS style from preset...")
            style_builder = StyleBuilder(preset)
            style = style_builder.build("Default")

            # Apply style for SRT or when reskinning
            if ext == "srt" or config.reskin:
                subtitle.apply_style(style, preset, wrap_text=True)

            # Apply animation if requested
            if apply_animation and preset.animation:
                progress.step(f"Applying animation: {preset.animation.type}")
                animation = AnimationRegistry.create(
                    preset.animation.type, preset.animation.params
                )
                subtitle.apply_animation(animation)

            # Calculate size
            progress.step("Computing overlay size...")
            size_calc = SizeCalculator(preset, safety_scale=config.safety_scale)
            size = size_calc.compute_size(subtitle.subs)
            progress.step(f"Computed overlay size: {size.width}x{size.height}")

            # Apply positioning
            position = size_calc.compute_anchor_position(size)
            subtitle.apply_center_positioning(position, size)
            subtitle.set_play_resolution(size)

            # Save working ASS
            subtitle.save(ass_path)

            # Handle placeholder substitution
            if apply_animation and preset.animation and preset.animation.type == "slide_up":
                animation = AnimationRegistry.create(
                    preset.animation.type, preset.animation.params
                )
                if animation.supports_placeholder_substitution():
                    content = ass_path.read_text(encoding="utf-8")
                    content = animation.substitute_placeholders(content, position)
                    ass_path.write_text(content, encoding="utf-8")

            # Calculate duration
            end_ms = subtitle.get_duration_ms()
            duration_sec = (end_ms / 1000.0) + 0.25
            if config.max_duration_sec > 0:
                duration_sec = min(duration_sec, config.max_duration_sec)

            progress.step(f"Subtitle duration: {end_ms}ms (~{duration_sec:.2f}s)")

            # Render
            progress.step("Rendering overlay video via FFmpeg...")

            output_path.parent.mkdir(parents=True, exist_ok=True)

            renderer = FFmpegRenderer(
                emitter=event_emitter,
                loglevel="error",
                show_progress=True,
                quality=config.quality,
            )

            renderer.render(
                ass_path=ass_path,
                output_path=output_path,
                size=size,
                fps=config.fps,
                duration_sec=duration_sec,
            )

            progress.step("Render complete")

            return RenderResult(
                success=True,
                output_path=output_path,
                width=size.width,
                height=size.height,
                duration_ms=end_ms,
            )

    except Exception as e:
        event_emitter.emit(
            AppEvent(
                event_type=EventType.LOG,
                message=str(e),
                level=EventLevel.ERROR,
                data={
                    "input_path": str(input_path),
                    "output_path": str(output_path),
                },
            )
        )
        return RenderResult(success=False, error=str(e))


def list_presets() -> dict:
    """
    List all available presets.

    Returns:
        Dictionary mapping preset names to their types (built-in or file path)
    """
    from .presets.defaults import list_builtin_presets

    result = {}
    for name in list_builtin_presets():
        result[name] = "built-in"
    return result


def list_animations() -> dict:
    """
    List all available animations with their default parameters.

    Returns:
        Dictionary mapping animation types to their info
    """
    return AnimationRegistry.get_info()
