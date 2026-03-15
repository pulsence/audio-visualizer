"""
Command-line argument parser.
"""

import argparse
import sys


def create_parser() -> argparse.ArgumentParser:
    """
    Create and configure the argument parser.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog="caption-animator",
        description="Render transparent subtitle overlay videos for DaVinci Resolve.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Render with built-in preset
  caption-animator input.srt --preset modern_box --out overlay.mov

  # Use custom preset
  caption-animator input.srt --preset my_preset.json --out overlay.mov

  # Use named preset from multi-preset file
  caption-animator input.srt --preset presets.yaml:fancy --out overlay.mov

  # Change output quality (default is small/H.264)
  caption-animator input.srt --quality medium  # ProRes 422 HQ
  caption-animator input.srt --quality large   # ProRes 4444 with alpha

  # Interactive mode for tweaking
  caption-animator input.srt --interactive

  # Batch process all SRT files in directory
  caption-animator "*.srt" --batch --preset modern_box

  # Batch with output directory
  caption-animator "subtitles/*.srt" --batch --batch-output-dir output/

  # Batch from file list
  caption-animator --batch-list files.txt --batch-output-dir rendered/

  # List available presets
  caption-animator --list-presets
        """
    )

    # List presets mode
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="List available presets (built-in and presets/ directory) and exit"
    )

    # Input file
    parser.add_argument(
        "input",
        nargs="?",
        help="Input subtitle file (.srt or .ass)"
    )

    # Output file
    parser.add_argument(
        "--out",
        default=None,
        help="Output overlay video path (.mov recommended). Default: <input>.mov"
    )

    # Preset selection
    parser.add_argument(
        "--preset",
        default="modern_box",
        help="Preset reference: built-in name, file path, or path:name for multi-preset files"
    )

    parser.add_argument(
        "--no-preset-for-ass",
        action="store_true",
        help="If input is .ass, ignore --preset unless --reskin is provided"
    )

    # ASS-specific options
    parser.add_argument(
        "--reskin",
        action="store_true",
        help="For .ass: apply preset style to Default and assign all events"
    )

    parser.add_argument(
        "--strip-overrides",
        action="store_true",
        help="When --reskin, strip existing ASS override tags before reapplying"
    )

    # Animation control
    parser.add_argument(
        "--apply-animation",
        action="store_true",
        help="Inject preset animation tags (auto for SRT conversion)"
    )

    parser.add_argument(
        "--no-animation",
        action="store_true",
        help="Disable animation injection even if preset includes it"
    )

    # Video settings
    parser.add_argument(
        "--fps",
        default="30",
        help="Overlay framerate (e.g., 30, 60, or 30000/1001). Default: 30"
    )

    parser.add_argument(
        "--safety-scale",
        type=float,
        default=1.12,
        help="Multiplier to avoid edge clipping. Default: 1.12"
    )

    parser.add_argument(
        "--quality",
        choices=["small", "medium", "large"],
        default="small",
        help=(
            "Output quality/size preset. "
            "small: H.264 (~5-10MB/min, universal compatibility), "
            "medium: ProRes 422 HQ (~220Mbps, no alpha), "
            "large: ProRes 4444 (~330Mbps, with alpha). "
            "Default: small"
        )
    )

    # Output options
    parser.add_argument(
        "--keep-ass",
        action="store_true",
        help="Save intermediate ASS file alongside output"
    )

    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep temporary working directory for debugging"
    )

    # Verbosity
    parser.add_argument(
        "--loglevel",
        default="error",
        choices=["quiet", "error", "warning", "info", "debug"],
        help="FFmpeg log level. Default: error"
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output (errors still print)"
    )

    parser.add_argument(
        "--hide-ffmpeg-progress",
        action="store_true",
        help="Hide FFmpeg render progress (frames/time)"
    )

    # Interactive mode
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Interactive mode: tweak preset settings and re-render"
    )

    # Batch processing mode
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Batch mode: treat input as glob pattern (e.g., '*.srt')"
    )

    parser.add_argument(
        "--batch-list",
        help="File containing list of input files to process (one per line)"
    )

    parser.add_argument(
        "--batch-output-dir",
        help="Output directory for batch processing (default: same as input)"
    )

    return parser


def parse_args(argv=None):
    """
    Parse command-line arguments.

    Args:
        argv: Argument list (default: sys.argv[1:])

    Returns:
        Parsed arguments namespace
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    # Validation
    if not args.list_presets and not args.input:
        parser.error("Input subtitle file is required unless --list-presets is used")

    if args.strip_overrides and not args.reskin:
        parser.error("--strip-overrides requires --reskin")

    if args.apply_animation and args.no_animation:
        parser.error("--apply-animation and --no-animation are mutually exclusive")

    return args
