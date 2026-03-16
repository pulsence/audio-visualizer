"""Session context and cross-tab asset management.

Provides SessionAsset (a dataclass representing a shared media asset) and
SessionContext (a QObject that maintains the live asset registry and an
analysis cache).  Tabs register, query, and update assets through
SessionContext; signals notify other tabs of changes so they can refresh
their views without polling.
"""
from __future__ import annotations

import copy
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from audio_visualizer.ui.mediaProbe import probe_media

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

VALID_CATEGORIES: tuple[str, ...] = (
    "audio",
    "subtitle",
    "video",
    "image",
    "json_bundle",
    "segments",
    "transcript",
    "config",
    "preset",
)

VALID_ROLES: tuple[str, ...] = (
    "primary_audio",
    "subtitle_source",
    "caption_source",
    "caption_overlay",
    "visualizer_output",
    "background",
    "final_render",
)

_IMPORTABLE_EXTENSIONS: dict[str, str] = {
    ".mp3": "audio",
    ".wav": "audio",
    ".flac": "audio",
    ".ogg": "audio",
    ".m4a": "audio",
    ".aac": "audio",
    ".wma": "audio",
    ".mp4": "video",
    ".mkv": "video",
    ".webm": "video",
    ".avi": "video",
    ".mov": "video",
    ".mxf": "video",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".bmp": "image",
    ".tiff": "image",
    ".srt": "subtitle",
    ".ass": "subtitle",
    ".vtt": "subtitle",
    ".json": "json_bundle",
}


# ------------------------------------------------------------------
# SessionAsset dataclass
# ------------------------------------------------------------------

@dataclass
class SessionAsset:
    """A single shared asset that any tab can reference.

    Attributes
    ----------
    id : str
        Unique identifier for the asset (typically a UUID or slug).
    display_name : str
        Human-readable label shown in the UI.
    path : Path
        Filesystem location of the asset.
    category : str
        One of :data:`VALID_CATEGORIES`.
    source_tab : str | None
        The tab that originally registered this asset.
    role : str | None
        Semantic role (see :data:`VALID_ROLES` for common values).
    width : int | None
        Pixel width (video / image assets).
    height : int | None
        Pixel height (video / image assets).
    fps : float | None
        Frame rate (video assets).
    duration_ms : int | None
        Duration in milliseconds.
    has_alpha : bool | None
        Whether the asset contains an alpha channel.
    has_audio : bool | None
        Whether the asset contains an audio stream.
    is_overlay_ready : bool | None
        Whether the asset is ready for overlay compositing.
    preferred_for_overlay : bool | None
        Whether the asset should be preferred when selecting an overlay.
    metadata : dict[str, object]
        Arbitrary extra data attached by the producing tab.
    """

    id: str
    display_name: str
    path: Path
    category: str
    source_tab: str | None = None
    role: str | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    duration_ms: int | None = None
    has_alpha: bool | None = None
    has_audio: bool | None = None
    is_overlay_ready: bool | None = None
    preferred_for_overlay: bool | None = None
    metadata: dict[str, object] = field(default_factory=dict)


# ------------------------------------------------------------------
# SessionContext QObject
# ------------------------------------------------------------------

class SessionContext(QObject):
    """Central registry of shared assets and cached analysis results.

    Every tab holds a reference to the same ``SessionContext`` instance.
    Assets are registered, queried, and mutated through this object; Qt
    signals propagate changes to any connected listener.

    Signals
    -------
    asset_added(str)
        Emitted after a new asset is registered.  Payload is the asset id.
    asset_updated(str)
        Emitted after an existing asset is modified.  Payload is the asset id.
    asset_removed(str)
        Emitted after an asset is removed.  Payload is the asset id.
    cache_invalidated(str)
        Emitted when cached analysis entries for an asset are purged.
        Payload is the asset id.
    """

    asset_added = Signal(str)
    asset_updated = Signal(str)
    asset_removed = Signal(str)
    cache_invalidated = Signal(str)
    project_folder_changed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._assets: dict[str, SessionAsset] = {}
        # Keyed by (asset_identity, analysis_type, settings_signature)
        self._analysis_cache: dict[tuple, object] = {}
        self._project_folder: Path | None = None

    # -- project folder --------------------------------------------

    @property
    def project_folder(self) -> Path | None:
        """Return the current project folder, or ``None`` if not set."""
        return self._project_folder

    def set_project_folder(self, path: Path | str | None) -> None:
        """Set the project folder used as a default browse directory.

        Parameters
        ----------
        path : Path | str | None
            Filesystem directory to use.  An empty or whitespace-only string
            is treated as ``None``.
        """
        if path is not None and isinstance(path, str):
            path = Path(path) if path.strip() else None
        self._project_folder = path
        self.project_folder_changed.emit(str(path) if path else "")
        logger.debug("Project folder set: %s", path)

    def import_asset_file(
        self,
        path: Path | str,
        *,
        source_tab: str = "assets",
    ) -> SessionAsset | None:
        """Import a single external asset into the session.

        Returns the existing asset when the resolved path is already
        registered, the new asset on success, or ``None`` for an
        unsupported/nonexistent path.
        """
        asset_path = Path(path)
        if not asset_path.is_file():
            return None

        existing = self.find_asset_by_path(asset_path)
        if existing is not None:
            return existing

        category = _IMPORTABLE_EXTENSIONS.get(asset_path.suffix.lower())
        if category is None:
            return None

        probe = None
        if category in {"audio", "video", "image"}:
            probe = probe_media(asset_path)

        metadata = {}
        if probe is not None:
            for key in ("codec_name", "pix_fmt"):
                value = probe.get(key)
                if value is not None:
                    metadata[key] = value

        asset = SessionAsset(
            id=str(uuid.uuid4()),
            display_name=asset_path.name,
            path=asset_path,
            category=category,
            source_tab=source_tab,
            width=probe.get("width") if probe else None,
            height=probe.get("height") if probe else None,
            fps=probe.get("fps") if probe else None,
            duration_ms=probe.get("duration_ms") if probe else None,
            has_alpha=probe.get("has_alpha") if probe else None,
            has_audio=probe.get("has_audio") if probe else None,
            metadata=metadata,
        )
        self.register_asset(asset)
        return asset

    def import_asset_folder(
        self,
        folder: Path | str,
        *,
        source_tab: str = "assets",
    ) -> list[SessionAsset]:
        """Import supported files from a folder tree into the session."""
        root = Path(folder)
        if not root.is_dir():
            return []

        imported: list[SessionAsset] = []
        for item in sorted(root.rglob("*")):
            if not item.is_file():
                continue
            asset = self.import_asset_file(item, source_tab=source_tab)
            if asset is not None:
                imported.append(asset)
        return imported

    # -- asset CRUD ------------------------------------------------

    def register_asset(self, asset: SessionAsset) -> None:
        """Add a new asset to the registry.

        Parameters
        ----------
        asset : SessionAsset
            The asset to register.  Its ``category`` must be one of
            :data:`VALID_CATEGORIES`.

        Raises
        ------
        ValueError
            If ``asset.category`` is not valid or ``asset.id`` is already
            registered.
        """
        if asset.category not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category '{asset.category}'. "
                f"Must be one of {VALID_CATEGORIES}."
            )
        if asset.id in self._assets:
            raise ValueError(
                f"Asset with id '{asset.id}' is already registered. "
                "Use update_asset() to modify it."
            )
        self._assets[asset.id] = asset
        logger.debug("Asset registered: %s (%s)", asset.id, asset.category)
        self.asset_added.emit(asset.id)

    def update_asset(self, asset_id: str, **kwargs: object) -> None:
        """Modify fields on an existing asset.

        Parameters
        ----------
        asset_id : str
            The id of the asset to update.
        **kwargs
            Field names and their new values.

        Raises
        ------
        KeyError
            If no asset with *asset_id* exists.
        AttributeError
            If a keyword does not correspond to a ``SessionAsset`` field.
        ValueError
            If *category* is supplied and not in :data:`VALID_CATEGORIES`.
        """
        asset = self._assets.get(asset_id)
        if asset is None:
            raise KeyError(f"No asset with id '{asset_id}'.")
        if "category" in kwargs and kwargs["category"] not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category '{kwargs['category']}'. "
                f"Must be one of {VALID_CATEGORIES}."
            )
        for attr, value in kwargs.items():
            if not hasattr(asset, attr):
                raise AttributeError(
                    f"SessionAsset has no field '{attr}'."
                )
            setattr(asset, attr, value)
        logger.debug("Asset updated: %s (fields: %s)", asset_id, list(kwargs))
        self.asset_updated.emit(asset_id)

    def remove_asset(self, asset_id: str) -> None:
        """Remove an asset from the registry.

        Also purges any analysis-cache entries whose key references the
        asset's identity.

        Parameters
        ----------
        asset_id : str
            The id of the asset to remove.

        Raises
        ------
        KeyError
            If no asset with *asset_id* exists.
        """
        if asset_id not in self._assets:
            raise KeyError(f"No asset with id '{asset_id}'.")
        del self._assets[asset_id]
        self._purge_analysis_for(asset_id)
        logger.debug("Asset removed: %s", asset_id)
        self.asset_removed.emit(asset_id)

    def get_asset(self, asset_id: str) -> SessionAsset | None:
        """Return the asset with *asset_id*, or ``None`` if not found."""
        return self._assets.get(asset_id)

    def find_asset_by_path(self, path: str | Path) -> SessionAsset | None:
        """Return the asset whose path matches *path*, or ``None``.

        Path matching uses resolved absolute paths where possible so tabs can
        look up session assets from user-selected filesystem paths without
        depending on the original registration object.
        """
        needle = Path(path)
        try:
            needle = needle.resolve()
        except OSError:
            needle = needle.absolute()

        for asset in self._assets.values():
            try:
                asset_path = asset.path.resolve()
            except OSError:
                asset_path = asset.path.absolute()
            if asset_path == needle:
                return asset
        return None

    def make_analysis_cache_key(
        self,
        asset_or_path: SessionAsset | str | Path,
        analysis_type: str,
        settings_signature: str,
    ) -> tuple[str, str, str]:
        """Build a stable analysis-cache key for an asset or raw path."""
        if isinstance(asset_or_path, SessionAsset):
            asset = asset_or_path
        else:
            asset = self.find_asset_by_path(Path(asset_or_path))

        if asset is not None:
            asset_identity = f"{asset.id}:{asset.path.resolve()}"
        else:
            path = Path(asset_or_path)
            try:
                resolved = path.resolve()
            except OSError:
                resolved = path.absolute()
            asset_identity = f"path:{resolved}"

        return (asset_identity, analysis_type, settings_signature)

    # -- querying --------------------------------------------------

    def list_assets(
        self,
        category: str | None = None,
        source_tab: str | None = None,
        role: str | None = None,
    ) -> list[SessionAsset]:
        """Return assets matching the given filters.

        All supplied filters are AND-combined.  Omitted filters are
        ignored (i.e., calling with no arguments returns every asset).

        Parameters
        ----------
        category : str | None
            If provided, only assets in this category.
        source_tab : str | None
            If provided, only assets originating from this tab.
        role : str | None
            If provided, only assets with this role.

        Returns
        -------
        list[SessionAsset]
        """
        results: list[SessionAsset] = []
        for asset in self._assets.values():
            if category is not None and asset.category != category:
                continue
            if source_tab is not None and asset.source_tab != source_tab:
                continue
            if role is not None and asset.role != role:
                continue
            results.append(asset)
        return results

    def get_assets_by_role(self, role: str) -> list[SessionAsset]:
        """Convenience shortcut for ``list_assets(role=role)``."""
        return self.list_assets(role=role)

    # -- role management -------------------------------------------

    def set_role(self, asset_id: str, role: str) -> None:
        """Assign *role* to the asset identified by *asset_id*.

        Parameters
        ----------
        asset_id : str
            The id of the asset.
        role : str
            The role to assign.

        Raises
        ------
        KeyError
            If no asset with *asset_id* exists.
        """
        self.update_asset(asset_id, role=role)

    def clear_role(self, role: str) -> None:
        """Remove *role* from every asset that currently holds it.

        Parameters
        ----------
        role : str
            The role to clear across all assets.
        """
        for asset in list(self._assets.values()):
            if asset.role == role:
                asset.role = None
                logger.debug(
                    "Cleared role '%s' from asset '%s'.", role, asset.id
                )
                self.asset_updated.emit(asset.id)

    # -- analysis cache --------------------------------------------

    def store_analysis(self, key: tuple, data: object) -> None:
        """Store an analysis result in the cache.

        Parameters
        ----------
        key : tuple
            A ``(asset_identity, analysis_type, settings_signature)``
            triple that uniquely identifies the analysis.
        data : object
            The analysis payload to cache.
        """
        self._analysis_cache[key] = data
        logger.debug("Analysis cached: %s", key)

    def get_analysis(self, key: tuple) -> object | None:
        """Retrieve a cached analysis result.

        Parameters
        ----------
        key : tuple
            The cache key originally passed to :meth:`store_analysis`.

        Returns
        -------
        object | None
            The cached data, or ``None`` if the key is absent.
        """
        return self._analysis_cache.get(key)

    def invalidate_analysis(self, asset_id: str) -> None:
        """Purge all cached analysis entries for *asset_id*.

        Any cache key whose first element equals *asset_id* is removed.
        Emits :attr:`cache_invalidated` with the asset id.

        Parameters
        ----------
        asset_id : str
            The asset identity component of the cache key.
        """
        self._purge_analysis_for(asset_id)
        logger.debug("Analysis invalidated for asset: %s", asset_id)
        self.cache_invalidated.emit(asset_id)

    # -- bulk operations -------------------------------------------

    def clear(self) -> None:
        """Remove all assets and purge the entire analysis cache."""
        asset_ids = list(self._assets.keys())
        self._assets.clear()
        self._analysis_cache.clear()
        if self._project_folder is not None:
            self._project_folder = None
            self.project_folder_changed.emit("")
        for asset_id in asset_ids:
            self.asset_removed.emit(asset_id)
        logger.debug("Session cleared (%d assets removed).", len(asset_ids))

    # -- serialization ---------------------------------------------

    def to_dict(self) -> dict:
        """Serialize the session state to a plain dictionary.

        Returns
        -------
        dict
            A JSON-compatible dictionary with ``"assets"`` and ``"roles"``
            keys.  The live analysis cache is intentionally excluded from
            persisted state because it is session-ephemeral and may contain
            in-memory objects that are not JSON-serializable.
        """
        assets_out: list[dict] = []
        for asset in self._assets.values():
            asset_dict: dict = {
                "id": asset.id,
                "display_name": asset.display_name,
                "path": str(asset.path),
                "category": asset.category,
                "source_tab": asset.source_tab,
                "role": asset.role,
                "width": asset.width,
                "height": asset.height,
                "fps": asset.fps,
                "duration_ms": asset.duration_ms,
                "has_alpha": asset.has_alpha,
                "has_audio": asset.has_audio,
                "is_overlay_ready": asset.is_overlay_ready,
                "preferred_for_overlay": asset.preferred_for_overlay,
                "metadata": asset.metadata,
            }
            assets_out.append(asset_dict)

        roles_out = {
            asset.role: asset.id
            for asset in self._assets.values()
            if asset.role
        }

        return {
            "assets": assets_out,
            "roles": roles_out,
            "project_folder": str(self._project_folder) if self._project_folder else None,
        }

    def from_dict(self, data: dict) -> None:
        """Restore session state from a dictionary produced by :meth:`to_dict`.

        Existing state is cleared before loading.  Signals are emitted
        for each restored asset.

        Parameters
        ----------
        data : dict
            A dictionary previously returned by :meth:`to_dict`.
        """
        self.clear()

        for asset_dict in data.get("assets", []):
            asset = SessionAsset(
                id=asset_dict["id"],
                display_name=asset_dict["display_name"],
                path=Path(asset_dict["path"]),
                category=asset_dict["category"],
                source_tab=asset_dict.get("source_tab"),
                role=asset_dict.get("role"),
                width=asset_dict.get("width"),
                height=asset_dict.get("height"),
                fps=asset_dict.get("fps"),
                duration_ms=asset_dict.get("duration_ms"),
                has_alpha=asset_dict.get("has_alpha"),
                has_audio=asset_dict.get("has_audio"),
                is_overlay_ready=asset_dict.get("is_overlay_ready"),
                preferred_for_overlay=asset_dict.get("preferred_for_overlay"),
                metadata=asset_dict.get("metadata", {}),
            )
            self._assets[asset.id] = asset
            self.asset_added.emit(asset.id)

        for role, asset_id in data.get("roles", {}).items():
            asset = self._assets.get(asset_id)
            if asset is not None:
                asset.role = role

        pf = data.get("project_folder")
        self._project_folder = Path(pf) if pf else None

        logger.debug(
            "Session restored: %d assets.",
            len(self._assets),
        )

    # -- internal helpers ------------------------------------------

    def _purge_analysis_for(self, asset_id: str) -> None:
        """Remove cache entries whose first key element matches *asset_id*."""
        to_remove = [k for k in self._analysis_cache if k and k[0] == asset_id]
        for key in to_remove:
            del self._analysis_cache[key]
