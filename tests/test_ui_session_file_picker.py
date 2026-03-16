"""Tests for session-aware file-picker path resolution helpers."""

from pathlib import Path

from audio_visualizer.ui.workspaceContext import WorkspaceContext
from audio_visualizer.ui.sessionFilePicker import (
    resolve_browse_directory,
    resolve_output_directory,
)


class TestResolveBrowseDirectory:
    def test_prefers_current_path_parent(self, tmp_path):
        current_file = tmp_path / "nested" / "file.srt"
        current_file.parent.mkdir()
        current_file.touch()

        resolved = resolve_browse_directory(current_path=current_file)

        assert resolved == str(current_file.parent)

    def test_uses_selected_asset_parent_before_project_folder(self, tmp_path):
        ctx = WorkspaceContext()
        project_folder = tmp_path / "project"
        project_folder.mkdir()
        ctx.set_project_folder(project_folder)

        asset_path = tmp_path / "session" / "audio.wav"
        asset_path.parent.mkdir()
        asset_path.touch()

        resolved = resolve_browse_directory(
            workspace_context=ctx,
            selected_asset_path=asset_path,
        )

        assert resolved == str(asset_path.parent)

    def test_falls_back_to_project_folder(self, tmp_path):
        ctx = WorkspaceContext()
        project_folder = tmp_path / "project"
        project_folder.mkdir()
        ctx.set_project_folder(project_folder)

        resolved = resolve_browse_directory(workspace_context=ctx)

        assert resolved == str(project_folder)


class TestResolveOutputDirectory:
    def test_explicit_directory_wins(self, tmp_path):
        explicit = tmp_path / "output"

        resolved = resolve_output_directory(explicit_directory=explicit)

        assert resolved == explicit

    def test_project_folder_wins_over_source_parent(self, tmp_path):
        ctx = WorkspaceContext()
        project_folder = tmp_path / "project"
        project_folder.mkdir()
        ctx.set_project_folder(project_folder)
        source_path = tmp_path / "input" / "clip.mp4"

        resolved = resolve_output_directory(
            workspace_context=ctx,
            source_path=source_path,
        )

        assert resolved == project_folder

    def test_source_parent_is_used_without_project_folder(self, tmp_path):
        source_path = tmp_path / "input" / "clip.mp4"
        source_path.parent.mkdir()
        source_path.touch()

        resolved = resolve_output_directory(source_path=source_path)

        assert resolved == source_path.parent
