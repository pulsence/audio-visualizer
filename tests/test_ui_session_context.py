"""Tests for SessionContext and SessionAsset from audio_visualizer.ui.sessionContext."""

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

import pytest

from audio_visualizer.ui.sessionContext import (
    SessionAsset,
    SessionContext,
    VALID_CATEGORIES,
    VALID_ROLES,
)


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


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestSessionContextAssetCRUD:
    def test_register_asset(self):
        ctx = SessionContext()
        asset = _make_asset()
        ctx.register_asset(asset)
        assert ctx.get_asset("a1") is asset

    def test_register_duplicate_raises(self):
        ctx = SessionContext()
        ctx.register_asset(_make_asset())
        with pytest.raises(ValueError, match="already registered"):
            ctx.register_asset(_make_asset())

    def test_register_invalid_category_raises(self):
        ctx = SessionContext()
        asset = _make_asset(category="bogus_category")
        with pytest.raises(ValueError, match="Invalid category"):
            ctx.register_asset(asset)

    def test_update_asset(self):
        ctx = SessionContext()
        ctx.register_asset(_make_asset())
        ctx.update_asset("a1", display_name="Updated Name", duration_ms=5000)
        asset = ctx.get_asset("a1")
        assert asset is not None
        assert asset.display_name == "Updated Name"
        assert asset.duration_ms == 5000

    def test_update_nonexistent_raises(self):
        ctx = SessionContext()
        with pytest.raises(KeyError, match="No asset with id"):
            ctx.update_asset("nonexistent", display_name="X")

    def test_remove_asset(self):
        ctx = SessionContext()
        ctx.register_asset(_make_asset())
        ctx.remove_asset("a1")
        assert ctx.get_asset("a1") is None

    def test_remove_nonexistent_raises(self):
        ctx = SessionContext()
        with pytest.raises(KeyError, match="No asset with id"):
            ctx.remove_asset("nonexistent")


class TestSessionContextQuery:
    def test_list_assets_no_filter(self):
        ctx = SessionContext()
        ctx.register_asset(_make_asset("a1", category="audio"))
        ctx.register_asset(_make_asset("a2", category="video", path=Path("/tmp/test.mp4")))
        result = ctx.list_assets()
        assert len(result) == 2

    def test_list_assets_by_category(self):
        ctx = SessionContext()
        ctx.register_asset(_make_asset("a1", category="audio"))
        ctx.register_asset(_make_asset("a2", category="video", path=Path("/tmp/test.mp4")))
        result = ctx.list_assets(category="audio")
        assert len(result) == 1
        assert result[0].id == "a1"

    def test_list_assets_by_source_tab(self):
        ctx = SessionContext()
        ctx.register_asset(_make_asset("a1", source_tab="srt"))
        ctx.register_asset(_make_asset("a2", source_tab="caption", path=Path("/tmp/test.mp4"), category="video"))
        result = ctx.list_assets(source_tab="srt")
        assert len(result) == 1
        assert result[0].id == "a1"

    def test_list_assets_by_role(self):
        ctx = SessionContext()
        ctx.register_asset(_make_asset("a1", role="primary_audio"))
        ctx.register_asset(_make_asset("a2", role="background", path=Path("/tmp/bg.png"), category="image"))
        result = ctx.list_assets(role="primary_audio")
        assert len(result) == 1
        assert result[0].id == "a1"

    def test_find_asset_by_path(self):
        ctx = SessionContext()
        asset = _make_asset("a1", path=Path("/tmp/audio.wav"))
        ctx.register_asset(asset)
        assert ctx.find_asset_by_path("/tmp/audio.wav") is asset


class TestSessionContextRoles:
    def test_set_role(self):
        ctx = SessionContext()
        ctx.register_asset(_make_asset())
        ctx.set_role("a1", "primary_audio")
        asset = ctx.get_asset("a1")
        assert asset is not None
        assert asset.role == "primary_audio"

    def test_clear_role(self):
        ctx = SessionContext()
        ctx.register_asset(_make_asset("a1", role="primary_audio"))
        ctx.register_asset(
            _make_asset("a2", role="primary_audio", path=Path("/tmp/other.wav"))
        )
        ctx.clear_role("primary_audio")
        assert ctx.get_asset("a1").role is None
        assert ctx.get_asset("a2").role is None


class TestSessionContextAnalysisCache:
    def test_analysis_cache_store_get(self):
        ctx = SessionContext()
        key = ("a1", "rms", "default")
        ctx.store_analysis(key, {"rms": [0.1, 0.2, 0.3]})
        result = ctx.get_analysis(key)
        assert result == {"rms": [0.1, 0.2, 0.3]}

    def test_analysis_cache_invalidate(self):
        ctx = SessionContext()
        key1 = ("a1", "rms", "default")
        key2 = ("a1", "chroma", "default")
        key3 = ("a2", "rms", "default")
        ctx.store_analysis(key1, "data1")
        ctx.store_analysis(key2, "data2")
        ctx.store_analysis(key3, "data3")
        ctx.invalidate_analysis("a1")
        assert ctx.get_analysis(key1) is None
        assert ctx.get_analysis(key2) is None
        assert ctx.get_analysis(key3) == "data3"

    def test_make_analysis_cache_key_uses_asset_identity(self):
        ctx = SessionContext()
        asset = _make_asset("a1", path=Path("/tmp/audio.wav"))
        ctx.register_asset(asset)
        key = ctx.make_analysis_cache_key(asset, "waveform", "mono")
        assert key[0].startswith("a1:")
        assert key[1:] == ("waveform", "mono")


class TestSessionContextBulk:
    def test_clear_session(self):
        ctx = SessionContext()
        ctx.register_asset(_make_asset("a1"))
        ctx.register_asset(_make_asset("a2", path=Path("/tmp/other.wav")))
        ctx.store_analysis(("a1", "rms", "default"), "data")
        ctx.clear()
        assert ctx.get_asset("a1") is None
        assert ctx.get_asset("a2") is None
        assert ctx.get_analysis(("a1", "rms", "default")) is None


class TestSessionContextSerialization:
    def test_to_dict_from_dict(self):
        ctx = SessionContext()
        asset = _make_asset(
            "a1",
            display_name="My Audio",
            path=Path("/tmp/test.wav"),
            category="audio",
            source_tab="srt",
            role="primary_audio",
        )
        asset.duration_ms = 3000
        asset.metadata = {"key": "value"}
        ctx.register_asset(asset)
        ctx.store_analysis(("a1", "rms", "v1"), [1, 2, 3])

        snapshot = ctx.to_dict()
        assert "analysis_cache" not in snapshot
        assert snapshot["roles"] == {"primary_audio": "a1"}

        # Restore into a fresh context
        ctx2 = SessionContext()
        ctx2.from_dict(snapshot)

        restored = ctx2.get_asset("a1")
        assert restored is not None
        assert restored.display_name == "My Audio"
        assert restored.path == Path("/tmp/test.wav")
        assert restored.category == "audio"
        assert restored.source_tab == "srt"
        assert restored.role == "primary_audio"
        assert restored.duration_ms == 3000
        assert restored.metadata == {"key": "value"}
        assert ctx2.get_analysis(("a1", "rms", "v1")) is None


class TestSessionContextSignals:
    def test_signals_emitted(self):
        ctx = SessionContext()
        added: list[str] = []
        updated: list[str] = []
        removed: list[str] = []

        ctx.asset_added.connect(lambda aid: added.append(aid))
        ctx.asset_updated.connect(lambda aid: updated.append(aid))
        ctx.asset_removed.connect(lambda aid: removed.append(aid))

        # Register triggers asset_added
        ctx.register_asset(_make_asset("a1"))
        assert added == ["a1"]

        # Update triggers asset_updated
        ctx.update_asset("a1", display_name="New Name")
        assert updated == ["a1"]

        # Remove triggers asset_removed
        ctx.remove_asset("a1")
        assert removed == ["a1"]
