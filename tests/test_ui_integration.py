"""Integration tests for cross-tab workflows, settings migration,
busy-state behaviour, and handoff flows.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from audio_visualizer.ui.workspaceContext import SessionAsset, WorkspaceContext
from audio_visualizer.ui.settingsSchema import (
    CURRENT_SCHEMA_VERSION,
    create_default_schema,
    migrate_settings,
    save_settings,
    load_settings,
)
from audio_visualizer.ui.workflowRecipes import (
    RECIPE_SCHEMA_VERSION,
    VALID_STAGES,
    RECIPE_ASSET_ROLES,
    WorkflowRecipe,
    apply_recipe,
    create_recipe_from_session,
    save_recipe,
    load_recipe,
    validate_recipe,
)
from audio_visualizer.ui.mainWindow import MainWindow
from audio_visualizer.ui.tabs.baseTab import BaseTab


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_asset(
    asset_id: str = "a1",
    display_name: str = "Test Asset",
    path: Path = Path("/tmp/test.wav"),
    category: str = "audio",
    source_tab: str | None = None,
    role: str | None = None,
) -> SessionAsset:
    return SessionAsset(
        id=asset_id,
        display_name=display_name,
        path=path,
        category=category,
        source_tab=source_tab,
        role=role,
    )


def _make_mock_tab(tab_id: str, settings: dict | None = None) -> MagicMock:
    tab = MagicMock(spec=BaseTab)
    tab.tab_id = tab_id
    tab.tab_title = tab_id.replace("_", " ").title()
    tab.collect_settings.return_value = settings or {}
    return tab


# ------------------------------------------------------------------
# Fixture: shared MainWindow instance
# ------------------------------------------------------------------

_cached_window = None


@pytest.fixture
def main_window():
    global _cached_window
    if _cached_window is None:
        try:
            _cached_window = MainWindow()
        except Exception as exc:
            pytest.skip(f"MainWindow could not be created: {exc}")
    return _cached_window


# ------------------------------------------------------------------
# 1. Settings migration
# ------------------------------------------------------------------


class TestSettingsMigration:
    """Test loading old Audio Visualizer-only settings into multi-tab schema."""

    def test_pre_stage_three_rejected(self):
        """Pre-Stage-Three settings are rejected and a clean default is returned."""
        old = {
            "general": {"audio_file_path": "song.mp3", "fps": 24},
            "visualizer": {"visualizer_type": "Volume: Rectangle"},
            "specific": {"box_height": 100},
            "ui": {"preview": True, "show_output": True, "preview_panel_visible": False},
        }
        migrated = migrate_settings(old)

        assert migrated["version"] == CURRENT_SCHEMA_VERSION
        assert "tabs" in migrated
        assert len(migrated["tabs"]) == 7

        # All tabs should be empty (old data discarded)
        for tab_id in migrated["tabs"]:
            assert migrated["tabs"][tab_id] == {}

    def test_already_versioned_passes_through(self):
        current = create_default_schema()
        current["tabs"]["srt_gen"] = {"model": "large-v3"}
        migrated = migrate_settings(current)

        assert migrated["version"] == CURRENT_SCHEMA_VERSION
        assert migrated["tabs"]["srt_gen"] == {"model": "large-v3"}

    def test_migration_fills_missing_sections(self):
        data = {
            "version": CURRENT_SCHEMA_VERSION,
            "tabs": {"audio_visualizer": {"general": {"fps": 30}}},
        }
        migrated = migrate_settings(data)

        assert "ui" in migrated
        assert "session" in migrated
        assert len(migrated["tabs"]) == 7

    def test_save_load_migration_roundtrip(self, tmp_path):
        """Save pre-Stage-Three format, load it, verify it falls back to defaults."""
        old = {
            "general": {"fps": 12},
            "visualizer": {"visualizer_type": "Waveform"},
        }
        path = tmp_path / "old_settings.json"
        path.write_text(json.dumps(old), encoding="utf-8")

        loaded = load_settings(path)
        assert loaded is not None
        assert loaded["version"] == CURRENT_SCHEMA_VERSION
        # Pre-Stage-Three data is rejected — all tabs are empty defaults
        assert loaded["tabs"]["audio_visualizer"] == {}


# ------------------------------------------------------------------
# 2. Cross-tab session flow
# ------------------------------------------------------------------


class TestCrossTabSessionFlow:
    """Test that outputs registered by one tab are visible to another."""

    def test_srt_gen_output_visible_to_srt_edit(self):
        ctx = WorkspaceContext()

        # SRT Gen registers an output subtitle file
        srt_asset = _make_asset(
            asset_id="srt_output_1",
            display_name="Transcription Output",
            path=Path("/tmp/output.srt"),
            category="subtitle",
            source_tab="srt_gen",
            role="subtitle_source",
        )
        ctx.register_asset(srt_asset)

        # SRT Edit queries for subtitle assets
        subtitle_assets = ctx.list_assets(category="subtitle")
        assert len(subtitle_assets) == 1
        assert subtitle_assets[0].id == "srt_output_1"
        assert subtitle_assets[0].source_tab == "srt_gen"

    def test_caption_animate_output_visible_to_composition(self):
        ctx = WorkspaceContext()

        # Caption Animate registers an overlay video
        overlay_asset = _make_asset(
            asset_id="caption_overlay_1",
            display_name="Caption Overlay",
            path=Path("/tmp/overlay.mov"),
            category="video",
            source_tab="caption_animate",
            role="caption_overlay",
        )
        overlay_asset.has_alpha = True
        overlay_asset.is_overlay_ready = True
        ctx.register_asset(overlay_asset)

        # Composition queries for overlay-ready video assets
        video_assets = ctx.list_assets(category="video")
        assert len(video_assets) == 1
        assert video_assets[0].id == "caption_overlay_1"
        assert video_assets[0].has_alpha is True
        assert video_assets[0].is_overlay_ready is True

    def test_audio_visualizer_output_visible_to_composition(self):
        ctx = WorkspaceContext()

        # Audio Visualizer registers a visualizer output
        viz_asset = _make_asset(
            asset_id="viz_output_1",
            display_name="Visualizer Output",
            path=Path("/tmp/visualizer.mp4"),
            category="video",
            source_tab="audio_visualizer",
            role="visualizer_output",
        )
        ctx.register_asset(viz_asset)

        # Composition can find it by role
        role_assets = ctx.get_assets_by_role("visualizer_output")
        assert len(role_assets) == 1
        assert role_assets[0].source_tab == "audio_visualizer"

    def test_multi_asset_workflow(self):
        """Full pipeline: audio -> SRT Gen -> SRT Edit -> Caption Animate -> Composition."""
        ctx = WorkspaceContext()

        # Step 1: User loads audio
        ctx.register_asset(_make_asset(
            "audio_1", "Song.wav", Path("/tmp/song.wav"),
            "audio", role="primary_audio",
        ))

        # Step 2: SRT Gen produces subtitle
        ctx.register_asset(_make_asset(
            "srt_1", "Transcription.srt", Path("/tmp/transcription.srt"),
            "subtitle", source_tab="srt_gen", role="subtitle_source",
        ))

        # Step 3: SRT Edit saves edited subtitle
        ctx.register_asset(_make_asset(
            "srt_2", "Edited.srt", Path("/tmp/edited.srt"),
            "subtitle", source_tab="srt_edit",
        ))

        # Step 4: Caption Animate renders overlay
        ctx.register_asset(SessionAsset(
            id="overlay_1",
            display_name="Caption Overlay",
            path=Path("/tmp/overlay.mov"),
            category="video",
            source_tab="caption_animate",
            role="caption_overlay",
            has_alpha=True,
            is_overlay_ready=True,
        ))

        # Verify the full chain is accessible
        assert len(ctx.list_assets()) == 4
        assert len(ctx.list_assets(category="subtitle")) == 2
        assert len(ctx.list_assets(category="video")) == 1
        assert len(ctx.list_assets(role="primary_audio")) == 1
        assert len(ctx.list_assets(role="caption_overlay")) == 1


# ------------------------------------------------------------------
# 3. Recipe round-trip
# ------------------------------------------------------------------


class TestRecipeRoundTrip:
    def test_save_load_contents_match(self, tmp_path):
        recipe = WorkflowRecipe(
            name="Integration Test",
            enabled_stages={s: (s != "srt_edit") for s in VALID_STAGES},
            asset_roles={
                "primary_audio": "/tmp/audio.wav",
                "subtitle_source": "/tmp/subs.srt",
                "caption_source": None,
                "background": None,
            },
            tabs={
                "srt_gen": {"model": "large-v3"},
                "audio_visualizer": {"fps": 24},
            },
            references={"caption_preset": "bold", "layout_preset": None, "lint_profile": "strict"},
            export={"naming_rule": "{name}_{date}", "target_dir": "/out"},
        )

        path = tmp_path / "roundtrip.avrecipe.json"
        save_recipe(recipe, path)
        loaded = load_recipe(path)

        assert loaded is not None
        assert loaded.name == recipe.name
        assert loaded.enabled_stages == recipe.enabled_stages
        assert loaded.asset_roles == recipe.asset_roles
        assert loaded.tabs == recipe.tabs
        assert loaded.references == recipe.references
        assert loaded.export == recipe.export


# ------------------------------------------------------------------
# 4. Recipe application with populated WorkspaceContext
# ------------------------------------------------------------------


class TestRecipeApplication:
    def test_apply_binds_roles(self):
        tabs = [_make_mock_tab("audio_visualizer")]
        ctx = WorkspaceContext()
        ctx.register_asset(_make_asset(
            "a1", path=Path("/tmp/audio.wav"), category="audio",
        ))

        recipe = WorkflowRecipe(
            name="Binding Test",
            asset_roles={
                "primary_audio": "/tmp/audio.wav",
                "subtitle_source": None,
                "caption_source": None,
                "background": None,
            },
        )

        apply_recipe(recipe, tabs, ctx)

        asset = ctx.get_asset("a1")
        assert asset is not None
        assert asset.role == "primary_audio"

    def test_apply_with_multiple_roles(self):
        tabs = [_make_mock_tab("audio_visualizer")]
        ctx = WorkspaceContext()
        ctx.register_asset(_make_asset(
            "a1", path=Path("/tmp/audio.wav"), category="audio",
        ))
        ctx.register_asset(_make_asset(
            "s1", path=Path("/tmp/subs.srt"), category="subtitle",
        ))

        recipe = WorkflowRecipe(
            name="Multi-Role Test",
            asset_roles={
                "primary_audio": "/tmp/audio.wav",
                "subtitle_source": "/tmp/subs.srt",
                "caption_source": None,
                "background": None,
            },
        )

        apply_recipe(recipe, tabs, ctx)

        assert ctx.get_asset("a1").role == "primary_audio"
        assert ctx.get_asset("s1").role == "subtitle_source"


# ------------------------------------------------------------------
# 5. Busy state
# ------------------------------------------------------------------


class TestBusyState:
    def test_busy_state_blocks_other_tabs(self, main_window):
        """Starting a job sets global busy; all tabs are notified."""
        # Ensure we start idle
        if main_window.is_global_busy():
            main_window.finish_job("")

        assert main_window.is_global_busy() is False

        # Start a job on audio_visualizer
        result = main_window.try_start_job("audio_visualizer")
        assert result is True
        assert main_window.is_global_busy() is True
        assert main_window._busy_owner_tab_id == "audio_visualizer"

        # Finish the job
        main_window.finish_job("audio_visualizer")
        assert main_window.is_global_busy() is False
        assert main_window._busy_owner_tab_id is None


# ------------------------------------------------------------------
# 6. Handoff flow
# ------------------------------------------------------------------


class TestHandoffFlow:
    def test_handoff_to_tab_switches(self, main_window):
        """handoff_to_tab switches the active tab."""
        main_window.handoff_to_tab("srt_edit")
        active = main_window.active_tab()
        assert active is not None
        assert active.tab_id == "srt_edit"

    def test_handoff_to_tab_assigns_role(self, main_window):
        """handoff_to_tab assigns a role to the specified asset."""
        ctx = main_window.workspace_context

        # Register a test asset (clean up first)
        test_id = "handoff_test_asset"
        if ctx.get_asset(test_id) is not None:
            ctx.remove_asset(test_id)

        ctx.register_asset(_make_asset(
            test_id, path=Path("/tmp/handoff.srt"), category="subtitle",
        ))

        main_window.handoff_to_tab("srt_edit", asset_id=test_id, role="subtitle_source")

        asset = ctx.get_asset(test_id)
        assert asset is not None
        assert asset.role == "subtitle_source"
        assert main_window.active_tab().tab_id == "srt_edit"

        # Cleanup
        ctx.remove_asset(test_id)

    def test_handoff_srt_gen_to_srt_edit(self, main_window):
        """Convenience handoff method switches to SRT Edit."""
        main_window.handoff_srt_gen_to_srt_edit()
        assert main_window.active_tab().tab_id == "srt_edit"

    def test_handoff_srt_edit_to_caption_animate(self, main_window):
        """Convenience handoff method switches to Caption Animate."""
        main_window.handoff_srt_edit_to_caption_animate()
        assert main_window.active_tab().tab_id == "caption_animate"

    def test_handoff_to_composition(self, main_window):
        """Convenience handoff method switches to Render Composition."""
        main_window.handoff_to_composition()
        assert main_window.active_tab().tab_id == "render_composition"

    def test_handoff_nonexistent_tab(self, main_window):
        """Handoff to a nonexistent tab does not crash."""
        before = main_window.active_tab().tab_id
        main_window.handoff_to_tab("nonexistent_tab_id")
        # Should stay on the same tab
        assert main_window.active_tab().tab_id == before


# ------------------------------------------------------------------
# 7. Session-aware file picker (unit-level, no dialog interaction)
# ------------------------------------------------------------------


class TestSessionFilePicker:
    def test_import_available(self):
        """Verify the module can be imported."""
        from audio_visualizer.ui.sessionFilePicker import (
            SessionFilePickerDialog,
            pick_session_or_file,
        )
        assert SessionFilePickerDialog is not None
        assert pick_session_or_file is not None

    def test_dialog_creates(self):
        """SessionFilePickerDialog can be instantiated."""
        from audio_visualizer.ui.sessionFilePicker import SessionFilePickerDialog

        ctx = WorkspaceContext()
        dialog = SessionFilePickerDialog(None, ctx, "audio", "Test", "All (*)")
        assert dialog is not None
        assert dialog.result_source == ""
        assert dialog.result_path is None

    def test_dialog_populates_assets(self):
        """Dialog populates the asset list from session context."""
        from audio_visualizer.ui.sessionFilePicker import SessionFilePickerDialog

        ctx = WorkspaceContext()
        ctx.register_asset(_make_asset(
            "a1", display_name="My Audio", category="audio",
        ))
        ctx.register_asset(_make_asset(
            "v1", display_name="My Video", path=Path("/tmp/vid.mp4"), category="video",
        ))

        # Filter by audio — should show only 1
        dialog = SessionFilePickerDialog(None, ctx, "audio", "Test", "All (*)")
        # The list should have 1 item (the audio asset)
        assert dialog._asset_list.count() == 1

    def test_dialog_shows_all_when_no_category(self):
        """Dialog shows all assets when category is None."""
        from audio_visualizer.ui.sessionFilePicker import SessionFilePickerDialog

        ctx = WorkspaceContext()
        ctx.register_asset(_make_asset(
            "a1", display_name="Audio", category="audio",
        ))
        ctx.register_asset(_make_asset(
            "v1", display_name="Video", path=Path("/tmp/vid.mp4"), category="video",
        ))

        dialog = SessionFilePickerDialog(None, ctx, None, "Test", "All (*)")
        assert dialog._asset_list.count() == 2

    def test_dialog_placeholder_when_empty(self):
        """Dialog shows placeholder when no matching assets."""
        from audio_visualizer.ui.sessionFilePicker import SessionFilePickerDialog

        ctx = WorkspaceContext()
        dialog = SessionFilePickerDialog(None, ctx, "audio", "Test", "All (*)")
        # Should have exactly 1 item: the placeholder
        assert dialog._asset_list.count() == 1


# ------------------------------------------------------------------
# 8. MainWindow has recipe menu actions
# ------------------------------------------------------------------


class TestMainWindowRecipeIntegration:
    def test_recipe_actions_exist(self, main_window):
        """MainWindow has save/apply/library recipe actions."""
        assert hasattr(main_window, "_save_recipe_action")
        assert hasattr(main_window, "_apply_recipe_action")
        assert hasattr(main_window, "_recipe_library_action")

    def test_handoff_methods_exist(self, main_window):
        """MainWindow has the handoff convenience methods."""
        assert callable(getattr(main_window, "handoff_to_tab", None))
        assert callable(getattr(main_window, "handoff_srt_gen_to_srt_edit", None))
        assert callable(getattr(main_window, "handoff_srt_edit_to_caption_animate", None))
        assert callable(getattr(main_window, "handoff_to_composition", None))
