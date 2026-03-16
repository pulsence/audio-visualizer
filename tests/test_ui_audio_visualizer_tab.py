"""Tests for the Audio Visualizer tab."""
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QWidget

app = QApplication.instance() or QApplication([])

from audio_visualizer.ui.tabs.audioVisualizerTab import AudioVisualizerTab
from audio_visualizer.ui.workspaceContext import WorkspaceContext
from audio_visualizer.ui.tabs.baseTab import BaseTab


class TestAudioVisualizerTabIdentity:

    def test_tab_id(self):
        tab = AudioVisualizerTab()
        assert tab.tab_id == "audio_visualizer"

    def test_tab_title(self):
        tab = AudioVisualizerTab()
        assert tab.tab_title == "Audio Visualizer"

    def test_is_base_tab(self):
        tab = AudioVisualizerTab()
        assert isinstance(tab, BaseTab)


class TestAudioVisualizerTabSettings:

    def test_collect_settings_returns_dict(self):
        tab = AudioVisualizerTab()
        settings = tab.collect_settings()
        assert isinstance(settings, dict)
        assert "general" in settings
        assert "visualizer" in settings
        assert "specific" in settings

    def test_validate_settings_returns_tuple(self):
        tab = AudioVisualizerTab()
        result = tab.validate_settings()
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)

    def test_apply_settings_roundtrip(self):
        tab = AudioVisualizerTab()
        original = tab.collect_settings()
        # Apply and re-collect
        tab.apply_settings(original)
        restored = tab.collect_settings()
        # General settings should match
        assert original["general"]["fps"] == restored["general"]["fps"]
        assert original["general"]["video_width"] == restored["general"]["video_width"]
        assert original["visualizer"]["visualizer_type"] == restored["visualizer"]["visualizer_type"]


class TestAudioVisualizerTabVisualizerRegistry:

    def test_view_attribute_map_has_14_entries(self):
        assert len(AudioVisualizerTab._VIEW_ATTRIBUTE_MAP) == 14

    def test_get_visualizer_view_lazy_loads(self):
        tab = AudioVisualizerTab()
        from audio_visualizer.visualizers.utilities import VisualizerOptions
        view = tab._get_visualizer_view(VisualizerOptions.VOLUME_RECTANGLE)
        assert view is not None
        # Second call should return same instance
        view2 = tab._get_visualizer_view(VisualizerOptions.VOLUME_RECTANGLE)
        assert view is view2

    def test_visualizer_selection_changed(self):
        tab = AudioVisualizerTab()
        # Should not raise
        tab.visualizer_selection_changed("Volume: Circle")


class TestAudioVisualizerTabWorkspaceContext:

    def test_workspace_context_injection(self):
        tab = AudioVisualizerTab()
        ctx = WorkspaceContext()
        tab.set_workspace_context(ctx)
        assert tab.workspace_context is ctx
        assert tab.generalSettingsView.workspace_context is ctx


class TestAudioVisualizerTabGlobalBusy:

    def test_set_global_busy_disables_render(self):
        tab = AudioVisualizerTab()
        tab.set_global_busy(True, "srt_gen")
        assert not tab.render_button.isEnabled()

    def test_set_global_busy_false_enables_render(self):
        tab = AudioVisualizerTab()
        tab.set_global_busy(True, "srt_gen")
        tab.set_global_busy(False, None)
        assert tab.render_button.isEnabled()


class _FakeMainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.completed_calls = []

    def show_job_completed(self, message, output_path=None, owner_tab_id=None):
        self.completed_calls.append((message, output_path, owner_tab_id))


class TestAudioVisualizerRenderCompletion:
    def test_render_finished_always_uses_global_completion_state(self, monkeypatch):
        main_window = _FakeMainWindow()
        tab = AudioVisualizerTab(main_window)
        tab._active_preview = False
        tab._show_output_for_last_render = False

        registered = []
        monkeypatch.setattr(tab, "_register_render_asset", lambda video_data: registered.append(video_data))

        class _VideoData:
            file_path = "/tmp/output.mp4"

        tab.render_finished(_VideoData())

        assert registered
        assert main_window.completed_calls == [
            ("Render complete.", "/tmp/output.mp4", "audio_visualizer")
        ]
