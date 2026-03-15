"""
Event system for progress reporting and logging.

This module provides a callback-based event system that allows library users
to receive progress updates without coupling to specific UI implementations.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Protocol


class EventType(Enum):
    """Types of events that can be emitted during rendering."""

    STEP = auto()  # General progress step
    RENDER_START = auto()  # FFmpeg render starting
    RENDER_PROGRESS = auto()  # FFmpeg progress update (frame, time, speed)
    RENDER_COMPLETE = auto()  # FFmpeg render finished
    DEBUG = auto()  # Debug information (e.g., FFmpeg command)
    WARNING = auto()  # Warning message
    ERROR = auto()  # Error message


@dataclass
class RenderEvent:
    """Event data for rendering progress."""

    event_type: EventType
    message: str = ""
    elapsed_seconds: float = 0.0
    data: Optional[Dict[str, Any]] = None

    # FFmpeg-specific fields
    frame: Optional[int] = None
    time: Optional[str] = None
    speed: Optional[str] = None


class EventHandler(Protocol):
    """Protocol for event handlers."""

    def __call__(self, event: RenderEvent) -> None: ...


class EventEmitter:
    """
    Manages event subscriptions and emission.

    Example:
        emitter = EventEmitter()

        def my_handler(event: RenderEvent):
            if event.event_type == EventType.STEP:
                print(f"[{event.elapsed_seconds:.1f}s] {event.message}")

        emitter.subscribe(my_handler)
        emitter.emit(RenderEvent(EventType.STEP, "Loading subtitles"))
    """

    def __init__(self) -> None:
        self._handlers: List[EventHandler] = []
        self._enabled = True

    def subscribe(self, handler: EventHandler) -> None:
        """Add an event handler."""
        self._handlers.append(handler)

    def unsubscribe(self, handler: EventHandler) -> None:
        """Remove an event handler."""
        if handler in self._handlers:
            self._handlers.remove(handler)

    def emit(self, event: RenderEvent) -> None:
        """Emit an event to all handlers."""
        if not self._enabled:
            return
        for handler in self._handlers:
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
