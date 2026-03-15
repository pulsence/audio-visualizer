"""Workflow recipe system for reusable workflow templates.

Recipes capture workflow intent (enabled stages, per-tab settings subsets,
asset-role expectations, preset references, and export rules) as
independently versioned ``.avrecipe.json`` artifacts.  They are distinct
from project saves and auto-saved last-session settings.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, TYPE_CHECKING

from audio_visualizer.app_paths import get_data_dir

if TYPE_CHECKING:
    from audio_visualizer.ui.sessionContext import SessionContext
    from audio_visualizer.ui.tabs.baseTab import BaseTab

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Recipe schema version (independent of settings schema)
# ------------------------------------------------------------------

RECIPE_SCHEMA_VERSION = 1

# ------------------------------------------------------------------
# Valid stage keys
# ------------------------------------------------------------------

VALID_STAGES: tuple[str, ...] = (
    "srt_gen",
    "srt_edit",
    "caption_animate",
    "render_composition",
)

# Valid asset role keys used in recipe asset_roles
RECIPE_ASSET_ROLES: tuple[str, ...] = (
    "primary_audio",
    "subtitle_source",
    "caption_source",
    "background",
)


# ------------------------------------------------------------------
# WorkflowRecipe dataclass
# ------------------------------------------------------------------

@dataclass
class WorkflowRecipe:
    """A reusable workflow template.

    Captures which stages are enabled, what asset roles are expected,
    per-tab settings subsets, preset/layout/lint references, and export
    rules.
    """

    version: int = RECIPE_SCHEMA_VERSION
    name: str = ""
    enabled_stages: dict[str, bool] = field(default_factory=lambda: {
        stage: True for stage in VALID_STAGES
    })
    asset_roles: dict[str, str | None] = field(default_factory=lambda: {
        role: None for role in RECIPE_ASSET_ROLES
    })
    tabs: dict[str, dict] = field(default_factory=dict)
    references: dict[str, str | None] = field(default_factory=lambda: {
        "caption_preset": None,
        "layout_preset": None,
        "lint_profile": None,
    })
    export: dict[str, str | None] = field(default_factory=lambda: {
        "naming_rule": None,
        "target_dir": None,
    })


# ------------------------------------------------------------------
# Recipe storage helpers
# ------------------------------------------------------------------

def get_recipe_library_dir() -> Path:
    """Return the application-data recipe directory, creating it if needed."""
    recipe_dir = get_data_dir() / "recipes"
    recipe_dir.mkdir(parents=True, exist_ok=True)
    return recipe_dir


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------

def validate_recipe(recipe: WorkflowRecipe) -> tuple[bool, str]:
    """Perform basic validation on a recipe.

    Parameters
    ----------
    recipe : WorkflowRecipe
        The recipe to validate.

    Returns
    -------
    tuple[bool, str]
        ``(True, "")`` when valid, ``(False, reason)`` otherwise.
    """
    if not isinstance(recipe, WorkflowRecipe):
        return False, "Recipe is not a WorkflowRecipe instance."

    if not isinstance(recipe.version, int) or recipe.version < 1:
        return False, f"Invalid recipe version: {recipe.version}"

    if not isinstance(recipe.name, str) or not recipe.name.strip():
        return False, "Recipe name must be a non-empty string."

    if not isinstance(recipe.enabled_stages, dict):
        return False, "enabled_stages must be a dict."

    for key in recipe.enabled_stages:
        if key not in VALID_STAGES:
            return False, f"Unknown stage key: {key}"

    if not isinstance(recipe.asset_roles, dict):
        return False, "asset_roles must be a dict."

    if not isinstance(recipe.tabs, dict):
        return False, "tabs must be a dict."

    if not isinstance(recipe.references, dict):
        return False, "references must be a dict."

    if not isinstance(recipe.export, dict):
        return False, "export must be a dict."

    return True, ""


# ------------------------------------------------------------------
# Save / load
# ------------------------------------------------------------------

def save_recipe(recipe: WorkflowRecipe, path: Path) -> bool:
    """Save a recipe as a ``.avrecipe.json`` file.

    Parameters
    ----------
    recipe : WorkflowRecipe
        The recipe to persist.
    path : Path
        Destination file path.  Parent directories are created if absent.

    Returns
    -------
    bool
        ``True`` on success.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(recipe)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Recipe saved to %s", path)
        return True
    except Exception:
        logger.exception("Failed to save recipe to %s", path)
        return False


def load_recipe(path: Path) -> WorkflowRecipe | None:
    """Load a recipe from a ``.avrecipe.json`` file.

    Parameters
    ----------
    path : Path
        Source file path.

    Returns
    -------
    WorkflowRecipe | None
        The loaded recipe, or ``None`` if the file cannot be read.
    """
    if not path.is_file():
        logger.warning("Recipe file not found: %s", path)
        return None

    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception:
        logger.exception("Failed to read recipe from %s", path)
        return None

    if not isinstance(data, dict):
        logger.warning("Recipe file does not contain a JSON object: %s", path)
        return None

    try:
        recipe = WorkflowRecipe(
            version=data.get("version", RECIPE_SCHEMA_VERSION),
            name=data.get("name", ""),
            enabled_stages=data.get("enabled_stages", {s: True for s in VALID_STAGES}),
            asset_roles=data.get("asset_roles", {r: None for r in RECIPE_ASSET_ROLES}),
            tabs=data.get("tabs", {}),
            references=data.get("references", {
                "caption_preset": None,
                "layout_preset": None,
                "lint_profile": None,
            }),
            export=data.get("export", {
                "naming_rule": None,
                "target_dir": None,
            }),
        )
    except Exception:
        logger.exception("Failed to parse recipe from %s", path)
        return None

    logger.info("Recipe loaded from %s: %s", path, recipe.name)
    return recipe


# ------------------------------------------------------------------
# Library management
# ------------------------------------------------------------------

def list_saved_recipes() -> list[dict]:
    """List recipes in the library directory.

    Returns
    -------
    list[dict]
        Each entry contains ``"name"``, ``"path"``, and ``"version"`` keys.
    """
    library_dir = get_recipe_library_dir()
    results: list[dict] = []

    for recipe_path in sorted(library_dir.glob("*.avrecipe.json")):
        try:
            raw = recipe_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            results.append({
                "name": data.get("name", recipe_path.stem),
                "path": str(recipe_path),
                "version": data.get("version", 0),
            })
        except Exception:
            logger.warning("Skipping unreadable recipe: %s", recipe_path)

    return results


# ------------------------------------------------------------------
# Recipe <-> session interaction
# ------------------------------------------------------------------

def create_recipe_from_session(
    tabs: list[Any],
    session_context: SessionContext,
    name: str = "",
) -> WorkflowRecipe:
    """Build a WorkflowRecipe from the current application state.

    Parameters
    ----------
    tabs : list[BaseTab]
        The registered tab instances.
    session_context : SessionContext
        The live session context.
    name : str
        Recipe display name.

    Returns
    -------
    WorkflowRecipe
    """
    enabled_stages: dict[str, bool] = {}
    tab_settings: dict[str, dict] = {}

    for tab in tabs:
        tab_id = tab.tab_id
        if tab_id in VALID_STAGES:
            enabled_stages[tab_id] = True
        tab_settings[tab_id] = tab.collect_settings()

    # Fill missing stages as disabled
    for stage in VALID_STAGES:
        enabled_stages.setdefault(stage, False)

    # Resolve current asset role bindings from session
    asset_roles: dict[str, str | None] = {}
    for role_key in RECIPE_ASSET_ROLES:
        assets = session_context.list_assets(role=role_key)
        if assets:
            asset_roles[role_key] = str(assets[0].path)
        else:
            asset_roles[role_key] = None

    # Extract references from tab settings if available
    references: dict[str, str | None] = {
        "caption_preset": None,
        "layout_preset": None,
        "lint_profile": None,
    }
    srt_edit_settings = tab_settings.get("srt_edit", {})
    if "lint_profile" in srt_edit_settings:
        references["lint_profile"] = srt_edit_settings["lint_profile"]

    export: dict[str, str | None] = {
        "naming_rule": None,
        "target_dir": None,
    }

    return WorkflowRecipe(
        version=RECIPE_SCHEMA_VERSION,
        name=name,
        enabled_stages=enabled_stages,
        asset_roles=asset_roles,
        tabs=tab_settings,
        references=references,
        export=export,
    )


def apply_recipe(
    recipe: WorkflowRecipe,
    tabs: list[Any],
    session_context: SessionContext,
) -> None:
    """Apply a recipe to tabs, resolving asset roles through SessionContext.

    Asset roles are resolved through the session context first; roles that
    cannot be resolved are left as ``None`` (the caller can prompt the user
    for missing bindings separately).

    Parameters
    ----------
    recipe : WorkflowRecipe
        The recipe to apply.
    tabs : list[BaseTab]
        The registered tab instances.
    session_context : SessionContext
        The live session context.
    """
    # Build tab lookup
    tab_map: dict[str, Any] = {tab.tab_id: tab for tab in tabs}

    # Apply per-tab settings
    for tab_id, settings in recipe.tabs.items():
        tab = tab_map.get(tab_id)
        if tab is not None and settings:
            try:
                tab.apply_settings(settings)
                logger.debug("Applied recipe settings to tab '%s'", tab_id)
            except Exception:
                logger.exception(
                    "Failed to apply recipe settings to tab '%s'", tab_id
                )

    # Resolve asset roles: for each recipe role, find a matching asset in
    # the session context or leave the binding as None.
    for role_key, role_path in recipe.asset_roles.items():
        if role_path is None:
            continue

        # Try to find an asset in the session with this role
        existing = session_context.list_assets(role=role_key)
        if existing:
            # Already bound in session — nothing to do
            logger.debug(
                "Asset role '%s' already bound to '%s'",
                role_key,
                existing[0].id,
            )
            continue

        # Check if an asset with the matching path exists
        role_path_obj = Path(role_path)
        all_assets = session_context.list_assets()
        matched = [a for a in all_assets if a.path == role_path_obj]
        if matched:
            session_context.set_role(matched[0].id, role_key)
            logger.debug(
                "Bound asset '%s' to role '%s' from recipe path",
                matched[0].id,
                role_key,
            )
        else:
            logger.info(
                "Recipe role '%s' path '%s' not found in session; "
                "leaving unbound.",
                role_key,
                role_path,
            )
