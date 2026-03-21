"""Tests for AssetsTab from audio_visualizer.ui.tabs.assetsTab."""

from pathlib import Path

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

import pytest

from audio_visualizer.ui.tabs.assetsTab import AssetsTab
from audio_visualizer.ui.workspaceContext import SessionAsset, WorkspaceContext


@pytest.fixture
def ctx():
    return WorkspaceContext()


@pytest.fixture
def tab(ctx):
    t = AssetsTab()
    t.set_workspace_context(ctx)
    return t


class TestAssetsTabIdentity:
    def test_tab_id(self, tab):
        assert tab.tab_id == "assets"

    def test_tab_title(self, tab):
        assert tab.tab_title == "Assets"


class TestAssetsTabRefresh:
    def test_empty_table_on_init(self, tab):
        assert tab._asset_table.rowCount() == 0

    def test_table_updates_on_asset_added(self, tab, ctx):
        ctx.register_asset(SessionAsset(
            id="test-1",
            display_name="test.mp3",
            path=Path("/tmp/test.mp3"),
            category="audio",
        ))
        assert tab._asset_table.rowCount() == 1
        assert tab._asset_table.item(0, 0).text() == "test.mp3"

    def test_table_updates_on_asset_removed(self, tab, ctx):
        ctx.register_asset(SessionAsset(
            id="test-1",
            display_name="test.mp3",
            path=Path("/tmp/test.mp3"),
            category="audio",
        ))
        assert tab._asset_table.rowCount() == 1
        ctx.remove_asset("test-1")
        assert tab._asset_table.rowCount() == 0


class TestAssetsTabImport:
    def test_import_single_file(self, tab, ctx, tmp_path):
        test_file = tmp_path / "song.mp3"
        test_file.touch()
        tab._import_single_file(test_file)
        assets = ctx.list_assets()
        assert len(assets) == 1
        assert assets[0].category == "audio"

    def test_import_deduplicates(self, tab, ctx, tmp_path):
        test_file = tmp_path / "song.mp3"
        test_file.touch()
        tab._import_single_file(test_file)
        tab._import_single_file(test_file)
        assert len(ctx.list_assets()) == 1

    def test_scan_folder(self, tab, ctx, tmp_path):
        (tmp_path / "a.mp3").touch()
        (tmp_path / "b.wav").touch()
        (tmp_path / "c.txt").touch()  # unsupported
        tab._scan_and_import_folder(tmp_path)
        assert len(ctx.list_assets()) == 2


class TestAssetsTabSettings:
    def test_collect_settings(self, tab):
        tab._imported_sources = ["/some/path"]
        s = tab.collect_settings()
        assert s["imported_sources"] == ["/some/path"]

    def test_apply_settings(self, tab):
        tab.apply_settings({"imported_sources": ["/a", "/b"]})
        assert tab._imported_sources == ["/a", "/b"]

    def test_apply_settings_defaults_empty_when_key_missing(self, tab):
        tab.apply_settings({})
        assert tab._imported_sources == []
