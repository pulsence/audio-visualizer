"""Shared event protocol for Audio Visualizer.

Provides a unified event system used by all internal packages (srt, caption)
to emit structured progress, status, and diagnostic events. A logging bridge
forwards events to Python's logging module for persistent log capture.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class EventLevel(str, Enum):
    """Severity levels mapping to Python logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class EventType(str, Enum):
    """All event kinds emitted by internal packages."""

    LOG = "LOG"
    PROGRESS = "PROGRESS"
    STAGE = "STAGE"
    JOB_START = "JOB_START"
    JOB_COMPLETE = "JOB_COMPLETE"
    RENDER_START = "RENDER_START"
    RENDER_PROGRESS = "RENDER_PROGRESS"
    RENDER_COMPLETE = "RENDER_COMPLETE"
    MODEL_LOAD = "MODEL_LOAD"


_LEVEL_MAP = {
    EventLevel.DEBUG: logging.DEBUG,
    EventLevel.INFO: logging.INFO,
    EventLevel.WARNING: logging.WARNING,
    EventLevel.ERROR: logging.ERROR,
}


@dataclass
class AppEvent:
    """Unified event dataclass for all internal packages.

    Attributes:
        event_type: The kind of event.
        message: Human-readable description.
        level: Severity level.
        timestamp: Seconds since epoch.
        data: Optional domain-specific payload (percent, frame, speed, etc.).
    """

    event_type: EventType
    message: str = ""
    level: EventLevel = EventLevel.INFO
    timestamp: float = field(default_factory=time.time)
    data: Optional[Dict[str, Any]] = None


AppEventHandler = Callable[[AppEvent], None]


class AppEventEmitter:
    """Event emitter with subscribe/unsubscribe/emit and enable/disable toggle."""

    def __init__(self) -> None:
        self._subscribers: List[AppEventHandler] = []
        self._enabled = True

    def subscribe(self, handler: AppEventHandler) -> None:
        """Register an event handler."""
        self._subscribers.append(handler)

    def unsubscribe(self, handler: AppEventHandler) -> None:
        """Remove an event handler."""
        if handler in self._subscribers:
            self._subscribers.remove(handler)

    def emit(self, event: AppEvent) -> None:
        """Emit an event to all subscribers."""
        if not self._enabled:
            return
        for handler in list(self._subscribers):
            handler(event)

    def enable(self) -> None:
        """Enable event emission."""
        self._enabled = True

    def disable(self) -> None:
        """Disable event emission."""
        self._enabled = False

    @property
    def enabled(self) -> bool:
        """Check if event emission is enabled."""
        return self._enabled


class LoggingBridge:
    """Forwards AppEvent instances to a Python logger.

    Progress events are forwarded at DEBUG level to avoid log spam.
    All other events use their own level.
    """

    def __init__(self, logger: logging.Logger, emitter: AppEventEmitter) -> None:
        self._logger = logger
        self._emitter = emitter
        emitter.subscribe(self._handle)

    def _handle(self, event: AppEvent) -> None:
        level = _LEVEL_MAP.get(event.level, logging.INFO)

        # Downgrade high-frequency progress events to DEBUG
        if event.event_type in (EventType.PROGRESS, EventType.RENDER_PROGRESS):
            level = logging.DEBUG

        msg = event.message
        if event.data:
            extras = ", ".join(f"{k}={v}" for k, v in event.data.items())
            msg = f"{msg} [{extras}]"

        self._logger.log(level, msg)

    def detach(self) -> None:
        """Unsubscribe from the emitter."""
        self._emitter.unsubscribe(self._handle)
