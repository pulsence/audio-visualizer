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
        assert "ui" in schema
        assert "tabs" in schema
        assert "session" in schema

        # Version matches constant
        assert schema["version"] == CURRENT_SCHEMA_VERSION

        # Tabs has exactly 5 keys
        assert len(schema["tabs"]) == 5
        expected_tabs = {
            "audio_visualizer",
            "srt_gen",
            "srt_edit",
            "caption_animate",
            "render_composition",
        }
        assert set(schema["tabs"].keys()) == expected_tabs

        # Each tab starts empty
        for tab_key in expected_tabs:
            assert schema["tabs"][tab_key] == {}

        # Session has expected structure
        assert "assets" in schema["session"]
        assert "roles" in schema["session"]


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

    def test_migrate_pre_stage_three(self):
        old_format = {
            "general": {"audio_file_path": "test.mp3", "fps": 12},
            "visualizer": {"visualizer_type": "Volume: Rectangle"},
            "specific": {"box_height": 50},
            "ui": {"preview": True, "show_output": False},
        }
        migrated = migrate_settings(old_format)

        # Should have current version
        assert migrated["version"] == CURRENT_SCHEMA_VERSION
        assert "tabs" in migrated

        av_tab = migrated["tabs"]["audio_visualizer"]

        # Old general keys preserved
        assert av_tab["general"]["audio_file_path"] == "test.mp3"
        assert av_tab["general"]["fps"] == 12

        # Old visualizer keys preserved
        assert av_tab["visualizer"]["visualizer_type"] == "Volume: Rectangle"

        # Old specific keys preserved
        assert av_tab["specific"]["box_height"] == 50

        # Old ui keys that belong in tab are preserved
        assert av_tab["ui"]["preview"] is True
        assert av_tab["ui"]["show_output"] is False

    def test_migrate_fills_missing_tabs(self):
        data = {
            "version": CURRENT_SCHEMA_VERSION,
            "tabs": {
                "audio_visualizer": {"general": {"fps": 30}},
                # Missing: srt_gen, srt_edit, caption_animate, render_composition
            },
        }
        migrated = migrate_settings(data)

        # All five tabs should be present
        assert len(migrated["tabs"]) == 5
        expected_tabs = {
            "audio_visualizer",
            "srt_gen",
            "srt_edit",
            "caption_animate",
            "render_composition",
        }
        assert set(migrated["tabs"].keys()) == expected_tabs

        # The existing tab data is preserved
        assert migrated["tabs"]["audio_visualizer"] == {"general": {"fps": 30}}

        # Missing tabs get filled with empty dicts
        assert migrated["tabs"]["srt_gen"] == {}
        assert migrated["tabs"]["srt_edit"] == {}
        assert migrated["tabs"]["caption_animate"] == {}
        assert migrated["tabs"]["render_composition"] == {}


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
