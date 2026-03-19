"""Tests for GeneralSettingsView from audio_visualizer.ui.views.general.generalSettingViews."""

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from audio_visualizer.ui.views.general.generalSettingViews import GeneralSettingsView


class TestVideoPathMp4Append:
    def test_appends_mp4_when_no_extension(self):
        view = GeneralSettingsView()
        view.video_file_path.setText("C:/test/output")
        view._on_video_path_editing_finished()
        assert view.video_file_path.text() == "C:/test/output.mp4"

    def test_preserves_explicit_extension(self):
        view = GeneralSettingsView()
        view.video_file_path.setText("C:/test/output.mov")
        view._on_video_path_editing_finished()
        assert view.video_file_path.text() == "C:/test/output.mov"

    def test_preserves_mp4_extension(self):
        view = GeneralSettingsView()
        view.video_file_path.setText("C:/test/output.mp4")
        view._on_video_path_editing_finished()
        assert view.video_file_path.text() == "C:/test/output.mp4"

    def test_empty_path_unchanged(self):
        view = GeneralSettingsView()
        view.video_file_path.setText("")
        view._on_video_path_editing_finished()
        assert view.video_file_path.text() == ""

    def test_whitespace_only_path_unchanged(self):
        view = GeneralSettingsView()
        view.video_file_path.setText("   ")
        view._on_video_path_editing_finished()
        # Whitespace-only is treated as empty — no .mp4 appended
        assert view.video_file_path.text() == "   "
