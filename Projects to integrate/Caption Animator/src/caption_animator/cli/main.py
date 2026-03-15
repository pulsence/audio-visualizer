"""
Main CLI entry point.
"""

import shutil
import sys
import tempfile
from pathlib import Path

from ..api import RenderConfig, render_subtitle
from ..core.events import EventEmitter, EventType, RenderEvent
from ..presets.loader import PresetLoader
from .args import parse_args
from .commands import list_presets_command


def create_stderr_handler(quiet: bool = False, hide_ffmpeg_progress: bool = False):
    """
    Create an event handler that prints to stderr.

    Args:
        quiet: If True, suppress most output
        hide_ffmpeg_progress: If True, suppress FFmpeg progress updates

    Returns:
        Event handler function
    """

    def handler(event: RenderEvent) -> None:
        if quiet:
            return

        if event.event_type == EventType.STEP:
            print(f"[{event.elapsed_seconds:6.1f}s] {event.message}", file=sys.stderr)
        elif event.event_type == EventType.DEBUG:
            print(event.message, file=sys.stderr)
        elif event.event_type == EventType.RENDER_PROGRESS and not hide_ffmpeg_progress:
            msg = "FFmpeg"
            if event.frame:
                msg += f" frame={event.frame}"
            if event.time:
                msg += f" time={event.time}"
            if event.speed:
                msg += f" speed={event.speed}"
            print(msg, file=sys.stderr)
        elif event.event_type in (EventType.WARNING, EventType.ERROR):
            print(event.message, file=sys.stderr)

    return handler


def render_subtitle_cli(
    input_path: Path,
    output_path: Path,
    preset_name: str,
    args,
) -> None:
    """
    Render subtitle file to video overlay (CLI wrapper).

    This function handles CLI-specific concerns like keeping ASS files,
    keeping temp directories, and printing final output messages.

    Args:
        input_path: Input subtitle file
        output_path: Output video file
        preset_name: Name of preset to use
        args: Parsed command-line arguments
    """
    # Determine source format
    ext = input_path.suffix.lower().lstrip(".")

    # Determine if we should apply animation
    apply_animation = args.apply_animation
    if args.no_animation:
        apply_animation = False
    elif ext == "srt" and not args.apply_animation and not args.no_animation:
        # Auto-apply for SRT
        apply_animation = True

    # Build config
    config = RenderConfig(
        preset=preset_name,
        fps=args.fps,
        quality=args.quality,
        safety_scale=args.safety_scale,
        apply_animation=apply_animation,
        reskin=args.reskin,
    )

    # Setup event emitter with stderr handler
    emitter = EventEmitter()
    emitter.subscribe(
        create_stderr_handler(
            quiet=args.quiet, hide_ffmpeg_progress=args.hide_ffmpeg_progress
        )
    )

    # For keep_ass and keep_temp, we need to handle the rendering ourselves
    # since the API doesn't expose temp files
    if args.keep_ass or args.keep_temp:
        _render_with_file_keeping(
            input_path=input_path,
            output_path=output_path,
            config=config,
            emitter=emitter,
            keep_ass=args.keep_ass,
            keep_temp=args.keep_temp,
            loglevel=args.loglevel,
        )
    else:
        # Use simple API
        def on_event(event: RenderEvent) -> None:
            handler = create_stderr_handler(
                quiet=args.quiet, hide_ffmpeg_progress=args.hide_ffmpeg_progress
            )
            handler(event)

        result = render_subtitle(
            input_path=input_path,
            output_path=output_path,
            config=config,
            on_event=on_event,
        )

        if not result.success:
            raise RuntimeError(result.error)

        print(f"Overlay rendered: {output_path}", file=sys.stderr)
        print(
            f"Overlay size: {result.width}x{result.height} @ {args.fps} fps",
            file=sys.stderr,
        )


def _render_with_file_keeping(
    input_path: Path,
    output_path: Path,
    config: RenderConfig,
    emitter: EventEmitter,
    keep_ass: bool,
    keep_temp: bool,
    loglevel: str,
) -> None:
    """
    Render with options to keep intermediate files.

    This is a CLI-specific feature that exposes temp file handling.
    """
    from ..animations import AnimationRegistry
    from ..core.sizing import SizeCalculator
    from ..core.style import StyleBuilder
    from ..core.subtitle import SubtitleFile
    from ..presets.loader import PresetLoader
    from ..rendering.ffmpeg import FFmpegRenderer
    from ..rendering.progress import ProgressTracker

    progress = ProgressTracker(emitter)

    ext = input_path.suffix.lower().lstrip(".")

    progress.step(f"Input: {input_path.name}")
    progress.step(f"Output: {output_path.name}")

    # Load subtitle
    progress.step(f"Loading subtitles...")
    subtitle = SubtitleFile.load(input_path)
    progress.step(f"Loaded {len(subtitle.subs.events)} subtitle events")

    # Load preset
    loader = PresetLoader()
    preset = loader.load(config.preset)

    with tempfile.TemporaryDirectory(prefix="caption_animator_") as temp_dir:
        temp_path = Path(temp_dir)
        ass_path = temp_path / "work.ass"

        # Build and apply style
        progress.step("Building ASS style from preset...")
        style_builder = StyleBuilder(preset)
        style = style_builder.build("Default")

        if ext == "srt" or config.reskin:
            subtitle.apply_style(style, preset, wrap_text=True)

        # Apply animation
        if config.apply_animation and preset.animation:
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

        # Save ASS
        subtitle.save(ass_path)

        # Handle placeholder substitution
        if (
            config.apply_animation
            and preset.animation
            and preset.animation.type == "slide_up"
        ):
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
            loglevel=loglevel,
            show_progress=True,
            quality=config.quality,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)

        renderer.render(
            ass_path=ass_path,
            output_path=output_path,
            size=size,
            fps=config.fps,
            duration_sec=duration_sec,
        )

        progress.step("FFmpeg render complete")

        # Save ASS if requested
        if keep_ass:
            ass_final = output_path.with_suffix(".ass")
            shutil.copy2(ass_path, ass_final)
            print(f"Saved ASS: {ass_final}", file=sys.stderr)

        # Keep temp directory if requested
        if keep_temp:
            debug_dir = output_path.parent / (output_path.stem + "_debug")
            if debug_dir.exists():
                shutil.rmtree(debug_dir)
            shutil.copytree(temp_path, debug_dir)
            print(f"Kept debug directory: {debug_dir}", file=sys.stderr)

    print(f"Overlay rendered: {output_path}", file=sys.stderr)
    print(f"Overlay size: {size.width}x{size.height} @ {config.fps} fps", file=sys.stderr)


def process_batch(args, input_files: list, preset_name: str) -> tuple:
    """
    Process multiple subtitle files in batch mode.

    Args:
        args: Parsed command-line arguments
        input_files: List of Path objects to process
        preset_name: Name of preset to use for all files

    Returns:
        Tuple of (success_count, failure_count, failed_files)
    """
    success_count = 0
    failure_count = 0
    failed_files = []
    total = len(input_files)

    print(f"\nBatch processing {total} file(s)...", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    for idx, input_path in enumerate(input_files, 1):
        input_path = Path(input_path)

        # Skip if file doesn't exist
        if not input_path.exists():
            print(f"[{idx}/{total}] SKIP: {input_path} (not found)", file=sys.stderr)
            failure_count += 1
            failed_files.append((input_path, "File not found"))
            continue

        # Skip if not a subtitle file
        if input_path.suffix.lower() not in (".srt", ".ass"):
            print(
                f"[{idx}/{total}] SKIP: {input_path} (not .srt/.ass)", file=sys.stderr
            )
            failure_count += 1
            failed_files.append((input_path, "Invalid file type"))
            continue

        # Determine output path
        if args.batch_output_dir:
            output_dir = Path(args.batch_output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / input_path.with_suffix(".mov").name
        else:
            output_path = input_path.with_suffix(".mov")

        # Process file
        try:
            print(f"\n[{idx}/{total}] Processing: {input_path.name}", file=sys.stderr)
            print(f"            Output: {output_path}", file=sys.stderr)

            render_subtitle_cli(input_path, output_path, preset_name, args)

            print(f"[{idx}/{total}] SUCCESS: {input_path.name}", file=sys.stderr)
            success_count += 1

        except Exception as e:
            print(f"[{idx}/{total}] FAILED: {input_path.name} - {e}", file=sys.stderr)
            failure_count += 1
            failed_files.append((input_path, str(e)))

    # Print summary
    print("\n" + "=" * 60, file=sys.stderr)
    print("Batch processing complete:", file=sys.stderr)
    print(f"  Total: {total} files", file=sys.stderr)
    print(f"  Success: {success_count}", file=sys.stderr)
    print(f"  Failed: {failure_count}", file=sys.stderr)

    if failed_files:
        print("\nFailed files:", file=sys.stderr)
        for path, reason in failed_files:
            print(f"  - {path}: {reason}", file=sys.stderr)

    return success_count, failure_count, failed_files


def main(argv=None) -> int:
    """
    Main CLI entry point.

    Args:
        argv: Command-line arguments (default: sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    try:
        args = parse_args(argv)

        # Handle --list-presets
        if args.list_presets:
            return list_presets_command()

        # Handle batch processing mode
        if args.batch or args.batch_list:
            import glob

            # Resolve input files
            input_files = []

            if args.batch_list:
                # Read file list from file
                list_path = Path(args.batch_list)
                if not list_path.exists():
                    print(
                        f"ERROR: Batch list file not found: {list_path}", file=sys.stderr
                    )
                    return 2
                with open(list_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            input_files.append(Path(line))
            elif args.batch:
                # Use input as glob pattern
                pattern = args.input
                matched_files = glob.glob(pattern, recursive=False)
                if not matched_files:
                    print(
                        f"ERROR: No files matched pattern: {pattern}", file=sys.stderr
                    )
                    return 2
                input_files = [Path(f) for f in matched_files]

            if not input_files:
                print("ERROR: No input files to process", file=sys.stderr)
                return 2

            # Process batch
            success_count, failure_count, _ = process_batch(
                args, input_files, args.preset
            )

            # Return exit code based on results
            if failure_count > 0 and success_count == 0:
                return 1  # All failed
            elif failure_count > 0:
                return 3  # Some failed
            else:
                return 0  # All succeeded

        # Validate input file
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
            return 2

        # Determine output path
        if args.out:
            output_path = Path(args.out)
        else:
            output_path = input_path.with_suffix(".mov")

        # Create output directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Handle interactive mode
        if args.interactive:
            from .interactive import interactive_mode

            return interactive_mode(args, input_path, output_path)

        # Render
        render_subtitle_cli(input_path, output_path, args.preset, args)

        return 0

    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        if not (hasattr(args, "quiet") and args.quiet):
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
