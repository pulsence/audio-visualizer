"""
Progress tracking utilities.

This module provides progress tracking that emits events instead of
printing directly, enabling UI-agnostic progress reporting.
"""

import time

from ..core.events import EventEmitter, EventType, RenderEvent


class ProgressTracker:
    """
    Progress tracker that emits events via an EventEmitter.

    Example:
        from caption_animator.core.events import EventEmitter, RenderEvent, EventType

        emitter = EventEmitter()
        emitter.subscribe(lambda e: print(f"[{e.elapsed_seconds:.1f}s] {e.message}"))

        progress = ProgressTracker(emitter)
        progress.step("Loading subtitles...")
        progress.step("Rendering video...")
    """

    def __init__(self, emitter: EventEmitter, enabled: bool = True) -> None:
        """
        Initialize progress tracker.

        Args:
            emitter: EventEmitter for progress events
            enabled: Whether to emit progress events
        """
        self.emitter = emitter
        self.enabled = enabled
        self._start_time = time.time()

    def step(self, message: str) -> None:
        """
        Emit a progress step event.

        Args:
            message: Progress message to emit
        """
        if not self.enabled:
            return

        elapsed = time.time() - self._start_time
        self.emitter.emit(
            RenderEvent(
                event_type=EventType.STEP,
                message=message,
                elapsed_seconds=elapsed,
            )
        )

    def reset(self) -> None:
        """Reset the timer to current time."""
        self._start_time = time.time()
