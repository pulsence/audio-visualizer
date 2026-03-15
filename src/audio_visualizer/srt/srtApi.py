#!/usr/bin/env python3
"""Public library API for the SRT package."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple

from audio_visualizer.srt.core.pipeline import CoreTranscriptionResult, transcribe_file_internal
from audio_visualizer.events import AppEvent, AppEventEmitter, EventLevel, EventType
from audio_visualizer.srt.models import PipelineMode, ResolvedConfig, SubtitleBlock
from audio_visualizer.srt.core.whisperWrapper import init_whisper_model_internal


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


def _emit(emitter: Optional[AppEventEmitter], event: AppEvent) -> None:
    if emitter is not None:
        emitter.emit(event)


def load_model(
    model_name: str,
    device: str,
    strict_cuda: bool,
    emitter: Optional[AppEventEmitter] = None,
) -> Tuple[Any, str, str]:
    """Load a faster-whisper model for reuse across transcriptions."""

    _emit(emitter, AppEvent(event_type=EventType.LOG, message=f"Loading model '{model_name}'..."))
    try:
        model, device_used, compute_type = init_whisper_model_internal(
            model_name=model_name,
            device=device,
            strict_cuda=strict_cuda,
            emitter=emitter,
        )
        _emit(
            emitter,
            AppEvent(
                event_type=EventType.MODEL_LOAD,
                message=f"Model '{model_name}' loaded on {device_used}",
                data={
                    "model_name": model_name,
                    "device": device_used,
                    "compute_type": compute_type,
                    "success": True,
                },
            ),
        )
        return model, device_used, compute_type
    except Exception as exc:
        _emit(
            emitter,
            AppEvent(
                event_type=EventType.MODEL_LOAD,
                message=f"Failed to load model '{model_name}'",
                level=EventLevel.ERROR,
                data={
                    "model_name": model_name,
                    "device": device,
                    "compute_type": "",
                    "success": False,
                    "detail": str(exc),
                },
            ),
        )
        _emit(
            emitter,
            AppEvent(
                event_type=EventType.LOG,
                message=str(exc),
                level=EventLevel.ERROR,
            ),
        )
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
    emitter: Optional[AppEventEmitter] = None,
) -> TranscriptionResult:
    """Transcribe a single media file and write outputs."""

    if initial_prompt is not None:
        cfg.transcription.initial_prompt = initial_prompt

    try:
        _emit(
            emitter,
            AppEvent(
                event_type=EventType.JOB_START,
                message=f"Starting transcription for {input_path.name}",
                data={
                    "input_path": str(input_path),
                    "output_path": str(output_path),
                    "format": fmt,
                },
            ),
        )
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
            emitter=emitter,
        )
        _emit(
            emitter,
            AppEvent(
                event_type=EventType.JOB_COMPLETE,
                message=f"Finished transcription for {input_path.name}",
                data={
                    "input_path": str(input_path),
                    "output_path": str(output_path),
                    "success": True,
                    "elapsed": result.elapsed,
                },
            ),
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
        _emit(
            emitter,
            AppEvent(
                event_type=EventType.JOB_COMPLETE,
                message=f"Transcription failed for {input_path.name}",
                level=EventLevel.ERROR,
                data={
                    "input_path": str(input_path),
                    "output_path": str(output_path),
                    "success": False,
                    "error": str(exc),
                },
            ),
        )
        _emit(
            emitter,
            AppEvent(
                event_type=EventType.LOG,
                message=str(exc),
                level=EventLevel.ERROR,
            ),
        )
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
