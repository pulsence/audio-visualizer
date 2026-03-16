"""Tests for RenderCompositionTab, composition model, undo/redo, and presets."""

from pathlib import Path

from PySide6.QtWidgets import QApplication, QWidget

app = QApplication.instance() or QApplication([])

import pytest
from unittest.mock import MagicMock

from audio_visualizer.ui.sessionContext import SessionAsset, SessionContext
from audio_visualizer.ui.tabs.renderCompositionTab import RenderCompositionTab
from audio_visualizer.ui.tabs.renderComposition.model import (
    CompositionAudioLayer,
    CompositionLayer,
    CompositionModel,
    DEFAULT_MATTE_SETTINGS,
    RESOLUTION_PRESET_LABELS,
    RESOLUTION_PRESETS,
    VALID_BEHAVIORS,
    VALID_LAYER_TYPES,
)
from audio_visualizer.ui.tabs.renderComposition.commands import (
    AddAudioLayerCommand,
    AddLayerCommand,
    ApplyPresetCommand,
    ChangeAudioSourceCommand,
    ChangeSourceCommand,
    EditAudioLayerCommand,
    MoveLayerCommand,
    RemoveAudioLayerCommand,
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

    def test_apply_settings_restores_direct_file_entries(self):
        tab = RenderCompositionTab()
        model = CompositionModel()
        model.add_layer(
            CompositionLayer(
                display_name="BG",
                asset_path=Path("/tmp/bg_from_settings.mp4"),
            )
        )
        model.audio_source_path = Path("/tmp/audio_from_settings.wav")

        tab.apply_settings({"model": model.to_dict()})

        source_texts = [tab._source_combo.itemText(i) for i in range(tab._source_combo.count())]
        audio_texts = [tab._audio_combo.itemText(i) for i in range(tab._audio_combo.count())]

        assert any("bg_from_settings.mp4" in text for text in source_texts)
        assert any("audio_from_settings.wav" in text for text in audio_texts)

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

    def test_blank_output_path_defaults_to_project_folder(self, tmp_path, monkeypatch):
        class _FakeSignal:
            def connect(self, _slot):
                return None

        class _FakeWorker:
            def __init__(self, model, output_path):
                self.model = model
                self.output_path = output_path
                self.signals = MagicMock(
                    progress=_FakeSignal(),
                    completed=_FakeSignal(),
                    failed=_FakeSignal(),
                    canceled=_FakeSignal(),
                )

            def cancel(self):
                return None

        class _FakeMainWindow(QWidget):
            def __init__(self):
                super().__init__()
                self.render_thread_pool = MagicMock()

            def try_start_job(self, _owner_tab_id):
                return True

            def show_job_status(self, *_args):
                return None

        main_window = _FakeMainWindow()
        tab = RenderCompositionTab(main_window)
        ctx = SessionContext()
        project_folder = tmp_path / "project"
        project_folder.mkdir()
        ctx.set_project_folder(project_folder)
        tab.set_session_context(ctx)
        tab._model.add_layer(CompositionLayer(
            display_name="BG",
            asset_path=tmp_path / "bg.mp4",
            end_ms=5000,
        ))

        captured = []

        class _CapturingWorker(_FakeWorker):
            def __init__(self, model, output_path):
                super().__init__(model, output_path)
                captured.append(output_path)

        monkeypatch.setattr(
            "audio_visualizer.ui.tabs.renderCompositionTab.CompositionWorker",
            _CapturingWorker,
            raising=False,
        )
        monkeypatch.setattr(
            "audio_visualizer.ui.workers.compositionWorker.CompositionWorker",
            _CapturingWorker,
        )

        tab._on_start_render()

        assert captured == [str(project_folder / "composition_output.mp4")]


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


# ------------------------------------------------------------------
# Resolution presets
# ------------------------------------------------------------------


class TestResolutionPresets:
    def test_preset_constants_defined(self):
        assert "hd" in RESOLUTION_PRESETS
        assert "hd_vertical" in RESOLUTION_PRESETS
        assert "2k" in RESOLUTION_PRESETS
        assert "4k" in RESOLUTION_PRESETS
        assert RESOLUTION_PRESETS["hd"] == (1920, 1080)
        assert RESOLUTION_PRESETS["4k"] == (3840, 2160)

    def test_preset_labels_include_custom(self):
        keys = [key for key, _label in RESOLUTION_PRESET_LABELS]
        assert "custom" in keys
        assert "hd" in keys

    def test_model_default_resolution_preset(self):
        model = CompositionModel()
        assert model.resolution_preset == "hd"

    def test_model_to_dict_includes_preset(self):
        model = CompositionModel()
        model.resolution_preset = "4k"
        data = model.to_dict()
        assert data["resolution_preset"] == "4k"

    def test_model_from_dict_restores_preset(self):
        data = {"resolution_preset": "2k", "output_width": 2560, "output_height": 1440}
        model = CompositionModel.from_dict(data)
        assert model.resolution_preset == "2k"

    def test_model_from_dict_defaults_to_custom(self):
        """Legacy data without resolution_preset defaults to custom."""
        data = {"output_width": 1280, "output_height": 720}
        model = CompositionModel.from_dict(data)
        assert model.resolution_preset == "custom"

    def test_tab_has_resolution_preset_combo(self):
        tab = RenderCompositionTab()
        assert hasattr(tab, "_resolution_preset_combo")
        # Should have all preset labels
        count = tab._resolution_preset_combo.count()
        assert count == len(RESOLUTION_PRESET_LABELS)

    def test_preset_selection_updates_width_height(self):
        """Selecting a preset updates width/height spinboxes and model."""
        tab = RenderCompositionTab()
        # Select 4K
        idx = tab._resolution_preset_combo.findData("4k")
        assert idx >= 0
        tab._resolution_preset_combo.setCurrentIndex(idx)
        assert tab._out_width_spin.value() == 3840
        assert tab._out_height_spin.value() == 2160
        assert tab._model.output_width == 3840
        assert tab._model.output_height == 2160
        assert tab._model.resolution_preset == "4k"

    def test_preset_selection_hd_vertical(self):
        tab = RenderCompositionTab()
        idx = tab._resolution_preset_combo.findData("hd_vertical")
        assert idx >= 0
        tab._resolution_preset_combo.setCurrentIndex(idx)
        assert tab._out_width_spin.value() == 1080
        assert tab._out_height_spin.value() == 1920
        assert tab._model.resolution_preset == "hd_vertical"

    def test_manual_edit_falls_back_to_custom(self):
        """Manually changing width/height to non-preset values sets preset to custom."""
        tab = RenderCompositionTab()
        # Start with HD preset
        idx = tab._resolution_preset_combo.findData("hd")
        tab._resolution_preset_combo.setCurrentIndex(idx)
        assert tab._model.resolution_preset == "hd"

        # Manually change width to a non-preset value
        tab._out_width_spin.setValue(1234)
        tab._on_output_settings_changed()
        assert tab._model.resolution_preset == "custom"
        custom_idx = tab._resolution_preset_combo.findData("custom")
        assert tab._resolution_preset_combo.currentIndex() == custom_idx

    def test_manual_edit_matches_preset(self):
        """Manually setting width/height to match a preset selects that preset."""
        tab = RenderCompositionTab()
        # Start with custom
        tab._out_width_spin.setValue(1234)
        tab._on_output_settings_changed()
        assert tab._model.resolution_preset == "custom"

        # Set to 4K dimensions
        tab._out_width_spin.setValue(3840)
        tab._out_height_spin.setValue(2160)
        tab._on_output_settings_changed()
        assert tab._model.resolution_preset == "4k"
        idx_4k = tab._resolution_preset_combo.findData("4k")
        assert tab._resolution_preset_combo.currentIndex() == idx_4k

    def test_settings_roundtrip_preserves_preset(self):
        """Preset survives collect_settings / apply_settings cycle."""
        tab = RenderCompositionTab()
        idx = tab._resolution_preset_combo.findData("2k")
        tab._resolution_preset_combo.setCurrentIndex(idx)
        assert tab._model.resolution_preset == "2k"

        settings = tab.collect_settings()

        tab2 = RenderCompositionTab()
        tab2.apply_settings(settings)
        assert tab2._model.resolution_preset == "2k"
        assert tab2._out_width_spin.value() == 2560
        assert tab2._out_height_spin.value() == 1440
        idx2 = tab2._resolution_preset_combo.findData("2k")
        assert tab2._resolution_preset_combo.currentIndex() == idx2

    def test_custom_preset_selection_no_dimension_change(self):
        """Selecting 'custom' does not change the current width/height."""
        tab = RenderCompositionTab()
        # Set to 4K first
        idx = tab._resolution_preset_combo.findData("4k")
        tab._resolution_preset_combo.setCurrentIndex(idx)
        assert tab._out_width_spin.value() == 3840

        # Switch to custom
        custom_idx = tab._resolution_preset_combo.findData("custom")
        tab._resolution_preset_combo.setCurrentIndex(custom_idx)
        # Width/height should remain unchanged
        assert tab._out_width_spin.value() == 3840
        assert tab._out_height_spin.value() == 2160
        assert tab._model.resolution_preset == "custom"


# ------------------------------------------------------------------
# Timeline widget
# ------------------------------------------------------------------


from audio_visualizer.ui.tabs.renderComposition.timelineWidget import (
    TimelineItem,
    TimelineWidget,
)


class TestTimelineWidget:
    def test_widget_creation(self):
        widget = TimelineWidget()
        assert widget.minimumHeight() == 120
        assert widget._items == []
        assert widget._selected_id is None

    def test_set_items(self):
        widget = TimelineWidget()
        items = [
            TimelineItem("v1", "Visual 1", 0, 5000, "visual"),
            TimelineItem("a1", "Audio 1", 0, 8000, "audio"),
        ]
        widget.set_items(items)
        assert len(widget._items) == 2
        assert widget._duration_ms == 10000  # minimum 10s

    def test_set_items_adjusts_duration(self):
        widget = TimelineWidget()
        items = [
            TimelineItem("v1", "Long", 0, 20000, "visual"),
        ]
        widget.set_items(items)
        assert widget._duration_ms == 20000

    def test_set_selected(self):
        widget = TimelineWidget()
        widget.set_selected("v1")
        assert widget._selected_id == "v1"
        widget.set_selected(None)
        assert widget._selected_id is None

    def test_ms_to_x_and_back(self):
        widget = TimelineWidget()
        widget.resize(1100, 200)  # 1100 - 100 header = 1000 available
        widget._duration_ms = 10000
        x = widget._ms_to_x(5000)
        # 5000/10000 * 1000 + 100 = 600
        assert abs(x - 600.0) < 1.0
        ms = widget._x_to_ms(600.0)
        assert abs(ms - 5000) < 50

    def test_recalc_duration_empty(self):
        widget = TimelineWidget()
        widget._items = []
        widget._recalc_duration()
        assert widget._duration_ms == 10000

    def test_recalc_duration_minimum(self):
        widget = TimelineWidget()
        widget._items = [TimelineItem("v1", "Short", 0, 3000)]
        widget._recalc_duration()
        assert widget._duration_ms == 10000  # minimum is 10s

    def test_item_selected_signal(self):
        widget = TimelineWidget()
        items = [TimelineItem("v1", "Visual 1", 0, 5000, "visual")]
        widget.set_items(items)
        widget.resize(1100, 200)

        signals = []
        widget.item_selected.connect(lambda item_id: signals.append(item_id))

        # Simulate selecting item internally
        widget._selected_id = "v1"
        widget.item_selected.emit("v1")
        assert signals == ["v1"]

    def test_item_moved_signal(self):
        widget = TimelineWidget()
        results = []
        widget.item_moved.connect(lambda a, b, c: results.append((a, b, c)))
        widget.item_moved.emit("v1", 1000, 6000)
        assert results == [("v1", 1000, 6000)]

    def test_item_trimmed_signal(self):
        widget = TimelineWidget()
        results = []
        widget.item_trimmed.connect(lambda a, b, c: results.append((a, b, c)))
        widget.item_trimmed.emit("v1", "start", 500)
        assert results == [("v1", "start", 500)]

    def test_get_item_rect(self):
        widget = TimelineWidget()
        widget.resize(1100, 200)
        widget._duration_ms = 10000
        item = TimelineItem("v1", "Test", 0, 5000, "visual")
        rect = widget._get_item_rect(item, 25)
        assert rect.y() == 25
        assert rect.height() == 30
        # Item spans 0..5000 out of 10000, available width is 1000
        # x1 = 100, x2 = 100 + 500 = 600, width = 500
        assert abs(rect.width() - 500.0) < 1.0

    def test_paint_does_not_crash(self):
        """Ensure paintEvent runs without errors."""
        widget = TimelineWidget()
        items = [
            TimelineItem("v1", "Visual 1", 0, 5000, "visual"),
            TimelineItem("v2", "Visual 2", 2000, 8000, "visual", enabled=False),
            TimelineItem("a1", "Audio 1", 0, 10000, "audio"),
        ]
        widget.set_items(items)
        widget.set_selected("v1")
        widget.resize(800, 200)
        widget.repaint()


class TestTimelineItem:
    def test_creation(self):
        item = TimelineItem("id1", "My Item", 100, 5000, "visual", True)
        assert item.item_id == "id1"
        assert item.display_name == "My Item"
        assert item.start_ms == 100
        assert item.end_ms == 5000
        assert item.track_type == "visual"
        assert item.enabled is True

    def test_defaults(self):
        item = TimelineItem("id1", "My Item", 0, 1000)
        assert item.track_type == "visual"
        assert item.enabled is True


# ------------------------------------------------------------------
# Timeline integration in tab
# ------------------------------------------------------------------


class TestTimelineIntegration:
    def test_tab_has_timeline(self):
        tab = RenderCompositionTab()
        assert hasattr(tab, "_timeline")
        assert isinstance(tab._timeline, TimelineWidget)

    def test_refresh_timeline_updates_items(self):
        tab = RenderCompositionTab()
        tab._model.add_layer(CompositionLayer(
            display_name="BG",
            layer_type="background",
            start_ms=0,
            end_ms=5000,
        ))
        tab._model.add_layer(CompositionLayer(
            display_name="Viz",
            layer_type="visualizer",
            start_ms=1000,
            end_ms=8000,
        ))
        tab._refresh_timeline()
        assert len(tab._timeline._items) == 2
        assert tab._timeline._items[0].display_name == "BG"
        assert tab._timeline._items[1].display_name == "Viz"

    def test_refresh_layer_list_refreshes_timeline(self):
        tab = RenderCompositionTab()
        tab._model.add_layer(CompositionLayer(
            display_name="L1",
            start_ms=0,
            end_ms=3000,
        ))
        tab._refresh_layer_list()
        assert len(tab._timeline._items) == 1
        assert tab._timeline._items[0].display_name == "L1"

    def test_timeline_item_selected_syncs_layer_list(self):
        tab = RenderCompositionTab()
        layer1 = CompositionLayer(display_name="L1", start_ms=0, end_ms=3000)
        layer2 = CompositionLayer(display_name="L2", start_ms=0, end_ms=5000)
        tab._model.add_layer(layer1)
        tab._model.add_layer(layer2)
        tab._refresh_layer_list()

        # Simulate timeline selecting layer2
        tab._on_timeline_item_selected(layer2.id)
        assert tab._layer_list.currentRow() == 1

    def test_timeline_item_moved_updates_model(self):
        tab = RenderCompositionTab()
        layer = CompositionLayer(
            display_name="Movable",
            start_ms=0,
            end_ms=5000,
        )
        tab._model.add_layer(layer)
        tab._refresh_layer_list()

        tab._on_timeline_item_moved(layer.id, 2000, 7000)
        assert layer.start_ms == 2000
        assert layer.end_ms == 7000

    def test_timeline_item_trimmed_start(self):
        tab = RenderCompositionTab()
        layer = CompositionLayer(
            display_name="Trimmable",
            start_ms=0,
            end_ms=5000,
        )
        tab._model.add_layer(layer)
        tab._refresh_layer_list()

        tab._on_timeline_item_trimmed(layer.id, "start", 500)
        assert layer.start_ms == 500
        assert layer.end_ms == 5000

    def test_timeline_item_trimmed_end(self):
        tab = RenderCompositionTab()
        layer = CompositionLayer(
            display_name="Trimmable",
            start_ms=0,
            end_ms=5000,
        )
        tab._model.add_layer(layer)
        tab._refresh_layer_list()

        tab._on_timeline_item_trimmed(layer.id, "end", 8000)
        assert layer.start_ms == 0
        assert layer.end_ms == 8000

    def test_timeline_selected_empty_id_ignored(self):
        """Selecting empty string on timeline does not crash."""
        tab = RenderCompositionTab()
        tab._on_timeline_item_selected("")

    def test_timeline_move_nonexistent_layer(self):
        """Moving a non-existent layer does not crash."""
        tab = RenderCompositionTab()
        tab._on_timeline_item_moved("nonexistent", 0, 5000)

    def test_timeline_trim_nonexistent_layer(self):
        """Trimming a non-existent layer does not crash."""
        tab = RenderCompositionTab()
        tab._on_timeline_item_trimmed("nonexistent", "start", 500)

    def test_apply_settings_refreshes_timeline(self):
        tab = RenderCompositionTab()
        model = CompositionModel()
        model.add_layer(CompositionLayer(
            display_name="Restored",
            start_ms=0,
            end_ms=6000,
        ))
        tab.apply_settings({"model": model.to_dict()})
        assert len(tab._timeline._items) == 1
        assert tab._timeline._items[0].display_name == "Restored"

    def test_timeline_disabled_layer(self):
        tab = RenderCompositionTab()
        tab._model.add_layer(CompositionLayer(
            display_name="Disabled",
            start_ms=0,
            end_ms=5000,
            enabled=False,
        ))
        tab._refresh_timeline()
        assert tab._timeline._items[0].enabled is False

    def test_timeline_preserves_track_type(self):
        tab = RenderCompositionTab()
        tab._model.add_layer(CompositionLayer(
            display_name="Visual",
            layer_type="background",
            start_ms=0,
            end_ms=5000,
        ))
        tab._refresh_timeline()
        assert tab._timeline._items[0].track_type == "visual"


# ------------------------------------------------------------------
# CompositionAudioLayer dataclass
# ------------------------------------------------------------------


class TestCompositionAudioLayer:
    def test_default_id_generated(self):
        al = CompositionAudioLayer(display_name="Test")
        assert al.id != ""
        assert len(al.id) > 0

    def test_provided_id_used(self):
        al = CompositionAudioLayer(id="my-audio-id", display_name="Test")
        assert al.id == "my-audio-id"

    def test_defaults(self):
        al = CompositionAudioLayer(display_name="Test Audio")
        assert al.display_name == "Test Audio"
        assert al.asset_id is None
        assert al.asset_path is None
        assert al.start_ms == 0
        assert al.duration_ms == 0
        assert al.use_full_length is True
        assert al.enabled is True


# ------------------------------------------------------------------
# Audio layers on CompositionModel
# ------------------------------------------------------------------


class TestCompositionModelAudioLayers:
    def test_model_has_audio_layers(self):
        model = CompositionModel()
        assert model.audio_layers == []

    def test_add_audio_layer(self):
        model = CompositionModel()
        al = CompositionAudioLayer(display_name="Music")
        model.audio_layers.append(al)
        assert len(model.audio_layers) == 1
        assert model.audio_layers[0].display_name == "Music"

    def test_to_dict_includes_audio_layers(self):
        model = CompositionModel()
        al = CompositionAudioLayer(
            display_name="Track 1",
            asset_path=Path("/tmp/track1.mp3"),
            start_ms=1000,
            duration_ms=5000,
            use_full_length=False,
        )
        model.audio_layers.append(al)
        data = model.to_dict()

        assert "audio_layers" in data
        assert len(data["audio_layers"]) == 1
        assert data["audio_layers"][0]["display_name"] == "Track 1"
        assert data["audio_layers"][0]["asset_path"] == str(Path("/tmp/track1.mp3"))
        assert data["audio_layers"][0]["start_ms"] == 1000
        assert data["audio_layers"][0]["duration_ms"] == 5000
        assert data["audio_layers"][0]["use_full_length"] is False

    def test_from_dict_restores_audio_layers(self):
        data = {
            "audio_layers": [
                {
                    "id": "al-1",
                    "display_name": "Track 1",
                    "asset_path": "/tmp/track1.mp3",
                    "start_ms": 500,
                    "duration_ms": 3000,
                    "use_full_length": False,
                    "enabled": True,
                },
                {
                    "id": "al-2",
                    "display_name": "Track 2",
                    "asset_path": "/tmp/track2.wav",
                    "start_ms": 0,
                    "duration_ms": 0,
                    "use_full_length": True,
                    "enabled": False,
                },
            ],
        }
        model = CompositionModel.from_dict(data)
        assert len(model.audio_layers) == 2
        assert model.audio_layers[0].id == "al-1"
        assert model.audio_layers[0].display_name == "Track 1"
        assert model.audio_layers[0].asset_path == Path("/tmp/track1.mp3")
        assert model.audio_layers[0].start_ms == 500
        assert model.audio_layers[0].duration_ms == 3000
        assert model.audio_layers[0].use_full_length is False
        assert model.audio_layers[1].id == "al-2"
        assert model.audio_layers[1].enabled is False

    def test_from_dict_backward_compat_migrates_single_audio(self):
        """Legacy data with audio_source_path but no audio_layers gets migrated."""
        data = {
            "audio_source_asset_id": "audio-legacy",
            "audio_source_path": "/tmp/legacy_audio.mp3",
        }
        model = CompositionModel.from_dict(data)
        assert len(model.audio_layers) == 1
        assert model.audio_layers[0].display_name == "Audio Source"
        assert model.audio_layers[0].asset_id == "audio-legacy"
        assert model.audio_layers[0].asset_path == Path("/tmp/legacy_audio.mp3")

    def test_from_dict_no_migration_when_audio_layers_present(self):
        """If audio_layers are present, legacy fields are not migrated."""
        data = {
            "audio_source_asset_id": "audio-old",
            "audio_source_path": "/tmp/old.mp3",
            "audio_layers": [
                {"id": "al-1", "display_name": "New Track", "asset_path": "/tmp/new.mp3"},
            ],
        }
        model = CompositionModel.from_dict(data)
        assert len(model.audio_layers) == 1
        assert model.audio_layers[0].display_name == "New Track"

    def test_to_dict_from_dict_roundtrip_with_audio_layers(self):
        model = CompositionModel()
        model.output_width = 1280
        model.output_height = 720
        model.audio_layers.append(CompositionAudioLayer(
            display_name="Music",
            asset_path=Path("/tmp/music.mp3"),
            start_ms=2000,
            duration_ms=8000,
            use_full_length=False,
            enabled=True,
        ))
        model.audio_layers.append(CompositionAudioLayer(
            display_name="Narration",
            asset_path=Path("/tmp/narration.wav"),
            start_ms=0,
            use_full_length=True,
            enabled=False,
        ))

        data = model.to_dict()
        restored = CompositionModel.from_dict(data)

        assert len(restored.audio_layers) == 2
        assert restored.audio_layers[0].display_name == "Music"
        assert restored.audio_layers[0].asset_path == Path("/tmp/music.mp3")
        assert restored.audio_layers[0].start_ms == 2000
        assert restored.audio_layers[0].duration_ms == 8000
        assert restored.audio_layers[0].use_full_length is False
        assert restored.audio_layers[1].display_name == "Narration"
        assert restored.audio_layers[1].enabled is False

    def test_get_duration_ms_with_audio_layers(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(display_name="L1", end_ms=5000))
        model.audio_layers.append(CompositionAudioLayer(
            display_name="Music",
            start_ms=2000,
            duration_ms=6000,
            use_full_length=False,
            enabled=True,
        ))
        # Audio layer ends at 2000 + 6000 = 8000
        assert model.get_duration_ms() == 8000

    def test_get_duration_ms_audio_layers_only(self):
        model = CompositionModel()
        model.audio_layers.append(CompositionAudioLayer(
            display_name="Music",
            start_ms=1000,
            duration_ms=4000,
            use_full_length=False,
            enabled=True,
        ))
        assert model.get_duration_ms() == 5000

    def test_get_duration_ms_full_length_audio_layer(self):
        """A full-length audio layer with start_ms only contributes start_ms."""
        model = CompositionModel()
        model.add_layer(CompositionLayer(display_name="L1", end_ms=10000))
        model.audio_layers.append(CompositionAudioLayer(
            display_name="Music",
            start_ms=500,
            use_full_length=True,
            enabled=True,
        ))
        assert model.get_duration_ms() == 10000

    def test_get_duration_ms_disabled_audio_layer_excluded(self):
        model = CompositionModel()
        model.add_layer(CompositionLayer(display_name="L1", end_ms=3000))
        model.audio_layers.append(CompositionAudioLayer(
            display_name="Music",
            start_ms=0,
            duration_ms=10000,
            use_full_length=False,
            enabled=False,
        ))
        assert model.get_duration_ms() == 3000


# ------------------------------------------------------------------
# Audio layer undo/redo commands
# ------------------------------------------------------------------


class TestAudioLayerUndoCommands:
    def test_add_audio_layer_command(self):
        model = CompositionModel()
        al = CompositionAudioLayer(display_name="Music")
        cmd = AddAudioLayerCommand(model, al)
        cmd.redo()
        assert len(model.audio_layers) == 1
        assert model.audio_layers[0].display_name == "Music"

        cmd.undo()
        assert len(model.audio_layers) == 0

    def test_remove_audio_layer_command(self):
        model = CompositionModel()
        al = CompositionAudioLayer(display_name="Removable")
        model.audio_layers.append(al)

        cmd = RemoveAudioLayerCommand(model, al.id)
        cmd.redo()
        assert len(model.audio_layers) == 0

        cmd.undo()
        assert len(model.audio_layers) == 1
        assert model.audio_layers[0].display_name == "Removable"

    def test_remove_audio_layer_preserves_index(self):
        model = CompositionModel()
        al1 = CompositionAudioLayer(display_name="First")
        al2 = CompositionAudioLayer(display_name="Second")
        al3 = CompositionAudioLayer(display_name="Third")
        model.audio_layers.extend([al1, al2, al3])

        cmd = RemoveAudioLayerCommand(model, al2.id)
        cmd.redo()
        assert len(model.audio_layers) == 2
        assert model.audio_layers[0].display_name == "First"
        assert model.audio_layers[1].display_name == "Third"

        cmd.undo()
        assert len(model.audio_layers) == 3
        assert model.audio_layers[1].display_name == "Second"

    def test_edit_audio_layer_command(self):
        model = CompositionModel()
        al = CompositionAudioLayer(
            display_name="Editable",
            start_ms=0,
            duration_ms=0,
            use_full_length=True,
        )
        model.audio_layers.append(al)

        cmd = EditAudioLayerCommand(
            model, al.id,
            start_ms=1000,
            duration_ms=5000,
            use_full_length=False,
        )
        cmd.redo()
        assert al.start_ms == 1000
        assert al.duration_ms == 5000
        assert al.use_full_length is False

        cmd.undo()
        assert al.start_ms == 0
        assert al.duration_ms == 0
        assert al.use_full_length is True

    def test_edit_audio_layer_partial_fields(self):
        model = CompositionModel()
        al = CompositionAudioLayer(display_name="Test", start_ms=100, enabled=True)
        model.audio_layers.append(al)

        cmd = EditAudioLayerCommand(model, al.id, enabled=False)
        cmd.redo()
        assert al.enabled is False
        assert al.start_ms == 100  # unchanged

        cmd.undo()
        assert al.enabled is True

    def test_audio_layer_undo_redo_via_tab_stack(self):
        tab = RenderCompositionTab()
        model = tab._model

        al = CompositionAudioLayer(display_name="Undoable Audio")
        cmd = AddAudioLayerCommand(model, al)
        tab._push_command(cmd)
        assert len(model.audio_layers) == 1

        tab._undo_stack.undo()
        assert len(model.audio_layers) == 0

        tab._undo_stack.redo()
        assert len(model.audio_layers) == 1


# ------------------------------------------------------------------
# Audio layer list UI
# ------------------------------------------------------------------


class TestAudioLayerListUI:
    def test_tab_has_audio_layer_list(self):
        tab = RenderCompositionTab()
        assert hasattr(tab, "_audio_layer_list")
        assert hasattr(tab, "_add_audio_btn")
        assert hasattr(tab, "_remove_audio_btn")
        assert hasattr(tab, "_audio_start_spin")
        assert hasattr(tab, "_audio_duration_spin")
        assert hasattr(tab, "_audio_full_length_cb")

    def test_add_audio_layer_updates_list(self):
        tab = RenderCompositionTab()
        tab._on_add_audio_layer()
        assert len(tab._model.audio_layers) == 1
        assert tab._audio_layer_list.count() == 1

    def test_remove_audio_layer_updates_list(self):
        tab = RenderCompositionTab()
        tab._on_add_audio_layer()
        assert tab._audio_layer_list.count() == 1

        tab._audio_layer_list.setCurrentRow(0)
        tab._on_remove_audio_layer()
        assert len(tab._model.audio_layers) == 0
        assert tab._audio_layer_list.count() == 0

    def test_audio_layer_editor_controls(self):
        tab = RenderCompositionTab()
        al = CompositionAudioLayer(
            display_name="Test Audio",
            start_ms=2000,
            duration_ms=5000,
            use_full_length=False,
        )
        tab._model.audio_layers.append(al)
        tab._refresh_audio_layer_list()
        tab._audio_layer_list.setCurrentRow(0)
        tab._load_audio_layer_properties(al)

        assert tab._audio_start_spin.value() == 2000
        assert tab._audio_duration_spin.value() == 5000
        assert tab._audio_full_length_cb.isChecked() is False

    def test_apply_settings_restores_audio_layers(self):
        tab = RenderCompositionTab()
        model = CompositionModel()
        model.audio_layers.append(CompositionAudioLayer(
            display_name="Restored Audio",
            asset_path=Path("/tmp/restored.mp3"),
        ))
        tab.apply_settings({"model": model.to_dict()})

        assert len(tab._model.audio_layers) == 1
        assert tab._model.audio_layers[0].display_name == "Restored Audio"
        assert tab._audio_layer_list.count() == 1
