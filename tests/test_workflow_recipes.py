"""Tests for audio_visualizer.ui.workflowRecipes module."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from audio_visualizer.ui.workflowRecipes import (
    RECIPE_ASSET_ROLES,
    RECIPE_SCHEMA_VERSION,
    VALID_STAGES,
    WorkflowRecipe,
    apply_recipe,
    create_recipe_from_session,
    get_recipe_library_dir,
    list_saved_recipes,
    load_recipe,
    save_recipe,
    validate_recipe,
)
from audio_visualizer.ui.workspaceContext import SessionAsset, WorkspaceContext


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
    """Create a mock BaseTab with tab_id and collect/apply_settings."""
    tab = MagicMock()
    tab.tab_id = tab_id
    tab.tab_title = tab_id.replace("_", " ").title()
    tab.collect_settings.return_value = settings or {}
    return tab


def _minimal_recipe(**overrides) -> WorkflowRecipe:
    """Create a minimal valid recipe with optional overrides."""
    defaults = {
        "name": "Test Recipe",
        "version": RECIPE_SCHEMA_VERSION,
        "enabled_stages": {s: True for s in VALID_STAGES},
        "asset_roles": {r: None for r in RECIPE_ASSET_ROLES},
        "tabs": {},
        "references": {
            "caption_preset": None,
            "layout_preset": None,
            "lint_profile": None,
        },
        "export": {"naming_rule": None, "target_dir": None},
    }
    defaults.update(overrides)
    return WorkflowRecipe(**defaults)


# ------------------------------------------------------------------
# WorkflowRecipe dataclass
# ------------------------------------------------------------------


class TestWorkflowRecipeDataclass:
    def test_default_construction(self):
        recipe = WorkflowRecipe()
        assert recipe.version == RECIPE_SCHEMA_VERSION
        assert recipe.name == ""
        assert isinstance(recipe.enabled_stages, dict)
        assert isinstance(recipe.asset_roles, dict)
        assert isinstance(recipe.tabs, dict)
        assert isinstance(recipe.references, dict)
        assert isinstance(recipe.export, dict)

    def test_all_stages_present_in_default(self):
        recipe = WorkflowRecipe()
        for stage in VALID_STAGES:
            assert stage in recipe.enabled_stages

    def test_all_role_keys_present_in_default(self):
        recipe = WorkflowRecipe()
        for role in RECIPE_ASSET_ROLES:
            assert role in recipe.asset_roles

    def test_custom_construction(self):
        recipe = WorkflowRecipe(
            name="My Recipe",
            enabled_stages={"srt_gen": True, "srt_edit": False,
                            "caption_animate": True, "render_composition": False},
        )
        assert recipe.name == "My Recipe"
        assert recipe.enabled_stages["srt_gen"] is True
        assert recipe.enabled_stages["srt_edit"] is False


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------


class TestValidateRecipe:
    def test_valid_recipe(self):
        recipe = _minimal_recipe()
        valid, msg = validate_recipe(recipe)
        assert valid is True
        assert msg == ""

    def test_invalid_not_recipe(self):
        valid, msg = validate_recipe("not a recipe")  # type: ignore
        assert valid is False
        assert "not a WorkflowRecipe" in msg

    def test_invalid_version(self):
        recipe = _minimal_recipe(version=0)
        valid, msg = validate_recipe(recipe)
        assert valid is False
        assert "version" in msg.lower()

    def test_invalid_empty_name(self):
        recipe = _minimal_recipe(name="")
        valid, msg = validate_recipe(recipe)
        assert valid is False
        assert "name" in msg.lower()

    def test_invalid_whitespace_name(self):
        recipe = _minimal_recipe(name="   ")
        valid, msg = validate_recipe(recipe)
        assert valid is False
        assert "name" in msg.lower()

    def test_invalid_stage_key(self):
        recipe = _minimal_recipe(enabled_stages={"bogus_stage": True})
        valid, msg = validate_recipe(recipe)
        assert valid is False
        assert "bogus_stage" in msg

    def test_invalid_enabled_stages_type(self):
        recipe = _minimal_recipe()
        recipe.enabled_stages = "not a dict"  # type: ignore
        valid, msg = validate_recipe(recipe)
        assert valid is False
        assert "enabled_stages" in msg

    def test_invalid_asset_roles_type(self):
        recipe = _minimal_recipe()
        recipe.asset_roles = "not a dict"  # type: ignore
        valid, msg = validate_recipe(recipe)
        assert valid is False
        assert "asset_roles" in msg

    def test_invalid_tabs_type(self):
        recipe = _minimal_recipe()
        recipe.tabs = "not a dict"  # type: ignore
        valid, msg = validate_recipe(recipe)
        assert valid is False
        assert "tabs" in msg

    def test_invalid_references_type(self):
        recipe = _minimal_recipe()
        recipe.references = "not a dict"  # type: ignore
        valid, msg = validate_recipe(recipe)
        assert valid is False
        assert "references" in msg

    def test_invalid_export_type(self):
        recipe = _minimal_recipe()
        recipe.export = "not a dict"  # type: ignore
        valid, msg = validate_recipe(recipe)
        assert valid is False
        assert "export" in msg


# ------------------------------------------------------------------
# Save / load round-trip
# ------------------------------------------------------------------


class TestSaveLoadRecipe:
    def test_save_creates_file(self, tmp_path):
        recipe = _minimal_recipe()
        path = tmp_path / "test.avrecipe.json"
        result = save_recipe(recipe, path)
        assert result is True
        assert path.exists()

    def test_save_load_roundtrip(self, tmp_path):
        recipe = _minimal_recipe(
            name="Roundtrip Test",
            enabled_stages={
                "srt_gen": True,
                "srt_edit": False,
                "caption_animate": True,
                "render_composition": True,
            },
            asset_roles={
                "primary_audio": "/tmp/audio.wav",
                "subtitle_source": "/tmp/subs.srt",
                "caption_source": None,
                "background": None,
            },
            tabs={"srt_gen": {"model": "large-v3"}},
            references={"caption_preset": "my_preset", "layout_preset": None, "lint_profile": "strict"},
            export={"naming_rule": "{date}_{name}", "target_dir": "/tmp/out"},
        )

        path = tmp_path / "roundtrip.avrecipe.json"
        save_recipe(recipe, path)
        loaded = load_recipe(path)

        assert loaded is not None
        assert loaded.name == "Roundtrip Test"
        assert loaded.version == RECIPE_SCHEMA_VERSION
        assert loaded.enabled_stages == recipe.enabled_stages
        assert loaded.asset_roles == recipe.asset_roles
        assert loaded.tabs == recipe.tabs
        assert loaded.references == recipe.references
        assert loaded.export == recipe.export

    def test_load_nonexistent(self, tmp_path):
        result = load_recipe(tmp_path / "nope.avrecipe.json")
        assert result is None

    def test_load_invalid_json(self, tmp_path):
        path = tmp_path / "bad.avrecipe.json"
        path.write_text("{invalid json!!!", encoding="utf-8")
        result = load_recipe(path)
        assert result is None

    def test_load_non_object(self, tmp_path):
        path = tmp_path / "array.avrecipe.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        result = load_recipe(path)
        assert result is None

    def test_save_creates_parent_dirs(self, tmp_path):
        recipe = _minimal_recipe()
        path = tmp_path / "subdir" / "deep" / "test.avrecipe.json"
        result = save_recipe(recipe, path)
        assert result is True
        assert path.exists()


# ------------------------------------------------------------------
# Recipe versioning
# ------------------------------------------------------------------


class TestRecipeVersioning:
    def test_version_persisted(self, tmp_path):
        recipe = _minimal_recipe(version=1)
        path = tmp_path / "v1.avrecipe.json"
        save_recipe(recipe, path)

        raw = json.loads(path.read_text(encoding="utf-8"))
        assert raw["version"] == 1

    def test_load_preserves_version(self, tmp_path):
        path = tmp_path / "versioned.avrecipe.json"
        data = {
            "version": 42,
            "name": "Future Recipe",
            "enabled_stages": {},
            "asset_roles": {},
            "tabs": {},
            "references": {},
            "export": {},
        }
        path.write_text(json.dumps(data), encoding="utf-8")
        loaded = load_recipe(path)
        assert loaded is not None
        assert loaded.version == 42

    def test_default_version_matches_constant(self):
        recipe = WorkflowRecipe()
        assert recipe.version == RECIPE_SCHEMA_VERSION


# ------------------------------------------------------------------
# Recipe library
# ------------------------------------------------------------------


class TestRecipeLibrary:
    def test_get_recipe_library_dir(self):
        lib_dir = get_recipe_library_dir()
        assert lib_dir.exists()
        assert lib_dir.is_dir()
        assert lib_dir.name == "recipes"

    def test_list_saved_recipes_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "audio_visualizer.ui.workflowRecipes.get_recipe_library_dir",
            lambda: tmp_path,
        )
        recipes = list_saved_recipes()
        assert recipes == []

    def test_list_saved_recipes(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "audio_visualizer.ui.workflowRecipes.get_recipe_library_dir",
            lambda: tmp_path,
        )

        # Create some recipe files
        for i, name in enumerate(["Alpha", "Beta"]):
            recipe = _minimal_recipe(name=name)
            save_recipe(recipe, tmp_path / f"{name.lower()}.avrecipe.json")

        recipes = list_saved_recipes()
        assert len(recipes) == 2
        names = [r["name"] for r in recipes]
        assert "Alpha" in names
        assert "Beta" in names
        assert all(r["version"] == RECIPE_SCHEMA_VERSION for r in recipes)
        assert all("path" in r for r in recipes)

    def test_list_skips_unreadable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "audio_visualizer.ui.workflowRecipes.get_recipe_library_dir",
            lambda: tmp_path,
        )

        # Valid recipe
        save_recipe(_minimal_recipe(name="Good"), tmp_path / "good.avrecipe.json")
        # Invalid file
        (tmp_path / "bad.avrecipe.json").write_text("{invalid!!!", encoding="utf-8")

        recipes = list_saved_recipes()
        assert len(recipes) == 1
        assert recipes[0]["name"] == "Good"


# ------------------------------------------------------------------
# create_recipe_from_session
# ------------------------------------------------------------------


class TestCreateRecipeFromSession:
    def test_basic_creation(self):
        tabs = [
            _make_mock_tab("audio_visualizer", {"fps": 30}),
            _make_mock_tab("srt_gen", {"model": "base"}),
            _make_mock_tab("srt_edit", {"lint_profile": "strict"}),
            _make_mock_tab("caption_animate"),
            _make_mock_tab("render_composition"),
        ]
        ctx = WorkspaceContext()

        recipe = create_recipe_from_session(tabs, ctx, name="Test")
        assert recipe.name == "Test"
        assert recipe.version == RECIPE_SCHEMA_VERSION

        # All stages should be enabled (they appear as tab ids)
        for stage in VALID_STAGES:
            assert stage in recipe.enabled_stages

        # Tab settings should be collected
        assert recipe.tabs["audio_visualizer"] == {"fps": 30}
        assert recipe.tabs["srt_gen"] == {"model": "base"}

        # References should pick up lint_profile
        assert recipe.references["lint_profile"] == "strict"

    def test_asset_roles_from_session(self):
        tabs = [_make_mock_tab("audio_visualizer")]
        ctx = WorkspaceContext()
        ctx.register_asset(_make_asset(
            "a1", path=Path("/tmp/audio.wav"),
            category="audio", role="primary_audio",
        ))
        ctx.register_asset(_make_asset(
            "s1", path=Path("/tmp/subs.srt"),
            category="subtitle", role="subtitle_source",
        ))

        recipe = create_recipe_from_session(tabs, ctx, name="Roles Test")
        assert recipe.asset_roles["primary_audio"] == str(Path("/tmp/audio.wav"))
        assert recipe.asset_roles["subtitle_source"] == str(Path("/tmp/subs.srt"))
        assert recipe.asset_roles["caption_source"] is None
        assert recipe.asset_roles["background"] is None


# ------------------------------------------------------------------
# apply_recipe
# ------------------------------------------------------------------


class TestApplyRecipe:
    def test_applies_tab_settings(self):
        tabs = [
            _make_mock_tab("audio_visualizer"),
            _make_mock_tab("srt_gen"),
        ]
        ctx = WorkspaceContext()

        recipe = _minimal_recipe(
            tabs={
                "audio_visualizer": {"fps": 24},
                "srt_gen": {"model": "large-v3"},
            }
        )

        apply_recipe(recipe, tabs, ctx)

        tabs[0].apply_settings.assert_called_once_with({"fps": 24})
        tabs[1].apply_settings.assert_called_once_with({"model": "large-v3"})

    def test_skips_missing_tabs(self):
        """Recipe references a tab_id not present in the tab list."""
        tabs = [_make_mock_tab("audio_visualizer")]
        ctx = WorkspaceContext()

        recipe = _minimal_recipe(
            tabs={
                "audio_visualizer": {"fps": 24},
                "nonexistent_tab": {"key": "value"},
            }
        )

        # Should not raise
        apply_recipe(recipe, tabs, ctx)
        tabs[0].apply_settings.assert_called_once_with({"fps": 24})

    def test_asset_role_binding_from_session(self):
        """Recipe binds asset roles through session context."""
        tabs = [_make_mock_tab("audio_visualizer")]
        ctx = WorkspaceContext()
        ctx.register_asset(_make_asset(
            "a1", path=Path("/tmp/audio.wav"), category="audio",
        ))

        recipe = _minimal_recipe(
            asset_roles={
                "primary_audio": "/tmp/audio.wav",
                "subtitle_source": None,
                "caption_source": None,
                "background": None,
            }
        )

        apply_recipe(recipe, tabs, ctx)

        # The asset should now have the role assigned
        asset = ctx.get_asset("a1")
        assert asset is not None
        assert asset.role == "primary_audio"

    def test_role_already_bound_in_session(self):
        """Recipe role already bound — no duplicate assignment."""
        tabs = [_make_mock_tab("audio_visualizer")]
        ctx = WorkspaceContext()
        ctx.register_asset(_make_asset(
            "a1", path=Path("/tmp/audio.wav"),
            category="audio", role="primary_audio",
        ))

        recipe = _minimal_recipe(
            asset_roles={
                "primary_audio": "/tmp/audio.wav",
                "subtitle_source": None,
                "caption_source": None,
                "background": None,
            }
        )

        # Should not raise or duplicate
        apply_recipe(recipe, tabs, ctx)
        asset = ctx.get_asset("a1")
        assert asset.role == "primary_audio"

    def test_missing_binding_left_unbound(self):
        """Recipe references a path not in session — role stays unbound."""
        tabs = [_make_mock_tab("audio_visualizer")]
        ctx = WorkspaceContext()

        recipe = _minimal_recipe(
            asset_roles={
                "primary_audio": "/tmp/missing.wav",
                "subtitle_source": None,
                "caption_source": None,
                "background": None,
            }
        )

        # Should not raise
        apply_recipe(recipe, tabs, ctx)

        # No assets exist, so nothing should be bound
        all_assets = ctx.list_assets()
        assert len(all_assets) == 0

    def test_empty_tabs_dict(self):
        """Recipe with empty tabs dict still applies without error."""
        tabs = [_make_mock_tab("audio_visualizer")]
        ctx = WorkspaceContext()
        recipe = _minimal_recipe(tabs={})

        apply_recipe(recipe, tabs, ctx)
        tabs[0].apply_settings.assert_not_called()


# ------------------------------------------------------------------
# Full round-trip: create -> save -> load -> apply
# ------------------------------------------------------------------


class TestRecipeFullRoundTrip:
    def test_create_save_load_apply(self, tmp_path):
        # Setup: create tabs with settings and a session with assets
        tabs = [
            _make_mock_tab("audio_visualizer", {"fps": 30}),
            _make_mock_tab("srt_gen", {"model": "large-v3", "language": "en"}),
            _make_mock_tab("srt_edit", {"lint_profile": "strict"}),
            _make_mock_tab("caption_animate", {"preset": "default"}),
            _make_mock_tab("render_composition"),
        ]
        ctx = WorkspaceContext()
        ctx.register_asset(_make_asset(
            "audio1", path=Path("/tmp/song.wav"),
            category="audio", role="primary_audio",
        ))

        # Step 1: Create recipe from session
        recipe = create_recipe_from_session(tabs, ctx, name="Full Test")
        assert recipe.name == "Full Test"
        assert recipe.asset_roles["primary_audio"] == str(Path("/tmp/song.wav"))

        # Step 2: Save
        path = tmp_path / "full_test.avrecipe.json"
        assert save_recipe(recipe, path) is True

        # Step 3: Load
        loaded = load_recipe(path)
        assert loaded is not None
        assert loaded.name == "Full Test"
        assert loaded.tabs["srt_gen"] == {"model": "large-v3", "language": "en"}

        # Step 4: Apply to a fresh set of tabs with a fresh session
        apply_tabs = [
            _make_mock_tab("audio_visualizer"),
            _make_mock_tab("srt_gen"),
            _make_mock_tab("srt_edit"),
            _make_mock_tab("caption_animate"),
            _make_mock_tab("render_composition"),
        ]
        apply_ctx = WorkspaceContext()
        # Register the same asset so role binding can work
        apply_ctx.register_asset(_make_asset(
            "audio1", path=Path("/tmp/song.wav"), category="audio",
        ))

        apply_recipe(loaded, apply_tabs, apply_ctx)

        # Verify tab settings were applied
        apply_tabs[0].apply_settings.assert_called_once_with({"fps": 30})
        apply_tabs[1].apply_settings.assert_called_once_with(
            {"model": "large-v3", "language": "en"}
        )

        # Verify asset role was bound
        asset = apply_ctx.get_asset("audio1")
        assert asset is not None
        assert asset.role == "primary_audio"
