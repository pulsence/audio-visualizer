"""Tests for audio_visualizer.ui.settingsSchema module."""

import json

import pytest
from pathlib import Path

from audio_visualizer.ui.settingsSchema import (
    create_default_schema,
    migrate_settings,
    save_settings,
    load_settings,
    validate_schema,
    CURRENT_SCHEMA_VERSION,
)


# ------------------------------------------------------------------
# create_default_schema
# ------------------------------------------------------------------


class TestCreateDefaultSchema:
    def test_create_default_schema(self):
        schema = create_default_schema()

        # Top-level keys
        assert "version" in schema
        assert "app" in schema
        assert "ui" in schema
        assert "tabs" in schema
        assert "session" in schema

        # Version matches constant
        assert schema["version"] == CURRENT_SCHEMA_VERSION

        # App section defaults
        assert schema["app"]["theme_mode"] == "auto"

        # Tabs has exactly 6 keys
        assert len(schema["tabs"]) == 6
        expected_tabs = {
            "audio_visualizer",
            "srt_gen",
            "srt_edit",
            "caption_animate",
            "render_composition",
            "assets",
        }
        assert set(schema["tabs"].keys()) == expected_tabs

        # Each tab starts empty
        for tab_key in expected_tabs:
            assert schema["tabs"][tab_key] == {}

        # Session has expected structure
        assert "assets" in schema["session"]
        assert "roles" in schema["session"]
        assert "project_folder" in schema["session"]
        assert schema["session"]["project_folder"] is None


# ------------------------------------------------------------------
# validate_schema
# ------------------------------------------------------------------


class TestValidateSchema:
    def test_validate_schema_valid(self):
        schema = create_default_schema()
        assert validate_schema(schema) is True

    def test_validate_schema_missing_version(self):
        schema = create_default_schema()
        del schema["version"]
        assert validate_schema(schema) is False

    def test_validate_schema_missing_tabs(self):
        schema = create_default_schema()
        del schema["tabs"]
        assert validate_schema(schema) is False


# ------------------------------------------------------------------
# migrate_settings
# ------------------------------------------------------------------


class TestMigrateSettings:
    def test_migrate_already_versioned(self):
        original = create_default_schema()
        original["tabs"]["audio_visualizer"] = {"general": {"fps": 30}}
        migrated = migrate_settings(original)

        # Data passes through unchanged (deep-copied)
        assert migrated["version"] == CURRENT_SCHEMA_VERSION
        assert migrated["tabs"]["audio_visualizer"] == {"general": {"fps": 30}}
        # Verify it is a copy, not the same object
        assert migrated is not original

    def test_migrate_pre_stage_three_rejected(self):
        """Pre-Stage-Three settings are rejected and a clean default is returned."""
        old_format = {
            "general": {"audio_file_path": "test.mp3", "fps": 12},
            "visualizer": {"visualizer_type": "Volume: Rectangle"},
            "specific": {"box_height": 50},
            "ui": {"preview": True, "show_output": False},
        }
        migrated = migrate_settings(old_format)

        # Should return a clean default schema, not the old data
        assert migrated["version"] == CURRENT_SCHEMA_VERSION
        assert "tabs" in migrated
        assert len(migrated["tabs"]) == 6

        # All tabs should be empty (old data discarded)
        for tab_key in migrated["tabs"]:
            assert migrated["tabs"][tab_key] == {}

    def test_migrate_fills_missing_tabs(self):
        data = {
            "version": CURRENT_SCHEMA_VERSION,
            "tabs": {
                "audio_visualizer": {"general": {"fps": 30}},
                # Missing: srt_gen, srt_edit, caption_animate, render_composition
            },
        }
        migrated = migrate_settings(data)

        # All six tabs should be present
        assert len(migrated["tabs"]) == 6
        expected_tabs = {
            "audio_visualizer",
            "srt_gen",
            "srt_edit",
            "caption_animate",
            "render_composition",
            "assets",
        }
        assert set(migrated["tabs"].keys()) == expected_tabs

        # The existing tab data is preserved
        assert migrated["tabs"]["audio_visualizer"] == {"general": {"fps": 30}}

        # Missing tabs get filled with empty dicts
        assert migrated["tabs"]["srt_gen"] == {}
        assert migrated["tabs"]["srt_edit"] == {}
        assert migrated["tabs"]["caption_animate"] == {}
        assert migrated["tabs"]["render_composition"] == {}
        assert migrated["tabs"]["assets"] == {}

    def test_migrate_fills_missing_app_section(self):
        """Versioned settings without an 'app' key get one filled in."""
        data = {
            "version": CURRENT_SCHEMA_VERSION,
            "tabs": {"audio_visualizer": {}},
        }
        migrated = migrate_settings(data)
        assert "app" in migrated
        assert migrated["app"]["theme_mode"] == "auto"

    def test_migrate_preserves_existing_app_section(self):
        """Existing app settings are not overwritten during migration."""
        data = {
            "version": CURRENT_SCHEMA_VERSION,
            "app": {"theme_mode": "on"},
            "tabs": {"audio_visualizer": {}},
        }
        migrated = migrate_settings(data)
        assert migrated["app"]["theme_mode"] == "on"


# ------------------------------------------------------------------
# save / load persistence
# ------------------------------------------------------------------


class TestPersistence:
    def test_save_load_roundtrip(self, tmp_path):
        data = create_default_schema()
        data["tabs"]["audio_visualizer"] = {"general": {"fps": 24}}
        path = tmp_path / "settings.json"

        result = save_settings(data, path)
        assert result is True
        assert path.exists()

        loaded = load_settings(path)
        assert loaded is not None
        assert loaded["version"] == data["version"]
        assert loaded["tabs"]["audio_visualizer"] == data["tabs"]["audio_visualizer"]
        assert loaded["ui"] == data["ui"]

    def test_load_nonexistent(self, tmp_path):
        path = tmp_path / "does_not_exist.json"
        result = load_settings(path)
        assert result is None

    def test_load_invalid_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{not valid json!!!", encoding="utf-8")
        result = load_settings(path)
        assert result is None
