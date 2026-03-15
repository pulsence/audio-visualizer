"""
Progress tracking utilities.

This module provides progress tracking that emits events instead of
printing directly, enabling UI-agnostic progress reporting.
"""

import time

from audio_visualizer.events import AppEvent, AppEventEmitter, EventType


class ProgressTracker:
    """
    Progress tracker that emits events via an AppEventEmitter.

    Example:
        from audio_visualizer.events import AppEventEmitter, AppEvent, EventType

        emitter = AppEventEmitter()
        emitter.subscribe(lambda e: print(f"[STAGE] {e.message}"))

        progress = ProgressTracker(emitter)
        progress.step("Loading subtitles...")
        progress.step("Rendering video...")
    """

    def __init__(self, emitter: AppEventEmitter, enabled: bool = True) -> None:
        """
        Initialize progress tracker.

        Args:
            emitter: AppEventEmitter for progress events
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

        self.emitter.emit(
            AppEvent(
                event_type=EventType.STAGE,
                message=message,
            )
        )

    def reset(self) -> None:
        """Reset the timer to current time."""
        self._start_time = time.time()
