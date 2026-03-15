"""Tests for the config module."""
import json
import pytest
from local_srt.config import PRESETS, apply_overrides, load_config_file
from local_srt.models import ResolvedConfig


class TestPresets:
    """Tests for PRESETS constant."""

    def test_presets_exist(self):
        """Test that presets dictionary exists."""
        assert PRESETS is not None
        assert isinstance(PRESETS, dict)

    def test_preset_keys(self):
        """Test that expected preset keys exist."""
        expected_keys = {"shorts", "yt", "podcast", "transcript"}
        assert set(PRESETS.keys()) == expected_keys

    def test_preset_structure(self):
        """Test that each preset has the expected structure."""
        for name, preset in PRESETS.items():
            assert isinstance(preset, dict), f"Preset {name} is not a dict"
            # Check for common keys
            assert "formatting" in preset
            assert "transcription" in preset
            assert "silence" in preset

    def test_shorts_preset(self):
        """Test shorts preset values."""
        shorts = PRESETS["shorts"]
        assert shorts["formatting"]["max_chars"] == 18
        assert shorts["formatting"]["max_lines"] == 1
        assert shorts["formatting"]["target_cps"] == 18.0

    def test_yt_preset(self):
        """Test yt preset values."""
        yt = PRESETS["yt"]
        assert yt["formatting"]["max_chars"] == 42
        assert yt["formatting"]["max_lines"] == 2
        assert yt["formatting"]["target_cps"] == 17.0

    def test_podcast_preset(self):
        """Test podcast preset values."""
        podcast = PRESETS["podcast"]
        assert podcast["formatting"]["max_chars"] == 40
        assert podcast["formatting"]["max_lines"] == 2
        assert podcast["formatting"]["target_cps"] == 16.0
        assert podcast["formatting"]["prefer_punct_splits"] is True

    def test_transcript_preset(self):
        """Test transcript preset values."""
        transcript = PRESETS["transcript"]
        assert transcript["formatting"]["max_chars"] == 80
        assert transcript["formatting"]["max_lines"] == 4
        assert transcript["formatting"]["min_dur"] == 2.0
        assert transcript["formatting"]["max_dur"] == 30.0
        assert transcript["formatting"]["prefer_punct_splits"] is True


class TestLoadConfigFile:
    """Tests for load_config_file function."""

    def test_load_config_none_path(self):
        """Test loading config with None path returns empty dict."""
        result = load_config_file(None)
        assert result == {}

    def test_load_config_file_not_found(self):
        """Test loading non-existent config file raises error."""
        with pytest.raises(FileNotFoundError):
            load_config_file("/nonexistent/path/config.json")

    def test_load_valid_config_file(self, tmp_path):
        """Test loading a valid config file."""
        config_data = {
            "formatting": {
                "max_chars": 50,
                "max_lines": 3,
                "target_cps": 20.0,
            }
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data), encoding="utf-8")

        result = load_config_file(str(config_file))
        assert result == config_data

    def test_load_config_invalid_json(self, tmp_path):
        """Test loading invalid JSON raises error."""
        config_file = tmp_path / "invalid.json"
        config_file.write_text("not valid json", encoding="utf-8")

        with pytest.raises(json.JSONDecodeError):
            load_config_file(str(config_file))

    def test_load_config_non_dict(self, tmp_path):
        """Test loading JSON that isn't a dict raises error."""
        config_file = tmp_path / "array.json"
        config_file.write_text(json.dumps(["array", "data"]), encoding="utf-8")

        with pytest.raises(ValueError, match="Config must be a JSON object"):
            load_config_file(str(config_file))

    def test_load_empty_config_file(self, tmp_path):
        """Test loading empty config file."""
        config_file = tmp_path / "empty.json"
        config_file.write_text(json.dumps({}), encoding="utf-8")

        result = load_config_file(str(config_file))
        assert result == {}


class TestApplyOverrides:
    """Tests for apply_overrides function."""

    def test_apply_overrides_empty(self):
        """Test applying empty overrides."""
        base = ResolvedConfig()
        result = apply_overrides(base, {})

        # Should return new instance with same values
        assert result is not base
        assert result.formatting.max_chars == base.formatting.max_chars
        assert result.formatting.max_lines == base.formatting.max_lines

    def test_apply_overrides_single_field(self):
        """Test applying override to single field."""
        base = ResolvedConfig()
        result = apply_overrides(base, {"formatting": {"max_chars": 50}})

        assert result.formatting.max_chars == 50
        # Other fields should remain default
        assert result.formatting.max_lines == base.formatting.max_lines
        assert result.formatting.target_cps == base.formatting.target_cps

    def test_apply_overrides_multiple_fields(self):
        """Test applying overrides to multiple fields."""
        base = ResolvedConfig()
        overrides = {
            "formatting": {
                "max_chars": 50,
                "max_lines": 3,
                "target_cps": 20.0,
                "min_dur": 0.5,
            }
        }
        result = apply_overrides(base, overrides)

        assert result.formatting.max_chars == 50
        assert result.formatting.max_lines == 3
        assert result.formatting.target_cps == 20.0
        assert result.formatting.min_dur == 0.5

    def test_apply_overrides_invalid_field_ignored(self):
        """Test that invalid field names are ignored."""
        base = ResolvedConfig()
        overrides = {
            "formatting": {
                "max_chars": 50,
                "invalid_field": "should be ignored",
            },
        }
        result = apply_overrides(base, overrides)

        assert result.formatting.max_chars == 50
        assert not hasattr(result.formatting, "invalid_field")

    def test_apply_overrides_preserves_base(self):
        """Test that base config is not modified."""
        base = ResolvedConfig()
        original_max_chars = base.formatting.max_chars

        result = apply_overrides(base, {"formatting": {"max_chars": 50}})

        # Base should be unchanged
        assert base.formatting.max_chars == original_max_chars
        # Result should have new value
        assert result.formatting.max_chars == 50

    def test_apply_overrides_with_preset(self):
        """Test applying preset as overrides."""
        base = ResolvedConfig()
        result = apply_overrides(base, PRESETS["shorts"])

        assert result.formatting.max_chars == PRESETS["shorts"]["formatting"]["max_chars"]
        assert result.formatting.max_lines == PRESETS["shorts"]["formatting"]["max_lines"]
        assert result.formatting.target_cps == PRESETS["shorts"]["formatting"]["target_cps"]

    def test_apply_overrides_boolean_fields(self):
        """Test applying overrides to boolean fields."""
        base = ResolvedConfig()
        overrides = {
            "formatting": {
                "allow_commas": False,
                "prefer_punct_splits": True,
            },
            "transcription": {
                "vad_filter": False,
            },
        }
        result = apply_overrides(base, overrides)

        assert result.formatting.allow_commas is False
        assert result.formatting.prefer_punct_splits is True
        assert result.transcription.vad_filter is False

    def test_apply_overrides_float_fields(self):
        """Test applying overrides to float fields."""
        base = ResolvedConfig()
        overrides = {
            "formatting": {
                "min_gap": 0.1,
                "pad": 0.05,
            },
            "silence": {
                "silence_threshold_db": -40.0,
            },
        }
        result = apply_overrides(base, overrides)

        assert result.formatting.min_gap == 0.1
        assert result.formatting.pad == 0.05
        assert result.silence.silence_threshold_db == -40.0
