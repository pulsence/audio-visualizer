"""SRT Gen worker — batch transcription QRunnable.

Iterates through a queue of input files, calling transcribe_file for each.
Uses AppEventEmitter + WorkerBridge for progress forwarding. Supports batch
cancel (stops before next file) by checking a threading flag between items.
"""
from __future__ import annotations

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

logger = logging.getLogger(__name__)


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


class SrtGenWorker(QRunnable):
    """QRunnable that processes a batch of transcription jobs.

    Parameters
    ----------
    jobs:
        Ordered list of job specs to process.
    emitter:
        Shared event emitter that transcribe_file writes into.
    model_manager:
        Optional shared ModelManager. When provided, the worker uses it
        for model loading so the tab can track loaded state.
    """

    def __init__(
        self,
        jobs: List[SrtGenJobSpec],
        emitter: AppEventEmitter,
        model_manager: Any | None = None,
    ) -> None:
        super().__init__()
        self.setAutoDelete(True)

        self._jobs = jobs
        self._emitter = emitter
        self._model_manager = model_manager
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

            if self._model_manager is not None:
                # Use the shared ModelManager for consistent state
                model = self._model_manager.load(
                    model_name=first.model_name,
                    device=first.device,
                    strict_cuda=False,
                    emitter=self._emitter,
                )
                info = self._model_manager.model_info()
                device_used = info.device if info else first.device
                compute_type_used = info.compute_type if info else "default"
            else:
                model, device_used, compute_type_used = load_model(
                    model_name=first.model_name,
                    device=first.device,
                    strict_cuda=False,
                    emitter=self._emitter,
                )

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
            })

        except Exception as exc:
            logger.exception("SrtGenWorker batch failed: %s", exc)
            self.signals.failed.emit(str(exc), {"detail": str(exc)})

        finally:
            self._bridge.detach()
