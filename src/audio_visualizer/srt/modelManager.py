"""Reusable Whisper model lifecycle manager.

Provides a thread-safe way to load, cache, and reuse a Whisper model
across multiple transcription jobs without reloading.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Optional

from audio_visualizer.events import AppEvent, AppEventEmitter, EventLevel, EventType
from audio_visualizer.srt.core.whisperWrapper import init_whisper_model_internal


@dataclass
class ModelInfo:
    """Metadata about the currently loaded model."""

    model_name: str
    device: str
    compute_type: str


class ModelManager:
    """Manages the lifecycle of a single Whisper model instance.

    Thread-safe: the model may be accessed from multiple threads (e.g. Qt workers).
    """

    def __init__(self, emitter: Optional[AppEventEmitter] = None) -> None:
        self._emitter = emitter
        self._lock = threading.Lock()
        self._model: Optional[Any] = None
        self._info: Optional[ModelInfo] = None

    def load(
        self,
        model_name: str,
        device: str = "auto",
        strict_cuda: bool = False,
        emitter: Optional[AppEventEmitter] = None,
    ) -> Any:
        """Load a Whisper model. Returns the model instance.

        If a model with the same name is already loaded, returns it without reloading.
        If a different model is loaded, unloads it first.
        """
        event_emitter = emitter or self._emitter
        with self._lock:
            if self._model is not None and self._info is not None:
                if self._info.model_name == model_name and (
                    device == "auto" or self._info.device == device
                ):
                    return self._model
                self._unload_internal()

            if event_emitter is not None:
                event_emitter.emit(AppEvent(
                    event_type=EventType.LOG,
                    message=f"Loading model '{model_name}'...",
                ))

            try:
                model, device_used, compute_type = init_whisper_model_internal(
                    model_name=model_name,
                    device=device,
                    strict_cuda=strict_cuda,
                    emitter=event_emitter,
                )
            except Exception as exc:
                if event_emitter is not None:
                    event_emitter.emit(AppEvent(
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
                    ))
                    event_emitter.emit(AppEvent(
                        event_type=EventType.LOG,
                        message=str(exc),
                        level=EventLevel.ERROR,
                    ))
                raise
            self._model = model
            self._info = ModelInfo(
                model_name=model_name,
                device=device_used,
                compute_type=compute_type,
            )

            if event_emitter is not None:
                event_emitter.emit(AppEvent(
                    event_type=EventType.MODEL_LOAD,
                    message=f"Model '{model_name}' loaded on {device_used}",
                    data={
                        "model_name": model_name,
                        "device": device_used,
                        "compute_type": compute_type,
                        "success": True,
                    },
                ))

            return self._model

    def get_model(self) -> Optional[Any]:
        """Return the current model instance, or None if not loaded."""
        with self._lock:
            return self._model

    def is_loaded(self) -> bool:
        """Check if a model is currently loaded."""
        with self._lock:
            return self._model is not None

    def model_info(self) -> Optional[ModelInfo]:
        """Return metadata about the loaded model, or None if not loaded."""
        with self._lock:
            return self._info

    def unload(self) -> None:
        """Release the currently loaded model."""
        with self._lock:
            self._unload_internal()

    def _unload_internal(self) -> None:
        self._model = None
        self._info = None
