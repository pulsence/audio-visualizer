"""Versioned settings schema, migration, and project-file persistence.

Defines the canonical settings structure (version 1) and offers helpers
to load, save, and validate settings files.
"""
from __future__ import annotations

import copy
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Schema version
# ------------------------------------------------------------------

CURRENT_SCHEMA_VERSION = 2

# ------------------------------------------------------------------
# Tab keys (single source of truth)
# ------------------------------------------------------------------

_TAB_KEYS: tuple[str, ...] = (
    "audio_visualizer",
    "srt_gen",
    "srt_edit",
    "caption_animate",
    "render_composition",
    "assets",
    "advanced",
)


# ------------------------------------------------------------------
# Default schema
# ------------------------------------------------------------------

def create_default_schema() -> dict:
    """Return a fresh settings dict at :data:`CURRENT_SCHEMA_VERSION`.

    The structure contains top-level ``version``, ``ui``, ``tabs``, and
    ``session`` sections.  Every tab key starts with an empty dict.
    """
    return {
        "version": CURRENT_SCHEMA_VERSION,
        "app": {
            "theme_mode": "auto",  # "off", "on", "auto"
        },
        "ui": {
            "last_active_tab": "audio_visualizer",
            "window": {
                "width": 1600,
                "height": 1000,
                "maximized": False,
            },
        },
        "tabs": {tab: {} for tab in _TAB_KEYS},
        "session": {
            "assets": [],
            "roles": {},
            "project_folder": None,
        },
    }


# ------------------------------------------------------------------
# Migration
# ------------------------------------------------------------------

def migrate_settings(data: dict) -> dict:
    """Migrate *data* to :data:`CURRENT_SCHEMA_VERSION`.

    If *data* already carries the current version number it is returned
    (deep-copied) as-is with missing sections filled in.

    Pre-Stage-Three settings (no ``"version"`` key) are **rejected**:
    a warning is logged and a clean default schema is returned.  Legacy
    payloads are no longer migrated.

    v1 → v2 migration:
    - Adds the ``"advanced"`` tab key.
    - Rejects composition payloads that lack ``composition_schema_version``
      (pre-center-origin data).

    Parameters
    ----------
    data : dict
        A settings dictionary in any known format.

    Returns
    -------
    dict
        A valid current-version schema.
    """
    data = copy.deepcopy(data)

    if "version" not in data:
        logger.warning(
            "Ignoring pre-Stage-Three settings (no 'version' key). "
            "Falling back to clean default schema."
        )
        return create_default_schema()

    version = data["version"]

    if version < 2:
        data = _migrate_v1_to_v2(data)

    result = _ensure_complete(data)
    return result


def _migrate_v1_to_v2(data: dict) -> dict:
    """Migrate settings from v1 to v2.

    - Adds the ``"advanced"`` tab key.
    - Rejects old composition payloads that lack ``composition_schema_version``.
    """
    logger.info("Migrating settings from v1 to v2.")

    # Add advanced tab key if missing
    tabs = data.get("tabs", {})
    tabs.setdefault("advanced", {})

    # Reject old composition payloads (pre-center-origin)
    comp_data = tabs.get("render_composition", {})
    if comp_data and "composition" in comp_data:
        comp_payload = comp_data["composition"]
        if isinstance(comp_payload, dict) and "composition_schema_version" not in comp_payload:
            logger.warning(
                "Rejecting pre-v0.7.0 composition payload (no composition_schema_version). "
                "Old top-left-origin coordinates are incompatible with center-origin."
            )
            comp_data.pop("composition", None)

    data["version"] = 2
    return data


def _ensure_complete(data: dict) -> dict:
    """Fill in any sections missing from a versioned settings dict.

    This keeps forward-compatible files usable even when new tab keys
    are added in future releases.
    """
    defaults = create_default_schema()

    data.setdefault("app", defaults["app"])
    data.setdefault("ui", defaults["ui"])
    data.setdefault("session", defaults["session"])
    data["session"].setdefault("project_folder", defaults["session"]["project_folder"])

    tabs = data.setdefault("tabs", {})
    for key in _TAB_KEYS:
        tabs.setdefault(key, {})

    return data


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------

def save_settings(data: dict, path: Path) -> bool:
    """Serialize *data* as JSON to *path*.

    Parameters
    ----------
    data : dict
        The settings dictionary to persist.
    path : Path
        Destination file path.  Parent directories are created if they
        do not exist.

    Returns
    -------
    bool
        ``True`` on success, ``False`` if an error occurred.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.debug("Settings saved to %s.", path)
        return True
    except Exception:
        logger.exception("Failed to save settings to %s.", path)
        return False


def load_settings(path: Path) -> dict | None:
    """Load settings from *path*, auto-migrating if necessary.

    Parameters
    ----------
    path : Path
        The JSON settings file to read.

    Returns
    -------
    dict | None
        The loaded (and possibly migrated) settings dict, or ``None``
        if the file does not exist or cannot be parsed.
    """
    if not path.is_file():
        logger.debug("Settings file not found: %s.", path)
        return None

    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception:
        logger.exception("Failed to read settings from %s.", path)
        return None

    if not isinstance(data, dict):
        logger.warning("Settings file does not contain a JSON object: %s.", path)
        return None

    migrated = migrate_settings(data)
    logger.debug("Settings loaded from %s (version %s).", path, migrated.get("version"))
    return migrated


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------

def validate_schema(data: dict) -> bool:
    """Perform basic structural validation on *data*.

    Checks that *data* is a ``dict`` with an integer ``"version"`` key
    and a ``"tabs"`` key whose value is also a ``dict``.

    Parameters
    ----------
    data : dict
        The settings dictionary to validate.

    Returns
    -------
    bool
        ``True`` when the structure passes validation.
    """
    if not isinstance(data, dict):
        return False
    if "version" not in data or not isinstance(data["version"], int):
        return False
    if "tabs" not in data or not isinstance(data["tabs"], dict):
        return False
    return True
