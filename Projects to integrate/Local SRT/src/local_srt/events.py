#!/usr/bin/env python3
"""Event system for Local SRT.

Defines dataclasses for structured events and a simple event emitter.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional


class EventLevel(str, Enum):
    """Logging levels for events."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class BaseEvent:
    """Base event with a timestamp (seconds since epoch)."""

    timestamp: float = field(default_factory=time.time)


@dataclass
class LogEvent(BaseEvent):
    """Informational log event."""

    message: str = ""
    level: EventLevel = EventLevel.INFO


@dataclass
class WarnEvent(BaseEvent):
    """Warning event."""

    message: str = ""


@dataclass
class ErrorEvent(BaseEvent):
    """Error event."""

    message: str = ""
    exception: Optional[Exception] = None


@dataclass
class ProgressEvent(BaseEvent):
    """Progress update event."""

    percent: float = 0.0
    segment_count: int = 0
    media_time: float = 0.0
    elapsed: float = 0.0
    eta: Optional[float] = None


@dataclass
class StageEvent(BaseEvent):
    """Stage transition event."""

    stage: str = ""
    stage_number: int = 0
    total_stages: int = 0


@dataclass
class FileStartEvent(BaseEvent):
    """Event fired when starting a file."""

    input_path: str = ""
    output_path: str = ""


@dataclass
class FileCompleteEvent(BaseEvent):
    """Event fired when completing a file."""

    input_path: str = ""
    output_path: str = ""
    success: bool = False
    error: Optional[str] = None


@dataclass
class ModelLoadEvent(BaseEvent):
    """Event fired after model load attempt."""

    model_name: str = ""
    device: str = ""
    compute_type: str = ""
    success: bool = False
    detail: Optional[str] = None


EventHandler = Callable[[BaseEvent], None]


class EventEmitter:
    """Simple event emitter with subscribe/emit."""

    def __init__(self) -> None:
        self._subscribers: List[EventHandler] = []

    def subscribe(self, handler: EventHandler) -> None:
        """Register an event handler."""

        self._subscribers.append(handler)

    def emit(self, event: BaseEvent) -> None:
        """Emit an event to all subscribers."""

        for handler in list(self._subscribers):
            handler(event)
