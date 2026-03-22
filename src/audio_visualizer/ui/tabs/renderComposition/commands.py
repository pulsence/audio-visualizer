"""QUndoCommand subclasses for Render Composition undo/redo support.

Each command encapsulates a reversible edit operation on a
CompositionModel, storing enough state to undo and redo the change.
"""
from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any

from PySide6.QtGui import QUndoCommand

from audio_visualizer.ui.tabs.renderComposition.model import (
    CompositionAudioLayer,
    CompositionLayer,
    CompositionModel,
)

logger = logging.getLogger(__name__)


class AddLayerCommand(QUndoCommand):
    """Add a new layer to the composition model."""

    def __init__(
        self,
        model: CompositionModel,
        layer: CompositionLayer,
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._layer = copy.deepcopy(layer)
        self.setText(f"Add layer '{layer.display_name}'")

    def redo(self) -> None:
        self._model.add_layer(copy.deepcopy(self._layer))

    def undo(self) -> None:
        self._model.remove_layer(self._layer.id)


class RemoveLayerCommand(QUndoCommand):
    """Remove a layer from the composition model."""

    def __init__(
        self,
        model: CompositionModel,
        layer_id: str,
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._layer_id = layer_id
        layer = model.get_layer(layer_id)
        self._snapshot: CompositionLayer | None = copy.deepcopy(layer) if layer else None
        self._index: int | None = None
        if layer is not None:
            for i, l in enumerate(model.layers):
                if l.id == layer_id:
                    self._index = i
                    break
        name = layer.display_name if layer else layer_id
        self.setText(f"Remove layer '{name}'")

    def redo(self) -> None:
        self._model.remove_layer(self._layer_id)

    def undo(self) -> None:
        if self._snapshot is not None:
            restored = copy.deepcopy(self._snapshot)
            if self._index is not None and self._index <= len(self._model.layers):
                self._model.layers.insert(self._index, restored)
            else:
                self._model.layers.append(restored)


class MoveLayerCommand(QUndoCommand):
    """Change center-origin position of a layer."""

    def __init__(
        self,
        model: CompositionModel,
        layer_id: str,
        new_x: int,
        new_y: int,
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._layer_id = layer_id
        self._new_x = new_x
        self._new_y = new_y
        layer = model.get_layer(layer_id)
        self._old_x = layer.center_x if layer else 0
        self._old_y = layer.center_y if layer else 0
        self.setText("Move layer")

    def redo(self) -> None:
        self._model.move_layer(self._layer_id, self._new_x, self._new_y)

    def undo(self) -> None:
        self._model.move_layer(self._layer_id, self._old_x, self._old_y)


class ResizeLayerCommand(QUndoCommand):
    """Change size (width, height) of a layer."""

    def __init__(
        self,
        model: CompositionModel,
        layer_id: str,
        new_width: int,
        new_height: int,
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._layer_id = layer_id
        self._new_width = new_width
        self._new_height = new_height
        layer = model.get_layer(layer_id)
        self._old_width = layer.width if layer else 1920
        self._old_height = layer.height if layer else 1080
        self.setText("Resize layer")

    def redo(self) -> None:
        self._model.resize_layer(self._layer_id, self._new_width, self._new_height)

    def undo(self) -> None:
        self._model.resize_layer(self._layer_id, self._old_width, self._old_height)


class ReorderLayerCommand(QUndoCommand):
    """Change z-order of a layer."""

    def __init__(
        self,
        model: CompositionModel,
        layer_id: str,
        new_z_order: int,
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._layer_id = layer_id
        self._new_z_order = new_z_order
        layer = model.get_layer(layer_id)
        self._old_z_order = layer.z_order if layer else 0
        self.setText("Reorder layer")

    def redo(self) -> None:
        self._model.reorder_layer(self._layer_id, self._new_z_order)

    def undo(self) -> None:
        self._model.reorder_layer(self._layer_id, self._old_z_order)


class ChangeSourceCommand(QUndoCommand):
    """Change the source asset of a layer (including source metadata)."""

    def __init__(
        self,
        model: CompositionModel,
        layer_id: str,
        new_asset_id: str | None,
        new_asset_path: Path | None,
        display_name: str | None = None,
        source_kind: str = "",
        source_duration_ms: int = 0,
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._layer_id = layer_id
        self._new_asset_id = new_asset_id
        self._new_asset_path = new_asset_path
        self._new_display_name = display_name
        self._new_source_kind = source_kind
        self._new_source_duration_ms = source_duration_ms
        layer = model.get_layer(layer_id)
        self._old_asset_id = layer.asset_id if layer else None
        self._old_asset_path = layer.asset_path if layer else None
        self._old_display_name = layer.display_name if layer else ""
        self._old_source_kind = layer.source_kind if layer else ""
        self._old_source_duration_ms = layer.source_duration_ms if layer else 0
        self.setText("Change layer source")

    def redo(self) -> None:
        updates: dict[str, Any] = {
            "asset_id": self._new_asset_id,
            "asset_path": self._new_asset_path,
            "source_kind": self._new_source_kind,
            "source_duration_ms": self._new_source_duration_ms,
        }
        if self._new_display_name is not None:
            updates["display_name"] = self._new_display_name
        self._model.update_layer(self._layer_id, **updates)

    def undo(self) -> None:
        updates: dict[str, Any] = {
            "asset_id": self._old_asset_id,
            "asset_path": self._old_asset_path,
            "display_name": self._old_display_name,
            "source_kind": self._old_source_kind,
            "source_duration_ms": self._old_source_duration_ms,
        }
        self._model.update_layer(self._layer_id, **updates)


class ApplyPresetCommand(QUndoCommand):
    """Replace the current layers with a preset layout."""

    def __init__(
        self,
        model: CompositionModel,
        preset_layers: list[CompositionLayer],
        preset_name: str = "preset",
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._new_layers = [copy.deepcopy(l) for l in preset_layers]
        self._old_layers = [copy.deepcopy(l) for l in model.layers]
        self.setText(f"Apply preset '{preset_name}'")

    def redo(self) -> None:
        self._model.layers.clear()
        for layer in self._new_layers:
            self._model.layers.append(copy.deepcopy(layer))

    def undo(self) -> None:
        self._model.layers.clear()
        for layer in self._old_layers:
            self._model.layers.append(copy.deepcopy(layer))


class AddAudioLayerCommand(QUndoCommand):
    """Add a new audio layer to the composition model."""

    def __init__(
        self,
        model: CompositionModel,
        layer: CompositionAudioLayer,
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._layer = copy.deepcopy(layer)
        self.setText(f"Add audio layer '{layer.display_name}'")

    def redo(self) -> None:
        self._model.audio_layers.append(copy.deepcopy(self._layer))

    def undo(self) -> None:
        self._model.audio_layers = [
            al for al in self._model.audio_layers if al.id != self._layer.id
        ]


class RemoveAudioLayerCommand(QUndoCommand):
    """Remove an audio layer from the composition model."""

    def __init__(
        self,
        model: CompositionModel,
        layer_id: str,
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._layer_id = layer_id
        self._snapshot: CompositionAudioLayer | None = None
        self._index: int | None = None
        for i, al in enumerate(model.audio_layers):
            if al.id == layer_id:
                self._snapshot = copy.deepcopy(al)
                self._index = i
                break
        self.setText("Remove audio layer")

    def redo(self) -> None:
        self._model.audio_layers = [
            al for al in self._model.audio_layers if al.id != self._layer_id
        ]

    def undo(self) -> None:
        if self._snapshot is not None:
            restored = copy.deepcopy(self._snapshot)
            if self._index is not None and self._index <= len(self._model.audio_layers):
                self._model.audio_layers.insert(self._index, restored)
            else:
                self._model.audio_layers.append(restored)


class EditAudioLayerCommand(QUndoCommand):
    """Edit one or more fields on an audio layer."""

    def __init__(
        self,
        model: CompositionModel,
        layer_id: str,
        parent: QUndoCommand | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._layer_id = layer_id
        self._new_values = kwargs
        self._old_values: dict[str, Any] = {}
        for al in model.audio_layers:
            if al.id == layer_id:
                for key in kwargs:
                    if hasattr(al, key):
                        self._old_values[key] = getattr(al, key)
                break
        self.setText("Edit audio layer")

    def redo(self) -> None:
        for al in self._model.audio_layers:
            if al.id == self._layer_id:
                for key, val in self._new_values.items():
                    if hasattr(al, key):
                        setattr(al, key, val)
                break

    def undo(self) -> None:
        for al in self._model.audio_layers:
            if al.id == self._layer_id:
                for key, val in self._old_values.items():
                    if hasattr(al, key):
                        setattr(al, key, val)
                break
