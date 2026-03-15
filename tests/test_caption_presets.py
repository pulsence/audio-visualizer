"""Tests for caption preset loading with app data directory resolution."""
import json
import pytest
from audio_visualizer.caption.presets.loader import PresetLoader


class TestPresetLoaderDataDir:
    """Tests for PresetLoader using app data directory."""

    def test_default_preset_dir_uses_data_dir(self, monkeypatch, tmp_path):
        """Default preset_dirs should point to the app data directory."""
        fake_data = tmp_path / "app_data"
        fake_data.mkdir()
        monkeypatch.setattr(
            "audio_visualizer.caption.presets.loader.get_data_dir",
            lambda: fake_data,
        )
        loader = PresetLoader()
        assert len(loader.preset_dirs) == 1
        assert loader.preset_dirs[0] == fake_data / "caption" / "presets"

    def test_builtin_presets_load_without_filesystem(self):
        """Built-in presets should load regardless of directory state."""
        loader = PresetLoader(preset_dirs=[])
        preset = loader.load("modern_box")
        assert preset.font_size > 0

    def test_file_preset_from_data_dir(self, monkeypatch, tmp_path):
        """PresetLoader should find file-based presets in the data dir."""
        fake_data = tmp_path / "app_data"
        presets_dir = fake_data / "caption" / "presets"
        presets_dir.mkdir(parents=True)
        monkeypatch.setattr(
            "audio_visualizer.caption.presets.loader.get_data_dir",
            lambda: fake_data,
        )
        preset_data = {"font_size": 72, "padding": 20}
        (presets_dir / "custom.json").write_text(
            json.dumps(preset_data), encoding="utf-8"
        )
        loader = PresetLoader()
        preset = loader.load("custom.json")
        assert preset.font_size == 72

    def test_default_preset_dir_seeds_example_files(self, monkeypatch, tmp_path):
        """Bundled example preset files are copied to the app data dir."""
        fake_data = tmp_path / "app_data"
        fake_data.mkdir()
        monkeypatch.setattr(
            "audio_visualizer.caption.presets.loader.get_data_dir",
            lambda: fake_data,
        )

        loader = PresetLoader()
        presets_dir = fake_data / "caption" / "presets"

        assert loader.preset_dirs == [presets_dir]
        assert (presets_dir / "preset.json").exists()
        assert (presets_dir / "word_highlight.json").exists()

    def test_seeded_example_preset_can_be_loaded(self, monkeypatch, tmp_path):
        """A seeded example preset should load through the default loader path."""
        fake_data = tmp_path / "app_data"
        fake_data.mkdir()
        monkeypatch.setattr(
            "audio_visualizer.caption.presets.loader.get_data_dir",
            lambda: fake_data,
        )

        loader = PresetLoader()
        preset = loader.load("word_highlight.json")
        assert preset.animation is not None
        assert preset.animation.type == "word_reveal"

    def test_explicit_preset_dirs_override(self, tmp_path):
        """Passing explicit preset_dirs should override the default."""
        custom_dir = tmp_path / "my_presets"
        custom_dir.mkdir()
        loader = PresetLoader(preset_dirs=[custom_dir])
        assert loader.preset_dirs == [custom_dir]

    def test_list_available_no_cwd_error(self, monkeypatch, tmp_path):
        """list_available should not raise when cwd is unrelated."""
        fake_data = tmp_path / "app_data"
        fake_data.mkdir()
        monkeypatch.setattr(
            "audio_visualizer.caption.presets.loader.get_data_dir",
            lambda: fake_data,
        )
        loader = PresetLoader()
        result = loader.list_available()
        assert "modern_box" in result
        assert "clean_outline" in result
