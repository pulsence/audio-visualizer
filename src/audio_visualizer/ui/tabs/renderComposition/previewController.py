"""Preview scheduling controller for Render Composition.

Owns the dirty-state flag, coalesced seek timer, and engine
load/seek coordination so that :class:`RenderCompositionTab` no
longer mixes preview scheduling directly with UI event handling.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel

from audio_visualizer.ui.tabs.renderComposition.evaluation import (
    compute_composition_duration_ms,
)

if TYPE_CHECKING:
    from audio_visualizer.ui.tabs.renderComposition.model import CompositionModel
    from audio_visualizer.ui.tabs.renderComposition.playbackEngine import PlaybackEngine

logger = logging.getLogger(__name__)


class PreviewController:
    """Coordinates preview scheduling between UI edits and the playback engine.

    Parameters
    ----------
    engine : PlaybackEngine
        The playback engine to delegate load/seek/play calls to.
    model_provider : callable
        Returns the current :class:`CompositionModel`.
    status_label : QLabel | None
        Optional label to update with preview failure messages.
    """

    def __init__(
        self,
        engine: PlaybackEngine,
        model_provider: Any,
        status_label: QLabel | None = None,
        *,
        parent_timer_owner: Any = None,
        on_seek_completed: Any = None,
    ) -> None:
        self._engine = engine
        self._model_provider = model_provider
        self._status_label = status_label
        self._on_seek_completed = on_seek_completed
        self._preview_model_dirty = True
        self._pending_seek_ms: int | None = None

        owner = parent_timer_owner or engine
        self._seek_timer = QTimer(owner)
        self._seek_timer.setSingleShot(True)
        self._seek_timer.timeout.connect(self._flush_seek)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_dirty(self) -> bool:
        return self._preview_model_dirty

    def mark_dirty(self) -> None:
        """Flag the model as changed so the next seek triggers a reload."""
        self._preview_model_dirty = True

    def schedule_seek(self, ms: int) -> None:
        """Queue a preview seek that will fire on the next event-loop turn.

        Rapid calls are coalesced — only the latest *ms* value is used.
        """
        self._pending_seek_ms = ms
        self._seek_timer.start(0)

    def load_engine_data(self) -> None:
        """Build engine-compatible layer dicts from the model and call ``engine.load()``."""
        model = self._model_provider()
        if model is None:
            return

        visual_layers: list[dict] = []
        audio_layers: list[dict] = []
        duration_ms = 0
        try:
            for layer in model.get_layers_sorted():
                if not layer.enabled:
                    continue
                visual_layers.append({
                    "id": layer.id,
                    "path": str(layer.asset_path) if layer.asset_path else "",
                    "source_kind": layer.source_kind,
                    "source_duration_ms": layer.source_duration_ms,
                    "start_ms": layer.start_ms,
                    "end_ms": layer.start_ms + layer.effective_duration_ms(),
                    "behavior_after_end": layer.behavior_after_end,
                    "center_x": layer.center_x,
                    "center_y": layer.center_y,
                    "width": layer.width,
                    "height": layer.height,
                    "z_order": layer.z_order,
                    "opacity": 1.0,
                    "enabled": layer.enabled,
                })

            for al in model.audio_layers:
                if not al.enabled:
                    continue
                audio_layers.append({
                    "id": al.id,
                    "path": str(al.asset_path) if al.asset_path else "",
                    "start_ms": al.start_ms,
                    "duration_ms": al.effective_end_ms() - al.start_ms,
                    "volume": al.volume,
                    "muted": al.muted,
                    "enabled": al.enabled,
                })

            duration_ms = compute_composition_duration_ms(model)
            self._engine.load(
                visual_layers,
                audio_layers,
                duration_ms,
                output_width=model.output_width,
                output_height=model.output_height,
            )
        except Exception:
            logger.exception(
                "Render Composition preview load failed "
                "(visual_layers=%d, audio_layers=%d, duration_ms=%d).",
                len(visual_layers),
                len(audio_layers),
                duration_ms,
            )
            self._set_failure_status("Preview failed — check logs for details.")
            raise
        self._preview_model_dirty = False
        self._clear_failure_status()

    def ensure_loaded(self) -> None:
        """Reload engine data if dirty."""
        if self._preview_model_dirty:
            self.load_engine_data()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _flush_seek(self) -> None:
        """Execute the latest queued preview seek."""
        if self._pending_seek_ms is None:
            return
        ms = self._pending_seek_ms
        self._pending_seek_ms = None
        self._seek_preview(ms)

    def _seek_preview(self, ms: int) -> None:
        """Load engine data if needed and render the frame at *ms*."""
        if self._preview_model_dirty:
            self.load_engine_data()
        try:
            self._engine.seek_from_timeline(ms)
            if self._on_seek_completed is not None:
                self._on_seek_completed(ms)
            self._clear_failure_status()
        except Exception:
            logger.exception(
                "Render Composition preview seek failed at %d ms (dirty=%s).",
                ms,
                self._preview_model_dirty,
            )
            self._set_failure_status("Preview failed — check logs for details.")

    def _clear_failure_status(self) -> None:
        """Clear stale preview failure text after a successful operation."""
        if self._status_label is None:
            return
        if self._status_label.text().startswith("Preview failed"):
            self._status_label.setText("")

    def _set_failure_status(self, text: str) -> None:
        """Update the preview status label after a preview failure."""
        if self._status_label is not None:
            self._status_label.setText(text)
