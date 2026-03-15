#!/usr/bin/env python3
"""Command-line interface for Local SRT.

This is the main entry point for the srtgen command-line tool.
"""
from __future__ import annotations

import argparse
import dataclasses
import os
import sys
import traceback
from pathlib import Path
from typing import List, Optional, Tuple

from .api import load_model, transcribe_file
from .batch import default_output_for, expand_inputs, preflight_one
from .config import MODE_PIPELINE_DEFAULTS, PRESETS, apply_overrides, load_config_file
from .events import (
    ErrorEvent,
    FileCompleteEvent,
    FileStartEvent,
    LogEvent,
    ModelLoadEvent,
    ProgressEvent,
    StageEvent,
    WarnEvent,
)
from .logging_utils import format_duration
from .model_management import (
    delete_model,
    diagnose,
    download_model,
    list_available_models,
    list_downloaded_models,
)
from .models import PipelineMode, ResolvedConfig
from .diarization import is_diarization_available
from .script_reader import read_docx
from . import __version__
from .system import ensure_parent_dir, ffmpeg_ok


def die(msg: str, code: int = 1) -> int:
    print(f"ERROR: {msg}", file=sys.stderr, flush=True)
    return code


def create_cli_handler(quiet: bool, show_progress: bool):
    state = {"progress_active": False}

    def clear_progress() -> None:
        if not state["progress_active"]:
            return
        sys.stdout.write("\r" + (" " * 160) + "\r")
        sys.stdout.flush()
        state["progress_active"] = False

    def handler(event) -> None:
        if isinstance(event, ProgressEvent):
            if quiet or not show_progress:
                return
            pct = f"{event.percent:5.1f}%"
            media_t = format_duration(event.media_time)
            eta = f"ETA {format_duration(event.eta)}" if event.eta else ""
            msg = f"   {pct} segs:{event.segment_count:5d} | media_t={media_t} | {eta}".rstrip()
            sys.stdout.write("\r" + msg[:160].ljust(160))
            sys.stdout.flush()
            state["progress_active"] = True
            return

        if not quiet:
            clear_progress()

        if isinstance(event, LogEvent) and not quiet:
            print(event.message)
        elif isinstance(event, WarnEvent) and not quiet:
            print(f"WARNING: {event.message}", file=sys.stderr)
        elif isinstance(event, ErrorEvent):
            print(f"ERROR: {event.message}", file=sys.stderr)
        elif isinstance(event, StageEvent) and not quiet:
            print(f"{event.stage_number}/{event.total_stages} {event.stage}...")
        elif isinstance(event, FileStartEvent) and not quiet:
            print(f"File: {event.input_path}")
        elif isinstance(event, FileCompleteEvent) and not quiet:
            if event.success:
                print(f"Done: {event.output_path}")
            else:
                print(f"Failed: {event.input_path} ({event.error})")
        elif isinstance(event, ModelLoadEvent) and not quiet:
            if event.success:
                print(f"Model loaded: {event.model_name} ({event.device}, {event.compute_type})")
            else:
                print(f"Model load failed: {event.model_name} ({event.detail})", file=sys.stderr)

    return handler


def emit_event(handler, event) -> None:
    if handler is None:
        return
    emit = getattr(handler, "emit", None)
    if callable(emit):
        emit(event)
    else:
        handler(event)


def main() -> int:
    """Main entry point for the srtgen command-line tool."""
    ap = argparse.ArgumentParser(description="Local SRT/VTT generator (faster-whisper + ffmpeg)")
    ap.add_argument("inputs", nargs="*", help="Media file(s), directory, or glob pattern(s)")
    ap.add_argument("--glob", default=None, help="Additional glob pattern to include (optional)")
    ap.add_argument("--outdir", default=None, help="Output directory (batch mode). If omitted, writes next to input.")
    ap.add_argument("--keep-structure", action="store_true", help="When using --outdir, preserve directory structure.")
    ap.add_argument("--root", default=None, help="Base root for --keep-structure (defaults to common parent when possible).")

    ap.add_argument("-o", "--output", default=None, help="Single-file output path (only valid when one input expands to one file).")

    ap.add_argument("--format", choices=["srt", "vtt", "ass", "txt", "json"], default="srt", help="Primary output format")
    ap.add_argument("--emit-transcript", default=None, help="Also write a transcript TXT to this path (or outdir-based if a directory).")
    ap.add_argument("--emit-segments", default=None, help="Also write segments JSON to this path (or outdir-based if a directory).")
    ap.add_argument("--emit-bundle", default=None, help="Also write a full JSON bundle (segments+subs+config) to this path (or outdir-based if a directory).")
    ap.add_argument("--word-srt", default=None, help="Word-level SRT output path (shorts mode only).")

    ap.add_argument("--model", default="medium", help="tiny/base/small/medium/large-v3")
    ap.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto", help="auto/cpu/cuda")
    ap.add_argument("--strict-cuda", action="store_true", help="If set, fail instead of falling back when CUDA init fails.")
    ap.add_argument("--language", default=None, help="Optional language code (e.g., en). If omitted, auto-detect.")
    ap.add_argument("--prompt", default=None, help="Optional initial prompt text for transcription.")
    ap.add_argument("--prompt-file", default=None, help="Path to a prompt file (.docx or .txt).")
    ap.add_argument("--correction-srt", default=None, help="Corrected sentence-level SRT for word-level alignment.")
    ap.add_argument("--script", default=None, help="Script file (.docx or .txt) for sentence-level substitution.")
    ap.add_argument("--diarize", action="store_true", help="Enable speaker diarization (Transcript mode).")
    ap.add_argument("--hf-token", default=None, help="HuggingFace token for diarization (or set HF_TOKEN env var).")
    ap.add_argument("--word-level", action="store_true", help="Output word-level subtitle cues.")
    ap.add_argument(
        "--no-condition-on-previous-text",
        dest="condition_on_previous_text",
        action="store_false",
        default=None,
        help="Disable conditioning on previous text during transcription.",
    )
    ap.add_argument("--no-speech-threshold", type=float, default=None, help="No-speech threshold for transcription.")
    ap.add_argument("--log-prob-threshold", type=float, default=None, help="Log probability threshold for transcription.")
    ap.add_argument(
        "--compression-ratio-threshold",
        type=float,
        default=None,
        help="Compression ratio threshold for transcription.",
    )
    ap.add_argument(
        "--vad-filter",
        dest="vad_filter",
        action="store_true",
        default=None,
        help="Enable VAD filtering during transcription.",
    )
    ap.add_argument(
        "--no-vad-filter",
        dest="vad_filter",
        action="store_false",
        default=None,
        help="Disable VAD filtering during transcription.",
    )

    ap.add_argument("--preset", default=None, help="Preset formatting: shorts | yt | podcast | transcript.")
    ap.add_argument(
        "--mode",
        choices=[mode.value for mode in PipelineMode],
        default=PipelineMode.GENERAL.value,
        help="Pipeline mode: general | shorts | transcript.",
    )
    ap.add_argument("--config", default=None, help="JSON config file. CLI args override config.")
    ap.add_argument("--dry-run", action="store_true", help="Validate inputs and show resolved settings, but do not transcribe.")

    ap.add_argument("--max_chars", type=int, default=None)
    ap.add_argument("--max_lines", type=int, default=None)
    ap.add_argument("--target_cps", type=float, default=None)
    ap.add_argument("--min_dur", type=float, default=None)
    ap.add_argument("--max_dur", type=float, default=None)

    ap.add_argument("--no-comma-split", action="store_true")
    ap.add_argument("--no-medium-split", action="store_true")
    ap.add_argument("--prefer-punct-splits", action="store_true")

    ap.add_argument("--min-gap", type=float, default=None, help="Minimum gap between consecutive subtitle cues (seconds).")
    ap.add_argument("--pad", type=float, default=None, help="Pad cues into silence where possible (seconds).")
    ap.add_argument("--silence-min-dur", type=float, default=None, help="Minimum silence duration for splits (seconds).")
    ap.add_argument("--silence-threshold", type=float, default=None, help="Silence threshold in dB (e.g., -35).")

    ap.add_argument("--overwrite", action="store_true", help="Overwrite output if it exists")
    ap.add_argument("--keep_wav", action="store_true", help="Do not delete temporary WAV file")
    ap.add_argument("--tmpdir", default=None, help="Directory for temporary WAV (defaults to system temp)")

    ap.add_argument("--list-models", action="store_true", help="List downloaded faster-whisper models and exit.")
    ap.add_argument("--list-available-models", action="store_true", help="List available faster-whisper model names and exit.")
    ap.add_argument("--download-model", default=None, help="Download a faster-whisper model and exit.")
    ap.add_argument("--delete-model", default=None, help="Delete a downloaded model from cache and exit.")

    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--no-progress", action="store_true")
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--continue-on-error", action="store_true", help="Batch mode: continue processing other files on error.")
    ap.add_argument("--version", action="store_true")
    ap.add_argument("--diagnose", action="store_true")

    args = ap.parse_args()

    if args.version:
        print(__version__)
        return 0

    if args.diagnose:
        info = diagnose()
        print(f"tool_version: {info.tool_version}")
        print(f"python: {info.python_version}")
        print(f"platform: {info.platform}")
        print(f"ffmpeg: {info.ffmpeg_version}")
        print(f"ffprobe: {info.ffprobe_version}")
        print(f"faster_whisper: {info.faster_whisper_version}")
        print(f"PATH ffmpeg: {info.ffmpeg_path}")
        print(f"PATH ffprobe: {info.ffprobe_path}")
        return 0

    if args.list_models or args.list_available_models or args.download_model or args.delete_model:
        if args.inputs:
            return die("Model management options must be used without input files.", 2)
        rc = 0
        if args.list_models:
            downloaded = list_downloaded_models()
            if downloaded:
                print("Downloaded models:")
                for name, path in downloaded:
                    print(f"  - {name}: {path}")
            else:
                print("No downloaded models found.")
            print("Available models:")
            print("  " + ", ".join(list_available_models()))
        if args.list_available_models and not args.list_models:
            print("Available models:")
            print("  " + ", ".join(list_available_models()))
        if args.download_model:
            try:
                path = download_model(args.download_model)
                print(f"Downloaded {args.download_model} to {path}")
            except Exception as exc:
                return die(str(exc), 2)
        if args.delete_model:
            try:
                path = delete_model(args.delete_model)
                print(f"Deleted cached model: {args.delete_model} ({path})")
            except Exception as exc:
                return die(str(exc), 2)
        return rc

    quiet = args.quiet
    show_progress = not args.no_progress

    if args.preset:
        preset_key = args.preset.lower()
        if preset_key not in PRESETS:
            return die(
                f"Invalid --preset '{args.preset}'. "
                f"Valid presets: {', '.join(sorted(PRESETS.keys()))}",
                code=2,
            )
        args.preset = preset_key

    if args.word_srt and PipelineMode(args.mode) != PipelineMode.SHORTS:
        return die("--word-srt is only valid when --mode shorts.", 2)

    if not args.inputs:
        return die("No input files provided.", 2)
    files = expand_inputs(args.inputs, args.glob)
    files = [p for p in files if p.exists() and p.is_file()]
    if not files:
        return die("No input files found after expansion.", 2)

    outdir = Path(args.outdir) if args.outdir else None
    if outdir:
        ensure_parent_dir(outdir / "dummy.txt")
        outdir.mkdir(parents=True, exist_ok=True)

    if args.root:
        base_root = Path(args.root)
    else:
        base_root = None
        if args.keep_structure and len(files) > 1:
            try:
                base_root = Path(os.path.commonpath([str(f.resolve()) for f in files]))
                if base_root.is_file():
                    base_root = base_root.parent
            except Exception:
                base_root = None

    cfg = ResolvedConfig()

    try:
        cfg_file = load_config_file(args.config)
    except Exception as e:
        return die(str(e), 2)

    cfg = apply_overrides(cfg, cfg_file)

    if args.preset:
        cfg = apply_overrides(cfg, PRESETS[args.preset])

    mode = PipelineMode(args.mode)
    cfg = apply_overrides(cfg, MODE_PIPELINE_DEFAULTS[mode])

    if args.max_chars is not None:
        cfg.formatting.max_chars = args.max_chars
    if args.max_lines is not None:
        cfg.formatting.max_lines = args.max_lines
    if args.target_cps is not None:
        cfg.formatting.target_cps = args.target_cps
    if args.min_dur is not None:
        cfg.formatting.min_dur = args.min_dur
    if args.max_dur is not None:
        cfg.formatting.max_dur = args.max_dur

    if args.no_comma_split:
        cfg.formatting.allow_commas = False
    if args.no_medium_split:
        cfg.formatting.allow_medium = False
    if args.prefer_punct_splits:
        cfg.formatting.prefer_punct_splits = True

    if args.min_gap is not None:
        cfg.formatting.min_gap = float(args.min_gap)
    if args.pad is not None:
        cfg.formatting.pad = float(args.pad)

    if args.silence_min_dur is not None:
        cfg.silence.silence_min_dur = float(args.silence_min_dur)
    if args.silence_threshold is not None:
        cfg.silence.silence_threshold_db = float(args.silence_threshold)

    if args.condition_on_previous_text is not None:
        cfg.transcription.condition_on_previous_text = args.condition_on_previous_text
    if args.no_speech_threshold is not None:
        cfg.transcription.no_speech_threshold = float(args.no_speech_threshold)
    if args.log_prob_threshold is not None:
        cfg.transcription.log_prob_threshold = float(args.log_prob_threshold)
    if args.compression_ratio_threshold is not None:
        cfg.transcription.compression_ratio_threshold = float(args.compression_ratio_threshold)
    if args.vad_filter is not None:
        cfg.transcription.vad_filter = args.vad_filter

    if args.prompt:
        cfg.transcription.initial_prompt = args.prompt
    if args.prompt_file:
        prompt_path = Path(args.prompt_file)
        try:
            if prompt_path.suffix.lower() == ".docx":
                cfg.transcription.initial_prompt = read_docx(prompt_path)
            else:
                cfg.transcription.initial_prompt = prompt_path.read_text(encoding="utf-8")
        except Exception as exc:
            return die(f"Failed to read prompt file: {exc}", 2)

    script_path: Optional[Path] = None
    if args.script:
        script_path = Path(args.script)
        try:
            if script_path.suffix.lower() == ".docx":
                read_docx(script_path)
            else:
                script_path.read_text(encoding="utf-8")
        except Exception as exc:
            return die(f"Failed to read script file: {exc}", 2)

    if not ffmpeg_ok():
        return die("ffmpeg not found on PATH. Install it or add it to PATH.", 2)

    if args.diarize and not is_diarization_available():
        return die(
            "Speaker diarization requires pyannote.audio. Install with: pip install local-srt[diarize].",
            2,
        )

    if args.output is not None and len(files) != 1:
        return die("--output may only be used when exactly one input file is provided (after expansion).", 2)

    if args.dry_run and not quiet:
        import json

        print("Resolved config:")
        print(json.dumps(dataclasses.asdict(cfg), indent=2))

    hf_token = args.hf_token or os.getenv("HF_TOKEN")

    handler = create_cli_handler(quiet, show_progress)
    model = None
    device_used = "unknown"
    compute_type_used = "unknown"
    if not args.dry_run:
        try:
            model, device_used, compute_type_used = load_model(
                args.model, args.device, args.strict_cuda, handler
            )
        except Exception as exc:
            return die(str(exc), 2)

    failures: List[Tuple[Path, str]] = []

    for f in files:
        if args.output:
            primary_out = Path(args.output)
        else:
            primary_out = default_output_for(f, outdir, args.format, args.keep_structure, base_root)

        ok, reason = preflight_one(f, primary_out, args.overwrite)
        if not ok:
            failures.append((f, reason))
            if not args.continue_on_error:
                return die(reason, 2)
            print(f"WARNING: {f}: {reason}", file=sys.stderr)
            continue

        def side_path(user_path: Optional[str], ext: str) -> Optional[Path]:
            if not user_path:
                return None
            p = Path(user_path)
            if p.exists() and p.is_dir():
                return (p / f.name).with_suffix(ext)
            if user_path.endswith(os.sep) or user_path.endswith("/"):
                p.mkdir(parents=True, exist_ok=True)
                return (p / f.name).with_suffix(ext)
            return p

        transcript_out = side_path(args.emit_transcript, ".txt")
        segments_out = side_path(args.emit_segments, ".segments.json")
        bundle_out = side_path(args.emit_bundle, ".bundle.json") if args.emit_bundle else None

        def word_path(primary_out: Path, user_path: Optional[str]) -> Path:
            if not user_path:
                return primary_out.with_name(f"{primary_out.stem}.words.srt")
            p = Path(user_path)
            if p.exists() and p.is_dir():
                return p / f"{primary_out.stem}.words.srt"
            if user_path.endswith(os.sep) or user_path.endswith("/"):
                p.mkdir(parents=True, exist_ok=True)
                return p / f"{primary_out.stem}.words.srt"
            return p

        word_out: Optional[Path] = None
        if mode == PipelineMode.SHORTS:
            word_out = word_path(primary_out, args.word_srt)
            if word_out:
                ok_word, reason = preflight_one(f, word_out, args.overwrite)
                if not ok_word:
                    failures.append((f, reason))
                    if not args.continue_on_error:
                        return die(reason, 2)
                    print(f"WARNING: {f}: {reason}", file=sys.stderr)
                    continue

        emit_event(
            handler,
            FileStartEvent(input_path=str(f), output_path=str(primary_out)),
        )

        try:
            result = transcribe_file(
                input_path=f,
                output_path=primary_out,
                fmt=args.format,
                cfg=cfg,
                model=model,
                device_used=device_used,
                compute_type_used=compute_type_used,
                language=args.language,
                word_level=args.word_level,
                mode=mode,
                word_output_path=word_out,
                transcript_path=transcript_out,
                segments_path=segments_out,
                json_bundle_path=bundle_out,
                correction_srt=Path(args.correction_srt) if args.correction_srt else None,
                script_path=script_path,
                diarize=args.diarize,
                hf_token=hf_token,
                dry_run=args.dry_run,
                keep_wav=args.keep_wav,
                tmpdir=Path(args.tmpdir) if args.tmpdir else None,
                event_handler=handler,
            )
        except KeyboardInterrupt:
            return die("Interrupted by user.", 130)
        except Exception as e:
            if args.debug:
                traceback.print_exc()
            failures.append((f, str(e)))
            emit_event(
                handler,
                FileCompleteEvent(
                    input_path=str(f),
                    output_path=str(primary_out),
                    success=False,
                    error=str(e),
                ),
            )
            if not args.continue_on_error:
                return die(f"{f}: {e}", 1)
            print(f"WARNING: {f}: {e}", file=sys.stderr)
            continue

        emit_event(
            handler,
            FileCompleteEvent(
                input_path=str(f),
                output_path=str(primary_out),
                success=result.success,
                error=result.error,
            ),
        )

        if not result.success:
            failures.append((f, result.error or "failed"))
            if not args.continue_on_error:
                return die(result.error or "failed", 1)

    if failures:
        if not quiet:
            print("\nSummary: failures:")
            for f, msg in failures:
                print(f"  - {f}: {msg}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
