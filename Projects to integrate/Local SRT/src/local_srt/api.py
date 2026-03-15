#!/usr/bin/env python3
"""Public library API for Local SRT."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple

from .batch import default_output_for, preflight_one
from .core import CoreTranscriptionResult, transcribe_file_internal
from .events import (
    ErrorEvent,
    EventHandler,
    FileCompleteEvent,
    FileStartEvent,
    LogEvent,
    ModelLoadEvent,
)
from .models import PipelineMode, ResolvedConfig, SubtitleBlock
from .whisper_wrapper import init_whisper_model_internal


@dataclass
class TranscriptionResult:
    """Public result for a single transcription."""

    success: bool
    input_path: Path
    output_path: Path
    subtitles: List[SubtitleBlock]
    segments: List[Any]
    device_used: str
    compute_type_used: str
    error: Optional[str] = None
    transcript_path: Optional[Path] = None
    segments_path: Optional[Path] = None
    json_bundle_path: Optional[Path] = None
    elapsed: Optional[float] = None


@dataclass
class BatchResult:
    """Summary of a batch transcription run."""

    total: int
    successful: int
    failed: int
    results: List[TranscriptionResult]


def _emit(handler: Optional[EventHandler], event: object) -> None:
    if handler is None:
        return
    emit = getattr(handler, "emit", None)
    if callable(emit):
        emit(event)
    else:
        handler(event)


def load_model(
    model_name: str,
    device: str,
    strict_cuda: bool,
    event_handler: Optional[EventHandler] = None,
) -> Tuple[Any, str, str]:
    """Load a faster-whisper model for reuse across transcriptions."""

    _emit(event_handler, LogEvent(message=f"Loading model '{model_name}'..."))
    try:
        model, device_used, compute_type = init_whisper_model_internal(
            model_name=model_name,
            device=device,
            strict_cuda=strict_cuda,
            event_handler=event_handler,
        )
        _emit(
            event_handler,
            ModelLoadEvent(
                model_name=model_name,
                device=device_used,
                compute_type=compute_type,
                success=True,
            ),
        )
        return model, device_used, compute_type
    except Exception as exc:
        _emit(
            event_handler,
            ModelLoadEvent(
                model_name=model_name,
                device=device,
                compute_type="",
                success=False,
                detail=str(exc),
            ),
        )
        _emit(event_handler, ErrorEvent(message=str(exc), exception=exc))
        raise


def transcribe_file(
    *,
    input_path: Path,
    output_path: Path,
    fmt: str,
    cfg: ResolvedConfig,
    model: Any,
    device_used: str,
    compute_type_used: str,
    language: Optional[str] = None,
    initial_prompt: str = "",
    word_level: bool = False,
    mode: PipelineMode = PipelineMode.GENERAL,
    word_output_path: Optional[Path] = None,
    transcript_path: Optional[Path] = None,
    segments_path: Optional[Path] = None,
    json_bundle_path: Optional[Path] = None,
    correction_srt: Optional[Path] = None,
    script_path: Optional[Path] = None,
    diarize: bool = False,
    hf_token: Optional[str] = None,
    dry_run: bool = False,
    keep_wav: bool = False,
    tmpdir: Optional[Path] = None,
    event_handler: Optional[EventHandler] = None,
) -> TranscriptionResult:
    """Transcribe a single media file and write outputs."""

    if initial_prompt is not None:
        cfg.transcription.initial_prompt = initial_prompt

    try:
        result: CoreTranscriptionResult = transcribe_file_internal(
            input_path=input_path,
            output_path=output_path,
            word_output_path=word_output_path,
            fmt=fmt,
            transcript_path=transcript_path,
            segments_path=segments_path,
            json_bundle_path=json_bundle_path,
            correction_srt=correction_srt,
            script_path=script_path,
            diarize=diarize,
            hf_token=hf_token,
            cfg=cfg,
            model=model,
            device_used=device_used,
            compute_type_used=compute_type_used,
            language=language,
            word_level=word_level,
            mode=mode,
            dry_run=dry_run,
            keep_wav=keep_wav,
            tmpdir=tmpdir,
            event_handler=event_handler,
        )
        return TranscriptionResult(
            success=True,
            input_path=input_path,
            output_path=output_path,
            subtitles=result.subtitles,
            segments=result.segments,
            device_used=result.device_used,
            compute_type_used=result.compute_type_used,
            transcript_path=result.transcript_path,
            segments_path=result.segments_path,
            json_bundle_path=result.json_bundle_path,
            elapsed=result.elapsed,
        )
    except Exception as exc:
        _emit(event_handler, ErrorEvent(message=str(exc), exception=exc))
        return TranscriptionResult(
            success=False,
            input_path=input_path,
            output_path=output_path,
            subtitles=[],
            segments=[],
            device_used=device_used,
            compute_type_used=compute_type_used,
            error=str(exc),
        )


def transcribe_batch(
    *,
    input_paths: Iterable[Path],
    outdir: Optional[Path],
    fmt: str,
    cfg: ResolvedConfig,
    model: Any,
    device_used: str,
    compute_type_used: str,
    language: Optional[str] = None,
    initial_prompt: str = "",
    word_level: bool = False,
    mode: PipelineMode = PipelineMode.GENERAL,
    keep_structure: bool = False,
    base_root: Optional[Path] = None,
    overwrite: bool = False,
    continue_on_error: bool = False,
    correction_srt: Optional[Path] = None,
    script_path: Optional[Path] = None,
    diarize: bool = False,
    hf_token: Optional[str] = None,
    dry_run: bool = False,
    keep_wav: bool = False,
    tmpdir: Optional[Path] = None,
    event_handler: Optional[EventHandler] = None,
) -> BatchResult:
    """Transcribe a batch of media files using a single model."""

    if initial_prompt is not None:
        cfg.transcription.initial_prompt = initial_prompt

    files = list(input_paths)
    results: List[TranscriptionResult] = []
    successful = 0
    failed = 0

    for input_path in files:
        output_path = default_output_for(input_path, outdir, fmt, keep_structure, base_root)
        ok, reason = preflight_one(input_path, output_path, overwrite)
        if not ok:
            failed += 1
            result = TranscriptionResult(
                success=False,
                input_path=input_path,
                output_path=output_path,
                subtitles=[],
                segments=[],
                device_used=device_used,
                compute_type_used=compute_type_used,
                error=reason,
            )
            results.append(result)
            _emit(
                event_handler,
                FileCompleteEvent(
                    input_path=str(input_path),
                    output_path=str(output_path),
                    success=False,
                    error=reason,
                ),
            )
            if not continue_on_error:
                break
            continue

        _emit(
            event_handler,
            FileStartEvent(
                input_path=str(input_path),
                output_path=str(output_path),
            ),
        )

        result = transcribe_file(
            input_path=input_path,
            output_path=output_path,
            fmt=fmt,
            cfg=cfg,
            model=model,
            device_used=device_used,
            compute_type_used=compute_type_used,
            language=language,
            word_level=word_level,
            mode=mode,
            transcript_path=None,
            segments_path=None,
            json_bundle_path=None,
            correction_srt=correction_srt,
            script_path=script_path,
            diarize=diarize,
            hf_token=hf_token,
            dry_run=dry_run,
            keep_wav=keep_wav,
            tmpdir=tmpdir,
            event_handler=event_handler,
        )

        results.append(result)
        if result.success:
            successful += 1
        else:
            failed += 1
            if not continue_on_error:
                _emit(
                    event_handler,
                    FileCompleteEvent(
                        input_path=str(input_path),
                        output_path=str(output_path),
                        success=False,
                        error=result.error,
                    ),
                )
                break

        _emit(
            event_handler,
            FileCompleteEvent(
                input_path=str(input_path),
                output_path=str(output_path),
                success=result.success,
                error=result.error,
            ),
        )

    _emit(
        event_handler,
        LogEvent(
            message=f"Batch complete: {successful} succeeded, {failed} failed (total {len(results)})."
        ),
    )

    return BatchResult(
        total=len(results),
        successful=successful,
        failed=failed,
        results=results,
    )
