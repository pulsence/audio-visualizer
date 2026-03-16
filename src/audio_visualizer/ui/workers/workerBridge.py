"""Shared Qt bridge between AppEventEmitter and worker signals.

Subscribes to an AppEventEmitter and re-emits each event through the
corresponding Qt Signal so that UI widgets can connect via the normal
signals/slots mechanism without touching the event layer directly.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

from PySide6.QtCore import QObject, Signal

from audio_visualizer.events import (
    AppEvent,
    AppEventEmitter,
    EventLevel,
    EventType,
)

logger = logging.getLogger(__name__)


class WorkerSignals(QObject):
    """Qt signals that mirror the shared worker event vocabulary.

    Signals
    -------
    started(job_type, owner_tab_id, label)
        Emitted when a job begins.
    stage(name, index, total, data)
        Emitted when the job enters a new pipeline stage.
        *index* and *total* are ``-1`` when the source event omits them.
    progress(percent, message, data)
        Emitted for incremental progress updates.
        *percent* is ``-1.0`` when unavailable.
    log(level, message, data)
        Emitted for diagnostic / informational messages.
    completed(result)
        Emitted when the job finishes successfully.  *result* carries
        output paths, asset metadata, and optional follow-up actions.
    failed(error_message, data)
        Emitted when the job terminates due to an error.
    canceled(message)
        Emitted when the job is canceled by the user.
    """

    started = Signal(str, str, str)
    stage = Signal(str, int, int, dict)
    progress = Signal(float, str, dict)
    log = Signal(str, str, dict)
    completed = Signal(dict)
    failed = Signal(str, dict)
    canceled = Signal(str)


class WorkerBridge:
    """Bridges an :class:`AppEventEmitter` to a :class:`WorkerSignals` instance.

    The bridge subscribes to every event on the emitter and maps each
    :class:`EventType` to the matching Qt signal, coercing ``None`` values
    into safe defaults so that slot signatures stay simple.

    Parameters
    ----------
    emitter:
        The application event emitter to listen to.
    signals:
        The Qt signals object that will re-broadcast each event.
    """

    def __init__(
        self,
        emitter: AppEventEmitter,
        signals: WorkerSignals,
    ) -> None:
        self._emitter = emitter
        self._signals = signals
        self._attached = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def attach(self) -> None:
        """Subscribe to the emitter and start forwarding events."""
        if self._attached:
            return
        self._emitter.subscribe(self._on_event)
        self._attached = True
        logger.debug("WorkerBridge attached to emitter")

    def detach(self) -> None:
        """Unsubscribe from the emitter and stop forwarding events."""
        if not self._attached:
            return
        self._emitter.unsubscribe(self._on_event)
        self._attached = False
        logger.debug("WorkerBridge detached from emitter")

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    def _safe_data(self, data: Optional[Dict]) -> Dict:
        """Return *data* or an empty dict when ``None``."""
        return data if data is not None else {}

    def _on_event(self, event: AppEvent) -> None:
        """Route a single :class:`AppEvent` to the right Qt signal."""
        data = self._safe_data(event.data)

        if event.event_type is EventType.JOB_START:
            self._handle_started(event, data)
        elif event.event_type is EventType.STAGE:
            self._handle_stage(event, data)
        elif event.event_type in (EventType.PROGRESS, EventType.RENDER_PROGRESS):
            self._handle_progress(event, data)
        elif event.event_type in (EventType.LOG, EventType.MODEL_LOAD):
            self._handle_log(event, data)
        elif event.event_type in (EventType.JOB_COMPLETE, EventType.RENDER_COMPLETE):
            self._handle_completed(event, data)
        else:
            # RENDER_START or unknown future types -- emit as log
            self._handle_log(event, data)

    # ------------------------------------------------------------------
    # Per-type handlers
    # ------------------------------------------------------------------

    def _handle_started(self, event: AppEvent, data: Dict) -> None:
        job_type = data.get("job_type", "")
        owner_tab_id = data.get("owner_tab_id", "")
        label = event.message or data.get("label", "")
        self._signals.started.emit(job_type, owner_tab_id, label)

    def _handle_stage(self, event: AppEvent, data: Dict) -> None:
        name = event.message or data.get("name", "")
        index = data.get("stage_number", -1)
        if index is None:
            index = -1
        total = data.get("total_stages", -1)
        if total is None:
            total = -1
        self._signals.stage.emit(name, int(index), int(total), data)

    def _handle_progress(self, event: AppEvent, data: Dict) -> None:
        percent: float = -1.0
        raw = data.get("percent")
        if raw is not None:
            try:
                percent = float(raw)
            except (TypeError, ValueError):
                percent = -1.0
        message = event.message
        self._signals.progress.emit(percent, message, data)

    def _handle_log(self, event: AppEvent, data: Dict) -> None:
        level = event.level.value if event.level else EventLevel.INFO.value
        self._signals.log.emit(level, event.message, data)

    def _handle_completed(self, event: AppEvent, data: Dict) -> None:
        # A completion event at ERROR level indicates a failed job.
        if event.level is EventLevel.ERROR:
            error_msg = data.get("error", event.message)
            self._signals.failed.emit(error_msg, data)
        else:
            self._signals.completed.emit(data)
