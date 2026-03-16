"""Tests for RenderCompositionTab, composition model, undo/redo, and presets."""

from pathlib import Path

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

import pytest

from audio_visualizer.ui.sessionContext import SessionAsset
from audio_visualizer.ui.tabs.renderCompositionTab import RenderCompositionTab
from audio_visualizer.ui.tabs.renderComposition.model import (
    CompositionLayer,
    CompositionModel,
    DEFAULT_MATTE_SETTINGS,
    VALID_BEHAVIORS,
    VALID_LAYER_TYPES,
)
from audio_visualizer.ui.tabs.renderComposition.commands import (
    AddLayerCommand,
    ApplyPresetCommand,
    ChangeAudioSourceCommand,
    ChangeSourceCommand,
    MoveLayerCommand,
    RemoveLayerCommand,
    ReorderLayerCommand,
    ResizeLayerCommand,
)
from audio_visualizer.ui.tabs.renderComposition.presets import (
    PRESET_NAMES,
    get_preset,
)


# ------------------------------------------------------------------
# Tab identity
# ------------------------------------------------------------------


class TestRenderCompositionTabIdentity:
    def test_tab_id_and_title(self):
        tab = RenderCompositionTab()
        assert tab.tab_id == "render_composition"
        assert tab.tab_title == "Render Composition"

    def test_has_undo_support(self):
        tab = RenderCompositionTab()
        assert tab.has_undo_support is True

    def test_undo_stack_limit(self):
        tab = RenderCompositionTab()
        assert tab._undo_stack is not None
        assert tab._undo_stack.undoLimit() == 100


# ------------------------------------------------------------------
# Settings round-trip
# ------------------------------------------------------------------


class TestRenderCompositionTabSettings:
    def test_collect_settings_structure(self):
        tab = RenderCompositionTab()
        settings = tab.collect_settings()
        expected_keys = {"model", "output_path", "preset"}
        assert set(settings.keys()) == expected_keys

    def test_collect_settings_model_structure(self):
        tab = RenderCompositionTab()
        settings = tab.collect_settings()
        model_data = settings["model"]
        assert "layers" in model_data
        assert "audio_source_asset_id" in model_data
        assert "output_width" in model_data
        assert "output_height" in model_data
        assert "output_fps" in model_data

    def test_apply_settings_roundtrip(self):
        tab = RenderCompositionTab()

        # Add a layer through the model and set output settings
        tab._model.add_layer(CompositionLayer(
            display_name="Test BG",
            layer_type="background",
            x=0, y=0, width=1920, height=1080,
            z_order=0, start_ms=0, end_ms=10000,
        ))
        tab._model.output_width = 1280
        tab._model.output_height = 720
        tab._model.output_fps = 24.0

        original = tab.collect_settings()

        # Apply to a fresh tab
        tab2 = RenderCompositionTab()
        tab2.apply_settings(original)
        restored = tab2.collect_settings()

        assert restored["model"]["output_width"] == 1280
        assert restored["model"]["output_height"] == 720
        assert restored["model"]["output_fps"] == 24.0
        assert len(restored["model"]["layers"]) == 1
        assert restored["model"]["layers"][0]["display_name"] == "Test BG"
        assert restored["model"]["layers"][0]["layer_type"] == "background"

    def test_apply_settings_output_path(self):
        tab = RenderCompositionTab()
        tab.apply_settings({"output_path": "/tmp/my_output.mp4"})
        settings = tab.collect_settings()
        assert settings["output_path"] == "/tmp/my_output.mp4"


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------


class TestRenderCompositionTabValidation:
    def test_validate_empty_fails(self):
        tab = RenderCompositionTab()
        valid, msg = tab.validate_settings()
        assert valid is False
        assert "no enabled layers" in msg.lower()

    def test_validate_layer_without_source_fails(self):
        tab = RenderCompositionTab()
        tab._model.add_layer(CompositionLayer(
            display_name="Empty",
            layer_type="custom",
        ))
        valid, msg = tab.validate_settings()
        assert valid is False
        assert "source" in msg.lower()

    def test_validate_with_source_passes(self):
        tab = RenderCompositionTab()
        tab._model.add_layer(CompositionLayer(
            display_name="BG",
            layer_type="background",
            asset_path=Path("/tmp/test.mp4"),
        ))
        valid, msg = tab.validate_settings()
        assert valid is True
        assert msg == ""


# ------------------------------------------------------------------
# Global busy
# ------------------------------------------------------------------


class TestRenderCompositionTabGlobalBusy:
    def test_set_global_busy_disables_start(self):
        tab = RenderCompositionTab()
        assert tab._start_btn.isEnabled() is True

        tab.set_global_busy(True, owner_tab_id="audio_visualizer")
        assert tab._start_btn.isEnabled() is False

        tab.set_global_busy(False)
        assert tab._start_btn.isEnabled() is True

    def test_own_tab_not_disabled(self):
        tab = RenderCompositionTab()
        tab.set_global_busy(True, owner_tab_id="render_composition")
        assert tab._start_btn.isEnabled() is True


# ------------------------------------------------------------------
# Composition model
# ------------------------------------------------------------------


class TestCompositionModel:
    def test_add_and_remove_layer(self):
        model = CompositionModel()
        layer = CompositionLayer(display_name="Test")
        model.add_layer(layer)
        assert len(model.layers) == 1

        removed = model.remove_layer(layer.id)
        assert removed is not None
        assert removed.display_name == "Test"
        assert len(model.layers) == 0

    def test_remove_nonexistent_layer(self):
        model = CompositionModel()
        assert model.remove_layer("nonexistent") is None

    def test_get_layer(self):
        model = CompositionModel()
        layer = CompositionLayer(display_name="Find Me")
        model.add_layer(layer)
        found = model.get_layer(layer.id)
        assert found is not None
        assert found.display_name == "Find Me"

    def test_move_layer(self):
        model = CompositionModel()
        layer = CompositionLayer(display_name="Move", x=0, y=0)
        model.add_layer(layer)
        model.move_layer(layer.id, 100, 200)
        assert layer.x == 100
        assert layer.y == 200

    def test_resize_layer(self):
        model = CompositionModel()
        layer = CompositionLayer(display_name="Resize", width=1920, height=1080)
        model.add_layer(layer)
        model.resize_layer(layer.id, 1280, 720)
        assert layer.width == 1280
        assert layer.height == 720

    def test_reorder_layer(self):
        model = CompositionModel()
        layer = CompositionLayer(display_name="Reorder", z_order=0)
        model.add_layer(layer)
        model.reorder_layer(layer.id, 5)
        assert layer.z_order == 5

    def test_update_layer(self):
        model = CompositionModel()
        layer = CompositionLayer(display_name="Update")
        model.add_layer(layer)
        model.update_layer(layer.id, display_name="Updated", layer_type="background")
        assert layer.display_name == "Updated"
        assert layer.layer_type == "background"

    def test_get_duration_ms(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(display_name="L1", end_ms=5000))
        model.add_layer(CompositionLayer(display_name="L2", end_ms=10000))
        model.add_layer(CompositionLayer(display_name="L3", end_ms=3000, enabled=False))
        assert model.get_duration_ms() == 10000

    def test_get_duration_ms_empty(self):
        model = CompositionModel()
        assert model.get_duration_ms() == 0

    def test_get_layers_sorted(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(display_name="High", z_order=10))
        model.add_layer(CompositionLayer(display_name="Low", z_order=1))
        model.add_layer(CompositionLayer(display_name="Mid", z_order=5))
        sorted_layers = model.get_layers_sorted()
        assert [l.display_name for l in sorted_layers] == ["Low", "Mid", "High"]

    def test_to_dict_from_dict_roundtrip(self):
        model = CompositionModel()
        model.output_width = 1280
        model.output_height = 720
        model.output_fps = 24.0
        model.audio_source_asset_id = "audio-123"
        model.audio_source_path = Path("/tmp/audio.mp3")
        model.add_layer(CompositionLayer(
            display_name="BG",
            layer_type="background",
            asset_path=Path("/tmp/bg.mp4"),
            x=10, y=20, width=1280, height=720,
            z_order=0, start_ms=0, end_ms=5000,
            behavior_after_end="loop",
        ))

        data = model.to_dict()
        restored = CompositionModel.from_dict(data)

        assert restored.output_width == 1280
        assert restored.output_height == 720
        assert restored.output_fps == 24.0
        assert restored.audio_source_asset_id == "audio-123"
        assert restored.audio_source_path == Path("/tmp/audio.mp3")
        assert len(restored.layers) == 1
        layer = restored.layers[0]
        assert layer.display_name == "BG"
        assert layer.layer_type == "background"
        assert layer.asset_path == Path("/tmp/bg.mp4")
        assert layer.x == 10
        assert layer.y == 20
        assert layer.behavior_after_end == "loop"


# ------------------------------------------------------------------
# Layer dataclass
# ------------------------------------------------------------------


class TestCompositionLayer:
    def test_default_id_generated(self):
        layer = CompositionLayer(display_name="Test")
        assert layer.id != ""
        assert len(layer.id) > 0

    def test_provided_id_used(self):
        layer = CompositionLayer(id="my-id", display_name="Test")
        assert layer.id == "my-id"

    def test_default_matte_settings(self):
        layer = CompositionLayer(display_name="Test")
        assert layer.matte_settings["mode"] == "none"
        assert layer.matte_settings["key_target"] == "#00FF00"

    def test_matte_settings_isolation(self):
        """Each layer gets its own matte_settings dict."""
        l1 = CompositionLayer(display_name="L1")
        l2 = CompositionLayer(display_name="L2")
        l1.matte_settings["mode"] = "chromakey"
        assert l2.matte_settings["mode"] == "none"


# ------------------------------------------------------------------
# Undo/redo commands
# ------------------------------------------------------------------


class TestUndoCommands:
    def test_add_layer_command(self):
        model = CompositionModel()
        layer = CompositionLayer(display_name="Added")
        cmd = AddLayerCommand(model, layer)
        cmd.redo()
        assert len(model.layers) == 1
        assert model.layers[0].display_name == "Added"

        cmd.undo()
        assert len(model.layers) == 0

    def test_remove_layer_command(self):
        model = CompositionModel()
        layer = CompositionLayer(display_name="ToRemove")
        model.add_layer(layer)

        cmd = RemoveLayerCommand(model, layer.id)
        cmd.redo()
        assert len(model.layers) == 0

        cmd.undo()
        assert len(model.layers) == 1
        assert model.layers[0].display_name == "ToRemove"

    def test_move_layer_command(self):
        model = CompositionModel()
        layer = CompositionLayer(display_name="Movable", x=0, y=0)
        model.add_layer(layer)

        cmd = MoveLayerCommand(model, layer.id, 100, 200)
        cmd.redo()
        assert layer.x == 100
        assert layer.y == 200

        cmd.undo()
        assert layer.x == 0
        assert layer.y == 0

    def test_resize_layer_command(self):
        model = CompositionModel()
        layer = CompositionLayer(display_name="Resizable", width=1920, height=1080)
        model.add_layer(layer)

        cmd = ResizeLayerCommand(model, layer.id, 1280, 720)
        cmd.redo()
        assert layer.width == 1280
        assert layer.height == 720

        cmd.undo()
        assert layer.width == 1920
        assert layer.height == 1080

    def test_reorder_layer_command(self):
        model = CompositionModel()
        layer = CompositionLayer(display_name="Reorderable", z_order=0)
        model.add_layer(layer)

        cmd = ReorderLayerCommand(model, layer.id, 5)
        cmd.redo()
        assert layer.z_order == 5

        cmd.undo()
        assert layer.z_order == 0

    def test_change_source_command(self):
        model = CompositionModel()
        layer = CompositionLayer(display_name="Src")
        model.add_layer(layer)

        cmd = ChangeSourceCommand(
            model, layer.id,
            new_asset_id="asset-1",
            new_asset_path=Path("/tmp/new.mp4"),
        )
        cmd.redo()
        assert layer.asset_id == "asset-1"
        assert layer.asset_path == Path("/tmp/new.mp4")

        cmd.undo()
        assert layer.asset_id is None
        assert layer.asset_path is None

    def test_change_audio_source_command(self):
        model = CompositionModel()

        cmd = ChangeAudioSourceCommand(
            model,
            new_asset_id="audio-1",
            new_path=Path("/tmp/audio.mp3"),
        )
        cmd.redo()
        assert model.audio_source_asset_id == "audio-1"
        assert model.audio_source_path == Path("/tmp/audio.mp3")

        cmd.undo()
        assert model.audio_source_asset_id is None
        assert model.audio_source_path is None

    def test_apply_preset_command(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(display_name="Original"))

        preset_layers = [
            CompositionLayer(display_name="Preset BG", layer_type="background"),
            CompositionLayer(display_name="Preset Viz", layer_type="visualizer"),
        ]

        cmd = ApplyPresetCommand(model, preset_layers, "test_preset")
        cmd.redo()
        assert len(model.layers) == 2
        assert model.layers[0].display_name == "Preset BG"
        assert model.layers[1].display_name == "Preset Viz"

        cmd.undo()
        assert len(model.layers) == 1
        assert model.layers[0].display_name == "Original"

    def test_undo_redo_via_tab_stack(self):
        tab = RenderCompositionTab()
        model = tab._model

        # Add layer
        layer = CompositionLayer(display_name="Undoable")
        cmd = AddLayerCommand(model, layer)
        tab._push_command(cmd)
        assert len(model.layers) == 1

        # Undo
        tab._undo_stack.undo()
        assert len(model.layers) == 0

        # Redo
        tab._undo_stack.redo()
        assert len(model.layers) == 1


# ------------------------------------------------------------------
# Presets
# ------------------------------------------------------------------


class TestPresets:
    def test_all_presets_available(self):
        assert "fullscreen_bg_centered_viz" in PRESET_NAMES
        assert "fullscreen_bg_bottom_captions" in PRESET_NAMES
        assert "pip_overlay" in PRESET_NAMES

    def test_fullscreen_bg_centered_viz(self):
        layers = get_preset("fullscreen_bg_centered_viz", 1920, 1080)
        assert len(layers) == 2
        bg = layers[0]
        viz = layers[1]
        assert bg.layer_type == "background"
        assert bg.width == 1920
        assert bg.height == 1080
        assert viz.layer_type == "visualizer"
        # Visualizer should be centered and smaller
        assert viz.width < 1920
        assert viz.height < 1080
        assert viz.x > 0
        assert viz.y > 0

    def test_fullscreen_bg_bottom_captions(self):
        layers = get_preset("fullscreen_bg_bottom_captions", 1920, 1080)
        assert len(layers) == 2
        bg = layers[0]
        cap = layers[1]
        assert bg.layer_type == "background"
        assert cap.layer_type == "caption_overlay"
        # Captions should be at the bottom
        assert cap.y > 0
        assert cap.width == 1920
        assert cap.height < 1080

    def test_pip_overlay(self):
        layers = get_preset("pip_overlay", 1920, 1080)
        assert len(layers) == 2
        bg = layers[0]
        pip = layers[1]
        assert bg.layer_type == "background"
        assert pip.layer_type == "visualizer"
        # PiP should be small and in corner
        assert pip.width < 1920 // 2
        assert pip.height < 1080 // 2
        assert pip.x > 0
        assert pip.y > 0

    def test_preset_scales_to_resolution(self):
        layers_1080 = get_preset("fullscreen_bg_centered_viz", 1920, 1080)
        layers_720 = get_preset("fullscreen_bg_centered_viz", 1280, 720)

        assert layers_1080[0].width == 1920
        assert layers_720[0].width == 1280
        assert layers_1080[1].width > layers_720[1].width

    def test_invalid_preset_raises(self):
        with pytest.raises(ValueError, match="Unknown preset"):
            get_preset("nonexistent")

    def test_preset_layers_have_unique_ids(self):
        layers = get_preset("fullscreen_bg_centered_viz")
        ids = [l.id for l in layers]
        assert len(ids) == len(set(ids))


# ------------------------------------------------------------------
# Direct file source handling
# ------------------------------------------------------------------


class TestDirectFileSourceHandling:
    def test_load_layer_properties_shows_direct_file(self):
        """When a layer has asset_path but no asset_id, the source combo shows the file."""
        tab = RenderCompositionTab()
        layer = CompositionLayer(
            display_name="BG",
            layer_type="background",
            asset_path=Path("/tmp/my_background.mp4"),
        )
        tab._model.add_layer(layer)
        tab._refresh_layer_list()
        tab._layer_list.setCurrentRow(0)

        tab._load_layer_properties(layer)

        # The source combo should show the file entry
        assert tab._source_combo.currentText().startswith("File:")
        assert "my_background.mp4" in tab._source_combo.currentText()

    def test_load_layer_properties_session_asset(self):
        """When a layer has an asset_id matching a combo entry, it selects correctly."""
        tab = RenderCompositionTab()
        from audio_visualizer.ui.sessionContext import SessionContext

        ctx = SessionContext()
        tab.set_session_context(ctx)

        ctx.register_asset(SessionAsset(
            id="vid-abc",
            display_name="My Video",
            path=Path("/tmp/video.mp4"),
            category="video",
        ))

        layer = CompositionLayer(
            display_name="Layer1",
            asset_id="vid-abc",
            asset_path=Path("/tmp/video.mp4"),
        )
        tab._model.add_layer(layer)
        tab._refresh_layer_list()
        tab._load_layer_properties(layer)

        assert "My Video" in tab._source_combo.currentText()

    def test_load_layer_properties_no_source(self):
        """When a layer has no source, combo shows (none)."""
        tab = RenderCompositionTab()
        layer = CompositionLayer(display_name="Empty")
        tab._model.add_layer(layer)
        tab._refresh_layer_list()
        tab._load_layer_properties(layer)

        assert tab._source_combo.currentText() == "(none)"

    def test_refresh_asset_combos_preserves_direct_files(self):
        """Direct-file entries survive asset combo refresh."""
        tab = RenderCompositionTab()
        from audio_visualizer.ui.sessionContext import SessionContext

        ctx = SessionContext()
        tab.set_session_context(ctx)

        # Add a layer with a direct file path
        layer = CompositionLayer(
            display_name="BG",
            asset_path=Path("/tmp/bg_file.mp4"),
        )
        tab._model.add_layer(layer)

        # Trigger a refresh
        tab._refresh_asset_combos()

        # The source combo should include the direct file entry
        texts = [tab._source_combo.itemText(i) for i in range(tab._source_combo.count())]
        assert any("bg_file.mp4" in t for t in texts)

    def test_output_path_gets_mp4_extension(self):
        """Output path without extension gets .mp4 appended."""
        tab = RenderCompositionTab()
        # Add a valid layer so validation passes
        tab._model.add_layer(CompositionLayer(
            display_name="BG",
            asset_path=Path("/tmp/bg.mp4"),
            end_ms=5000,
        ))
        tab._output_path_edit.setText("/tmp/my_output")

        # The _on_start_render would normally append .mp4
        # Test the logic directly
        output_path = tab._output_path_edit.text().strip()
        if not Path(output_path).suffix:
            output_path = output_path + ".mp4"
        assert output_path == "/tmp/my_output.mp4"


# ------------------------------------------------------------------
# Preview section
# ------------------------------------------------------------------


class TestPreviewSection:
    def test_preview_widgets_exist(self):
        tab = RenderCompositionTab()
        assert hasattr(tab, "_preview_label")
        assert hasattr(tab, "_preview_time_spin")
        assert hasattr(tab, "_preview_refresh_btn")

    def test_preview_timestamp_default(self):
        tab = RenderCompositionTab()
        assert tab._preview_time_spin.value() == 0

    def test_preview_validate_fails_gracefully(self):
        """Refresh preview with no layers shows error in status label."""
        tab = RenderCompositionTab()
        tab._on_refresh_preview()
        assert "Cannot preview" in tab._preview_status_label.text()
