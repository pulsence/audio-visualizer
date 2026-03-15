"""
Interactive mode for tweaking presets and re-rendering.
"""

import json
import sys
from pathlib import Path
from typing import Any

from ..core.config import PresetConfig
from ..presets.loader import PresetLoader
from ..animations.registry import AnimationRegistry
from .main import render_subtitle_cli


def interactive_mode(args, input_path: Path, output_path: Path) -> int:
    """
    Interactive REPL for tweaking preset settings and re-rendering.

    Args:
        args: Parsed command-line arguments
        input_path: Input subtitle file
        output_path: Output video file

    Returns:
        Exit code
    """
    print("\nInteractive mode. Type 'help' for commands.\n", file=sys.stderr)

    # Load initial preset and track the file path if it's a file
    loader = PresetLoader()
    preset = loader.load(args.preset)
    baseline_preset = PresetConfig.from_dict(preset.to_dict())  # Keep original

    # Try to determine if preset is from a file
    preset_file_path = None
    if args.preset and (Path(args.preset).exists() or ":" in args.preset):
        # It's a file path or multi-preset reference
        if ":" in args.preset:
            preset_file_path = Path(args.preset.split(":")[0])
        else:
            preset_file_path = Path(args.preset)

    def print_preset_summary():
        """Print current preset configuration."""
        print("Current preset/settings:", file=sys.stderr)
        if preset_file_path:
            print(f"  preset       : {preset_file_path}", file=sys.stderr)
        else:
            print(f"  preset       : {args.preset} (built-in)", file=sys.stderr)
        print(f"  input        : {input_path}", file=sys.stderr)
        print(f"  out          : {output_path}", file=sys.stderr)
        print(f"  fps          : {args.fps}", file=sys.stderr)
        print(f"  quality      : {args.quality}", file=sys.stderr)
        print(f"  safety_scale : {args.safety_scale}", file=sys.stderr)
        print(f"  font         : {preset.font_name} size={preset.font_size} bold={preset.bold}", file=sys.stderr)
        print(f"  colors       : primary={preset.primary_color} outline={preset.outline_color}", file=sys.stderr)
        print(f"  outline/shadow: outline_px={preset.outline_px} shadow_px={preset.shadow_px}", file=sys.stderr)
        print(f"  wrap         : max_width_px={preset.max_width_px} line_spacing={preset.line_spacing}", file=sys.stderr)
        if preset.animation:
            print(f"  animation    : type={preset.animation.type} params={preset.animation.params}", file=sys.stderr)

    def do_render():
        """Perform rendering with current settings."""
        try:
            # Save the preset temporarily and use the preset name
            # We need to pass the preset data, not just a name
            # For interactive mode, we use the raw orchestration
            from ..api import RenderConfig
            from ..core.events import EventEmitter, EventType, RenderEvent
            from ..core.sizing import SizeCalculator
            from ..core.style import StyleBuilder
            from ..core.subtitle import SubtitleFile
            from ..rendering.ffmpeg import FFmpegRenderer
            from ..rendering.progress import ProgressTracker
            import tempfile

            ext = input_path.suffix.lower().lstrip(".")

            # Determine if we should apply animation
            apply_animation = args.apply_animation
            if args.no_animation:
                apply_animation = False
            elif ext == "srt" and not args.apply_animation and not args.no_animation:
                apply_animation = True

            # Setup event emitter
            emitter = EventEmitter()

            def stderr_handler(event: RenderEvent) -> None:
                if args.quiet:
                    return
                if event.event_type == EventType.STEP:
                    print(f"[{event.elapsed_seconds:6.1f}s] {event.message}", file=sys.stderr)
                elif event.event_type == EventType.DEBUG:
                    print(event.message, file=sys.stderr)
                elif event.event_type == EventType.RENDER_PROGRESS:
                    msg = "FFmpeg"
                    if event.frame:
                        msg += f" frame={event.frame}"
                    if event.time:
                        msg += f" time={event.time}"
                    if event.speed:
                        msg += f" speed={event.speed}"
                    print(msg, file=sys.stderr)

            emitter.subscribe(stderr_handler)
            progress = ProgressTracker(emitter)

            progress.step(f"Input: {input_path.name}")
            progress.step(f"Output: {output_path.name}")

            # Load subtitle
            progress.step("Loading subtitles...")
            subtitle = SubtitleFile.load(input_path)
            progress.step(f"Loaded {len(subtitle.subs.events)} subtitle events")

            with tempfile.TemporaryDirectory(prefix="caption_animator_") as temp_dir:
                temp_path = Path(temp_dir)
                ass_path = temp_path / "work.ass"

                # Build and apply style
                progress.step("Building ASS style from preset...")
                style_builder = StyleBuilder(preset)
                style = style_builder.build("Default")

                if ext == "srt" or args.reskin:
                    subtitle.apply_style(style, preset, wrap_text=True)

                # Apply animation
                if apply_animation and preset.animation:
                    progress.step(f"Applying animation: {preset.animation.type}")
                    animation = AnimationRegistry.create(
                        preset.animation.type, preset.animation.params
                    )
                    subtitle.apply_animation(animation)

                # Calculate size
                progress.step("Computing overlay size...")
                size_calc = SizeCalculator(preset, safety_scale=args.safety_scale)
                size = size_calc.compute_size(subtitle.subs)
                progress.step(f"Computed overlay size: {size.width}x{size.height}")

                # Apply positioning
                position = size_calc.compute_anchor_position(size)
                subtitle.apply_center_positioning(position, size)
                subtitle.set_play_resolution(size)

                # Save ASS
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
                progress.step(f"Subtitle duration: {end_ms}ms (~{duration_sec:.2f}s)")

                # Render
                progress.step("Rendering overlay video via FFmpeg...")
                renderer = FFmpegRenderer(
                    emitter=emitter,
                    loglevel=args.loglevel,
                    show_progress=True,
                    quality=args.quality,
                )

                output_path.parent.mkdir(parents=True, exist_ok=True)

                renderer.render(
                    ass_path=ass_path,
                    output_path=output_path,
                    size=size,
                    fps=args.fps,
                    duration_sec=duration_sec,
                )

                progress.step("FFmpeg render complete")

            print(f"Overlay rendered: {output_path}", file=sys.stderr)
            print(f"Overlay size: {size.width}x{size.height} @ {args.fps} fps", file=sys.stderr)

        except Exception as e:
            print(f"Render failed: {e}", file=sys.stderr)

    def set_value(key: str, value_str: str):
        """Set a preset value by dotted key path."""
        # Parse value
        value: Any = value_str.strip()

        # Try to parse as JSON for complex types
        if value.lower() in ("true", "false"):
            value = value.lower() == "true"
        elif value.lower() in ("none", "null"):
            value = None
        else:
            try:
                value = int(value)
            except ValueError:
                try:
                    value = float(value)
                except ValueError:
                    # Try JSON parsing for lists/dicts
                    if value.startswith(("[", "{")):
                        try:
                            value = json.loads(value)
                        except:
                            pass  # Keep as string

        # Set the value
        parts = key.split(".")
        if len(parts) == 1:
            # Special case: changing animation type with just "animation <type>"
            if key == "animation":
                from ..core.config import AnimationConfig
                # Verify animation type exists
                if value not in AnimationRegistry.list():
                    available = ', '.join(AnimationRegistry.list())
                    print(f"Unknown animation type: {value}. Available: {available}", file=sys.stderr)
                else:
                    # Get default params for new animation type
                    defaults = AnimationRegistry.get_defaults(value)
                    preset.animation = AnimationConfig(type=value, params=defaults)
                    print(f"Animation changed to: {value} (with default params: {defaults})", file=sys.stderr)
            # Top-level attribute
            elif hasattr(preset, key):
                setattr(preset, key, value)
                print(f"{key} = {getattr(preset, key)}", file=sys.stderr)
            else:
                print(f"Unknown key: {key}", file=sys.stderr)
        elif parts[0] == "animation" and len(parts) == 2:
            # Animation parameter (e.g., animation.mode, animation.lead_in_ms)
            if preset.animation:
                preset.animation.params[parts[1]] = value
                print(f"animation.{parts[1]} = {value}", file=sys.stderr)
            else:
                print("No animation configured", file=sys.stderr)
        else:
            print(f"Unsupported nested key: {key}", file=sys.stderr)

    # Main loop
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.", file=sys.stderr)
            return 0

        if not line:
            continue

        parts = line.split(None, 1)
        cmd = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        if cmd in ("q", "quit", "exit"):
            return 0

        elif cmd in ("h", "help", "?"):
            print(
                "Commands:\n"
                "  r | render                 Render with current settings\n"
                "  p | print                  Print preset/settings summary\n"
                "  set <key> <value>          Set preset value (e.g., set font_size 72)\n"
                "  get <key>                  Show current value of a key\n"
                "  keys                       List all available preset keys\n"
                "  animations                 List available animations and their parameters\n"
                "  load <path>                Load different SRT/ASS file\n"
                "  out <path>                 Change output path\n"
                "  fps <value>                Change FPS\n"
                "  quality <small|medium|large> Change output quality\n"
                "  scale <value>              Change safety_scale\n"
                "  save [path.json]           Save preset (defaults to loaded preset file if available)\n"
                "  reset                      Reset preset to initial state\n"
                "  quit                       Exit\n",
                file=sys.stderr
            )

        elif cmd in ("r", "render"):
            do_render()

        elif cmd in ("p", "print"):
            print_preset_summary()

        elif cmd == "reset":
            preset = PresetConfig.from_dict(baseline_preset.to_dict())
            print("Preset reset to initial state.", file=sys.stderr)

        elif cmd == "get":
            if not rest:
                print("Usage: get <key>", file=sys.stderr)
                continue
            key = rest.strip()
            parts = key.split(".")
            if len(parts) == 1:
                # Top-level attribute
                if hasattr(preset, key):
                    value = getattr(preset, key)
                    print(f"{key} = {value}", file=sys.stderr)
                else:
                    print(f"Unknown key: {key}", file=sys.stderr)
            elif parts[0] == "animation" and len(parts) == 2:
                # Animation parameter
                if preset.animation:
                    param_name = parts[1]
                    if param_name in preset.animation.params:
                        value = preset.animation.params[param_name]
                        print(f"animation.{param_name} = {value}", file=sys.stderr)
                    else:
                        print(f"Animation parameter not set: {param_name}", file=sys.stderr)
                else:
                    print("No animation configured", file=sys.stderr)
            else:
                print(f"Unsupported nested key: {key}", file=sys.stderr)

        elif cmd == "keys":
            print("Available preset keys:", file=sys.stderr)
            print("  Top-level: font_file, font_name, font_size, bold, italic,", file=sys.stderr)
            print("             primary_color, outline_color, shadow_color,", file=sys.stderr)
            print("             outline_px, shadow_px, blur_px,", file=sys.stderr)
            print("             line_spacing, max_width_px, padding, alignment,", file=sys.stderr)
            print("             margin_l, margin_r, margin_v, wrap_style", file=sys.stderr)
            if preset.animation:
                print(f"\n  Animation ({preset.animation.type}):", file=sys.stderr)
                defaults = AnimationRegistry.get_defaults(preset.animation.type)
                param_names = ', '.join(defaults.keys())
                print(f"    {param_names}", file=sys.stderr)
                print("\n  Set animation params with: set animation.<param> <value>", file=sys.stderr)
            else:
                print("\n  No animation configured", file=sys.stderr)

        elif cmd == "animations":
            print("Available animations:", file=sys.stderr)
            for anim_type in AnimationRegistry.list():
                defaults = AnimationRegistry.get_defaults(anim_type)
                params = ', '.join(f"{k}={v}" for k, v in defaults.items())
                print(f"  {anim_type}: {params}", file=sys.stderr)
            print("\nTo change animation type, use: set animation <name>", file=sys.stderr)

        elif cmd == "load":
            if not rest:
                print("Usage: load <path.srt|path.ass>", file=sys.stderr)
                continue
            new_input = Path(rest.strip())
            if not new_input.exists():
                print(f"File not found: {new_input}", file=sys.stderr)
                continue
            if new_input.suffix.lower() not in ('.srt', '.ass'):
                print("Only .srt and .ass files are supported", file=sys.stderr)
                continue
            input_path = new_input
            print(f"Loaded: {input_path}", file=sys.stderr)

        elif cmd == "save":
            # Default to current preset file if no path provided
            if not rest:
                if preset_file_path:
                    save_path = preset_file_path
                else:
                    print("Usage: save <path.json>", file=sys.stderr)
                    print("  (No default available - preset was loaded from built-in)", file=sys.stderr)
                    continue
            else:
                # Strip quotes if present (handles both single and double quotes)
                path_str = rest.strip()
                if (path_str.startswith('"') and path_str.endswith('"')) or \
                   (path_str.startswith("'") and path_str.endswith("'")):
                    path_str = path_str[1:-1]
                save_path = Path(path_str)

            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_text(preset.to_json(), encoding="utf-8")
            print(f"Saved preset: {save_path}", file=sys.stderr)

        elif cmd == "out":
            if not rest:
                print("Usage: out <path.mov>", file=sys.stderr)
                continue
            output_path = Path(rest.strip())
            output_path.parent.mkdir(parents=True, exist_ok=True)
            print(f"Output set: {output_path}", file=sys.stderr)

        elif cmd == "fps":
            if not rest:
                print("Usage: fps <value>", file=sys.stderr)
                continue
            args.fps = rest.strip()
            print(f"FPS set: {args.fps}", file=sys.stderr)

        elif cmd == "quality":
            if not rest:
                print("Usage: quality <small|medium|large>", file=sys.stderr)
                continue
            quality = rest.strip().lower()
            if quality not in ["small", "medium", "large"]:
                print(f"Invalid quality: {quality}. Choose from: small, medium, large", file=sys.stderr)
                continue
            args.quality = quality
            quality_info = {
                "small": "H.264 (~5-10MB/min)",
                "medium": "ProRes 422 HQ (~220Mbps, no alpha)",
                "large": "ProRes 4444 (~330Mbps, with alpha)"
            }
            print(f"Quality set: {quality} ({quality_info[quality]})", file=sys.stderr)

        elif cmd == "scale":
            if not rest:
                print("Usage: scale <value>", file=sys.stderr)
                continue
            args.safety_scale = float(rest.strip())
            print(f"safety_scale set: {args.safety_scale}", file=sys.stderr)

        elif cmd == "set":
            if not rest or " " not in rest:
                print("Usage: set <key> <value>", file=sys.stderr)
                continue
            key, value = rest.split(None, 1)
            set_value(key, value)

        else:
            print(f"Unknown command: {cmd}. Type 'help' for commands.", file=sys.stderr)
