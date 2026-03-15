#!/usr/bin/env python3
"""Core transcription logic for Local SRT."""
from __future__ import annotations

import json
import os
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple

from .audio import detect_silences, to_wav_16k_mono
from .events import ErrorEvent, EventHandler, LogEvent, ProgressEvent, StageEvent
from .logging_utils import format_duration
from .models import PipelineMode, ResolvedConfig, SubtitleBlock
from . import __version__ as TOOL_VERSION
from .output_writers import segments_to_jsonable, write_ass, write_json_bundle, write_srt, write_txt, write_vtt
from .subtitle_generation import (
    apply_silence_alignment,
    chunk_segments_to_transcript_blocks,
    chunk_segments_to_subtitles,
    chunk_words_to_subtitles,
    collect_words,
    hygiene_and_polish,
    words_to_subtitles,
)
from .alignment import align_corrected_srt, align_script_to_segments
from .diarization import assign_speakers, is_diarization_available, load_diarization_pipeline, run_diarization
from .script_reader import read_docx
from .system import ensure_parent_dir, ffmpeg_ok, probe_duration_seconds


@dataclass
class CoreTranscriptionResult:
    """Internal result for a transcription run."""

    input_path: Path
    output_path: Path
    transcript_path: Optional[Path]
    segments_path: Optional[Path]
    json_bundle_path: Optional[Path]
    segments: List[Any]
    subtitles: List[SubtitleBlock]
    device_used: str
    compute_type_used: str
    elapsed: float


def _emit(handler: Optional[EventHandler], event: object) -> None:
    if handler is None:
        return
    emit = getattr(handler, "emit", None)
    if callable(emit):
        emit(event)
    else:
        handler(event)


def transcribe_file_internal(
    *,
    input_path: Path,
    output_path: Path,
    word_output_path: Optional[Path],
    fmt: str,
    transcript_path: Optional[Path],
    segments_path: Optional[Path],
    json_bundle_path: Optional[Path],
    correction_srt: Optional[Path],
    script_path: Optional[Path],
    diarize: bool,
    hf_token: Optional[str],
    cfg: ResolvedConfig,
    model: Any,
    device_used: str,
    compute_type_used: str,
    language: Optional[str],
    word_level: bool,
    mode: PipelineMode = PipelineMode.GENERAL,
    dry_run: bool,
    keep_wav: bool,
    tmpdir: Optional[Path],
    event_handler: Optional[EventHandler],
) -> CoreTranscriptionResult:
    """Process a single media file and generate subtitles (no CLI dependencies)."""

    if not ffmpeg_ok():
        raise RuntimeError("ffmpeg not found on PATH. Install it or add it to PATH.")

    ensure_parent_dir(output_path)
    if word_output_path:
        ensure_parent_dir(word_output_path)
    if transcript_path:
        ensure_parent_dir(transcript_path)
    if segments_path:
        ensure_parent_dir(segments_path)
    if json_bundle_path:
        ensure_parent_dir(json_bundle_path)

    tmpdir_path = str(tmpdir) if tmpdir else None
    fd, tmp_wav = tempfile.mkstemp(prefix="srtgen_", suffix=".wav", dir=tmpdir_path)
    os.close(fd)

    started = time.time()
    try:
        _emit(event_handler, LogEvent(message=f"Input: {input_path}"))
        _emit(event_handler, LogEvent(message=f"Output: {output_path}"))

        if dry_run:
            _emit(event_handler, LogEvent(message="Dry run: skipping transcription."))
            return CoreTranscriptionResult(
                input_path=input_path,
                output_path=output_path,
                transcript_path=transcript_path,
                segments_path=segments_path,
                json_bundle_path=json_bundle_path,
                segments=[],
                subtitles=[],
                device_used=device_used,
                compute_type_used=compute_type_used,
                elapsed=time.time() - started,
            )

        _emit(event_handler, StageEvent(stage="Converting audio", stage_number=1, total_stages=4))
        to_wav_16k_mono(str(input_path), tmp_wav)

        _emit(event_handler, StageEvent(stage="Transcribing", stage_number=2, total_stages=4))
        t0 = time.time()
        segments_iter, _info = model.transcribe(
            tmp_wav,
            vad_filter=cfg.transcription.vad_filter,
            language=language,
            word_timestamps=True,
            condition_on_previous_text=cfg.transcription.condition_on_previous_text,
            no_speech_threshold=cfg.transcription.no_speech_threshold,
            log_prob_threshold=cfg.transcription.log_prob_threshold,
            compression_ratio_threshold=cfg.transcription.compression_ratio_threshold,
            initial_prompt=cfg.transcription.initial_prompt or None,
        )

        seg_list: List[Any] = []
        dur_total = probe_duration_seconds(str(tmp_wav))
        last_ratio = 0.0

        for idx, seg in enumerate(segments_iter, start=1):
            seg_list.append(seg)

            now = time.time()
            elapsed = max(0.001, now - t0)
            media_t = float(getattr(seg, "end", 0.0))

            percent = 0.0
            eta_sec: Optional[float] = None

            if dur_total and dur_total > 0:
                ratio = media_t / dur_total if media_t > 0 else 0.0
                ratio = max(last_ratio, ratio)
                ratio = min(1.0, ratio)
                last_ratio = ratio
                percent = ratio * 100.0

                if media_t > 0:
                    rtf = media_t / elapsed
                    if rtf > 0.01:
                        remaining_media = max(0.0, dur_total - media_t)
                        eta_sec = remaining_media / rtf

            _emit(
                event_handler,
                ProgressEvent(
                    percent=percent,
                    segment_count=idx,
                    media_time=media_t,
                    elapsed=elapsed,
                    eta=eta_sec,
                ),
            )

        _emit(
            event_handler,
            LogEvent(
                message=(
                    f"Transcription complete: {len(seg_list)} segments in "
                    f"{format_duration(time.time() - t0)}"
                )
            ),
        )

        _emit(event_handler, StageEvent(stage="Chunking + formatting", stage_number=3, total_stages=4))
        t1 = time.time()
        if diarize and mode == PipelineMode.TRANSCRIPT:
            if not is_diarization_available():
                raise RuntimeError("pyannote.audio is required for diarization.")
            if not hf_token:
                raise ValueError("HF token is required for diarization. Use --hf-token or HF_TOKEN.")
            _emit(event_handler, LogEvent(message="Running speaker diarization..."))
            pipeline = load_diarization_pipeline(hf_token)
            diarization = run_diarization(pipeline, tmp_wav)
            seg_list = assign_speakers(seg_list, diarization)

        script_applied = False
        if script_path:
            if script_path.suffix.lower() == ".docx":
                script_text = read_docx(script_path)
            else:
                script_text = script_path.read_text(encoding="utf-8")

            sentence_re = re.compile(r"[^.!?;]+[.!?;]?")
            sentences = [m.group().strip() for m in sentence_re.finditer(script_text) if m.group().strip()]
            if sentences:
                seg_list = align_script_to_segments(sentences, seg_list)
                script_applied = True
        silences: List[Tuple[float, float]] = detect_silences(
            tmp_wav,
            min_silence_dur=cfg.silence.silence_min_dur,
            silence_threshold_db=cfg.silence.silence_threshold_db,
        )

        words = collect_words(seg_list)
        if correction_srt and words:
            words = align_corrected_srt(correction_srt, words)
        word_subs: Optional[List[SubtitleBlock]] = None

        if mode == PipelineMode.SHORTS:
            if not words:
                raise ValueError("Shorts mode requires word timestamps but none were returned.")
            if not word_output_path:
                raise ValueError("Shorts mode requires a word_output_path.")
            if script_applied:
                subs = chunk_segments_to_subtitles(seg_list, cfg)
            else:
                subs = chunk_words_to_subtitles(words, cfg, silences)
            word_subs = words_to_subtitles(words)
        elif mode == PipelineMode.TRANSCRIPT:
            subs = chunk_segments_to_transcript_blocks(seg_list, cfg, silences)
        elif word_level:
            if not words:
                raise ValueError("Word-level output requested but no word timestamps are available.")
            subs = words_to_subtitles(words)
        else:
            if script_applied:
                subs = chunk_segments_to_subtitles(seg_list, cfg)
            elif words:
                subs = chunk_words_to_subtitles(words, cfg, silences)
            else:
                subs = chunk_segments_to_subtitles(seg_list, cfg)

        subs = apply_silence_alignment(subs, silences)
        subs = hygiene_and_polish(
            subs,
            min_gap=cfg.formatting.min_gap,
            pad=cfg.formatting.pad,
            silence_intervals=silences,
        )
        _emit(
            event_handler,
            LogEvent(
                message=(
                    f"Chunking complete: {len(subs)} subtitle blocks in "
                    f"{format_duration(time.time() - t1)}"
                )
            ),
        )

        _emit(event_handler, StageEvent(stage="Writing outputs", stage_number=4, total_stages=4))
        if fmt == "srt":
            write_srt(subs, output_path, max_chars=cfg.formatting.max_chars, max_lines=cfg.formatting.max_lines)
        elif fmt == "vtt":
            write_vtt(subs, output_path, max_chars=cfg.formatting.max_chars, max_lines=cfg.formatting.max_lines)
        elif fmt == "ass":
            write_ass(subs, output_path, max_chars=cfg.formatting.max_chars, max_lines=cfg.formatting.max_lines)
        elif fmt == "txt":
            write_txt(subs, output_path)
        elif fmt == "json":
            write_json_bundle(
                output_path,
                input_file=str(input_path),
                device_used=device_used,
                compute_type_used=compute_type_used,
                cfg=cfg,
                segments=seg_list,
                subs=subs,
                tool_version=TOOL_VERSION,
            )
        else:
            raise ValueError(f"Unknown format: {fmt}")

        if transcript_path:
            write_txt(subs, transcript_path)

        if segments_path:
            ensure_parent_dir(segments_path)
            tmp = segments_path.with_suffix(segments_path.suffix + ".tmp")
            include_words = any(getattr(seg, "words", None) for seg in seg_list)
            tmp.write_text(
                json.dumps(
                    {
                        "input_file": str(input_path),
                        "segments": segments_to_jsonable(seg_list, include_words=include_words),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            os.replace(tmp, segments_path)

        if word_subs and word_output_path:
            write_srt(
                word_subs,
                word_output_path,
                max_chars=cfg.formatting.max_chars,
                max_lines=cfg.formatting.max_lines,
            )

        if json_bundle_path:
            write_json_bundle(
                json_bundle_path,
                input_file=str(input_path),
                device_used=device_used,
                compute_type_used=compute_type_used,
                cfg=cfg,
                segments=seg_list,
                subs=subs,
                tool_version=TOOL_VERSION,
            )

        _emit(
            event_handler,
            LogEvent(message=f"Done: {output_path} (total {format_duration(time.time() - started)})"),
        )

        return CoreTranscriptionResult(
            input_path=input_path,
            output_path=output_path,
            transcript_path=transcript_path,
            segments_path=segments_path,
            json_bundle_path=json_bundle_path,
            segments=seg_list,
            subtitles=subs,
            device_used=device_used,
            compute_type_used=compute_type_used,
            elapsed=time.time() - started,
        )
    except Exception as exc:
        _emit(event_handler, ErrorEvent(message=str(exc), exception=exc))
        raise
    finally:
        if not keep_wav and os.path.exists(tmp_wav):
            try:
                os.remove(tmp_wav)
            except OSError:
                pass
