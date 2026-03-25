"""SRT Gen worker — batch transcription QRunnable.

Iterates through a queue of input files, calling transcribe_file for each.
Uses AppEventEmitter + WorkerBridge for progress forwarding. Supports batch
cancel (stops before next file) by checking a threading flag between items.

The worker always loads the model on its own thread to ensure GPU handles
(CUDA/cuBLAS) stay on the same thread that performs inference.  This avoids
cross-thread cublas errors and hangs that occur when a model is loaded on one
thread (e.g. the _ModelLoadWorker UI preload) and used on another.
"""
from __future__ import annotations

import concurrent.futures
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional

from PySide6.QtCore import QRunnable

from audio_visualizer.events import AppEvent, AppEventEmitter, EventLevel, EventType
from audio_visualizer.srt.models import PipelineMode, ResolvedConfig
from audio_visualizer.srt.srtApi import TranscriptionResult, load_model, transcribe_file
from audio_visualizer.ui.workers.workerBridge import WorkerBridge, WorkerSignals
from audio_visualizer import __version__ as TOOL_VERSION

logger = logging.getLogger(__name__)


def _resolve_lora_ct2_path(lora_name: str) -> Optional[Path]:
    """Return the CTranslate2 model directory for a trained LoRA adapter.

    Returns None if the LoRA model or its CT2 subdirectory does not exist.
    """
    try:
        from audio_visualizer.srt.training.loraTrainer import get_lora_models_dir

        model_dir = get_lora_models_dir() / lora_name / "ct2"
        if model_dir.is_dir():
            return model_dir
    except Exception:
        logger.debug("Could not resolve LoRA CT2 path for '%s'", lora_name)
    return None


@dataclass
class SrtGenJobSpec:
    """Parameters for a single transcription job within the batch."""

    input_path: Path
    output_path: Path
    fmt: str
    cfg: ResolvedConfig
    model_name: str
    device: str
    language: Optional[str]
    word_level: bool
    mode: PipelineMode
    transcript_path: Optional[Path] = None
    segments_path: Optional[Path] = None
    json_bundle_path: Optional[Path] = None
    diarize: bool = False
    hf_token: Optional[str] = None
    dry_run: bool = False
    keep_wav: bool = False
    lora_name: Optional[str] = None
    script_path: Optional[Path] = None
    existing_srt_path: Optional[Path] = None


class SrtGenWorker(QRunnable):
    """QRunnable that processes a batch of transcription jobs.

    The worker always loads the Whisper model on its own thread so that GPU
    handles stay thread-local, avoiding cross-thread cuBLAS / CUDA errors.

    Parameters
    ----------
    jobs:
        Ordered list of job specs to process.
    emitter:
        Shared event emitter that transcribe_file writes into.
    """

    def __init__(
        self,
        jobs: List[SrtGenJobSpec],
        emitter: AppEventEmitter,
    ) -> None:
        super().__init__()
        self.setAutoDelete(True)

        self._jobs = jobs
        self._emitter = emitter
        self._cancel_flag = threading.Event()
        self.signals = WorkerSignals()
        self._bridge = WorkerBridge(emitter, self.signals)
        self._results: List[TranscriptionResult] = []

    # ------------------------------------------------------------------
    # Cancel support
    # ------------------------------------------------------------------

    def cancel(self) -> None:
        """Request cancellation. Checked between queue items."""
        self._cancel_flag.set()

    @property
    def is_canceled(self) -> bool:
        """Return True if cancel has been requested."""
        return self._cancel_flag.is_set()

    # ------------------------------------------------------------------
    # Bundle-from-SRT
    # ------------------------------------------------------------------

    def _run_bundle_from_srt(
        self,
        job: SrtGenJobSpec,
        model: Any,
        device_used: str,
        compute_type_used: str,
    ) -> TranscriptionResult:
        """Process a bundle-from-SRT job.

        Runs Whisper for word-level timing, parses the existing subtitle
        file, aligns cues to Whisper words, and writes a bundle that
        preserves the original subtitle text with attached word timing.
        """
        import os
        import tempfile
        import time

        from audio_visualizer.srt.core.alignment import (
            align_cues_to_whisper_words,
            parse_subtitle_file,
        )
        from audio_visualizer.srt.io.audioHelpers import to_wav_16k_mono
        from audio_visualizer.srt.io.outputWriters import write_bundle_from_srt
        from audio_visualizer.srt.io.systemHelpers import ensure_parent_dir
        from audio_visualizer.srt.models import WordItem

        started = time.time()

        try:
            self._emitter.emit(AppEvent(
                event_type=EventType.LOG,
                message=f"Bundle from SRT: {job.existing_srt_path.name} + {job.input_path.name}",
            ))

            # Step 1: Parse existing subtitle file
            self._emitter.emit(AppEvent(
                event_type=EventType.LOG,
                message=f"Parsing subtitle file: {job.existing_srt_path.name}",
            ))
            cues = parse_subtitle_file(job.existing_srt_path)
            self._emitter.emit(AppEvent(
                event_type=EventType.LOG,
                message=f"Parsed {len(cues)} subtitle cues",
            ))

            # Step 2: Run Whisper for word-level timing
            self._emitter.emit(AppEvent(
                event_type=EventType.LOG,
                message="Running Whisper for word-level timing...",
            ))
            fd, tmp_wav = tempfile.mkstemp(prefix="srtgen_bundle_", suffix=".wav")
            os.close(fd)

            try:
                to_wav_16k_mono(str(job.input_path), tmp_wav)
                segments_iter, _info = model.transcribe(
                    tmp_wav,
                    vad_filter=job.cfg.transcription.vad_filter,
                    language=job.language,
                    word_timestamps=True,
                    condition_on_previous_text=job.cfg.transcription.condition_on_previous_text,
                    no_speech_threshold=job.cfg.transcription.no_speech_threshold,
                    log_prob_threshold=job.cfg.transcription.log_prob_threshold,
                    compression_ratio_threshold=job.cfg.transcription.compression_ratio_threshold,
                    initial_prompt=job.cfg.transcription.initial_prompt or None,
                )
                seg_list = list(segments_iter)
            finally:
                if not job.keep_wav and os.path.exists(tmp_wav):
                    try:
                        os.remove(tmp_wav)
                    except OSError:
                        pass

            # Collect all word-level timing
            whisper_words: list[WordItem] = []
            for seg in seg_list:
                for w in getattr(seg, "words", None) or []:
                    w_text = getattr(w, "word", getattr(w, "text", ""))
                    whisper_words.append(WordItem(
                        start=float(w.start),
                        end=float(w.end),
                        text=w_text,
                        confidence=getattr(w, "probability", None),
                    ))

            self._emitter.emit(AppEvent(
                event_type=EventType.LOG,
                message=f"Whisper produced {len(whisper_words)} words from {len(seg_list)} segments",
            ))

            # Step 3: Align existing cues to Whisper words
            self._emitter.emit(AppEvent(
                event_type=EventType.LOG,
                message="Aligning cues to Whisper word timing...",
            ))
            aligned = align_cues_to_whisper_words(cues, whisper_words)

            # Report alignment quality
            matched = sum(1 for a in aligned if a.alignment_status == "matched")
            partial = sum(1 for a in aligned if a.alignment_status == "partial")
            estimated = sum(1 for a in aligned if a.alignment_status == "estimated")
            avg_conf = (
                sum(a.alignment_confidence for a in aligned) / len(aligned)
                if aligned else 0.0
            )
            self._emitter.emit(AppEvent(
                event_type=EventType.LOG,
                message=(
                    f"Alignment: {matched} matched, {partial} partial, "
                    f"{estimated} estimated (avg confidence: {avg_conf:.2f})"
                ),
            ))

            # Step 4: Write bundle output
            output_path = job.json_bundle_path or job.output_path
            ensure_parent_dir(output_path)
            write_bundle_from_srt(
                output_path,
                aligned_cues=aligned,
                input_file=str(job.input_path),
                device_used=device_used,
                compute_type_used=compute_type_used,
                model_name=job.model_name,
                tool_version=TOOL_VERSION,
                cfg=job.cfg,
            )

            self._emitter.emit(AppEvent(
                event_type=EventType.LOG,
                message=f"Bundle written: {output_path}",
            ))

            elapsed = time.time() - started
            return TranscriptionResult(
                success=True,
                input_path=job.input_path,
                output_path=output_path,
                subtitles=[],
                segments=seg_list,
                device_used=device_used,
                compute_type_used=compute_type_used,
                json_bundle_path=output_path,
                elapsed=elapsed,
            )

        except Exception as exc:
            self._emitter.emit(AppEvent(
                event_type=EventType.LOG,
                message=f"Bundle-from-SRT failed: {exc}",
                level=EventLevel.ERROR,
            ))
            return TranscriptionResult(
                success=False,
                input_path=job.input_path,
                output_path=job.output_path,
                subtitles=[],
                segments=[],
                device_used=device_used,
                compute_type_used=compute_type_used,
                error=str(exc),
                elapsed=time.time() - started,
            )

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Execute the batch transcription on the thread-pool thread."""
        self._bridge.attach()
        total = len(self._jobs)

        try:
            # Load the model once using the first job's settings.
            if not self._jobs:
                self.signals.completed.emit({"results": [], "total": 0})
                return

            self._emitter.emit(AppEvent(
                event_type=EventType.JOB_START,
                message=f"Generating SRTs for {total} file(s)",
                data={
                    "job_type": "srt_gen",
                    "owner_tab_id": "srt_gen",
                    "label": f"Generating SRTs for {total} file(s)",
                },
            ))

            if self._cancel_flag.is_set():
                self.signals.canceled.emit("Cancelled before model load")
                return

            first = self._jobs[0]
            self._emitter.emit(AppEvent(
                event_type=EventType.STAGE,
                message="Loading model",
                data={"stage_number": 0, "total_stages": total + 1},
            ))

            # Resolve model name: if a LoRA adapter is selected, use the
            # merged CTranslate2 model path instead of the base model name.
            effective_model_name = first.model_name
            if first.lora_name:
                lora_model_path = _resolve_lora_ct2_path(first.lora_name)
                if lora_model_path is not None:
                    effective_model_name = str(lora_model_path)
                    self._emitter.emit(AppEvent(
                        event_type=EventType.LOG,
                        message=f"Using LoRA model: {first.lora_name}",
                    ))
                else:
                    self._emitter.emit(AppEvent(
                        event_type=EventType.LOG,
                        message=(
                            f"LoRA model '{first.lora_name}' not found, "
                            "falling back to base model"
                        ),
                        level=EventLevel.WARNING,
                    ))

            # Always load the model on THIS thread so GPU handles (CUDA /
            # cuBLAS) stay thread-local.  We wrap in a ThreadPoolExecutor so
            # we can poll for cancel while the blocking load_model runs.
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    load_model,
                    model_name=effective_model_name,
                    device=first.device,
                    strict_cuda=False,
                    emitter=self._emitter,
                )
                while not future.done():
                    if self._cancel_flag.wait(timeout=0.5):
                        future.cancel()
                        self.signals.canceled.emit("Cancelled during model load")
                        return
                model, device_used, compute_type_used = future.result()

            if self._cancel_flag.is_set():
                self.signals.canceled.emit("Cancelled after model load")
                return

            for idx, job in enumerate(self._jobs):
                if self._cancel_flag.is_set():
                    logger.info("Batch cancelled before file %d/%d", idx + 1, total)
                    self.signals.canceled.emit(
                        f"Cancelled after {idx}/{total} files"
                    )
                    return

                if job.existing_srt_path:
                    self._emitter.emit(AppEvent(
                        event_type=EventType.STAGE,
                        message=f"Bundle from SRT: {job.input_path.name} ({idx + 1}/{total})",
                        data={"stage_number": idx + 1, "total_stages": total + 1},
                    ))
                    result = self._run_bundle_from_srt(
                        job, model, device_used, compute_type_used
                    )
                else:
                    self._emitter.emit(AppEvent(
                        event_type=EventType.STAGE,
                        message=f"Transcribing {job.input_path.name} ({idx + 1}/{total})",
                        data={"stage_number": idx + 1, "total_stages": total + 1},
                    ))

                    result = transcribe_file(
                        input_path=job.input_path,
                        output_path=job.output_path,
                        fmt=job.fmt,
                        cfg=job.cfg,
                        model=model,
                        device_used=device_used,
                        compute_type_used=compute_type_used,
                        language=job.language,
                        word_level=job.word_level,
                        mode=job.mode,
                        transcript_path=job.transcript_path,
                        segments_path=job.segments_path,
                        json_bundle_path=job.json_bundle_path,
                        diarize=job.diarize,
                        hf_token=job.hf_token,
                        dry_run=job.dry_run,
                        keep_wav=job.keep_wav,
                        script_path=job.script_path,
                        emitter=self._emitter,
                    )
                self._results.append(result)

                # Emit per-file progress
                self._emitter.emit(AppEvent(
                    event_type=EventType.PROGRESS,
                    message=f"Completed {idx + 1}/{total}",
                    data={"percent": ((idx + 1) / total) * 100},
                ))

            # All done — emit batch completion
            self.signals.completed.emit({
                "results": [
                    {
                        "success": r.success,
                        "input_path": str(r.input_path),
                        "output_path": str(r.output_path),
                        "error": r.error,
                        "transcript_path": str(r.transcript_path) if r.transcript_path else None,
                        "segments_path": str(r.segments_path) if r.segments_path else None,
                        "json_bundle_path": str(r.json_bundle_path) if r.json_bundle_path else None,
                        "elapsed": r.elapsed,
                    }
                    for r in self._results
                ],
                "total": total,
                "device_used": device_used,
                "compute_type_used": compute_type_used,
            })

        except Exception as exc:
            logger.exception("SrtGenWorker batch failed: %s", exc)
            self.signals.failed.emit(str(exc), {"detail": str(exc)})

        finally:
            self._bridge.detach()
