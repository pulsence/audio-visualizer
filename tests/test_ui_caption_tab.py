"""Tests for CaptionAnimateTab from audio_visualizer.ui.tabs.captionAnimateTab."""

from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QLineEdit, QWidget

app = QApplication.instance() or QApplication([])

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from audio_visualizer.ui.tabs.captionAnimateTab import CaptionAnimateTab
from audio_visualizer.ui.tabs.baseTab import BaseTab
from audio_visualizer.ui.workspaceContext import SessionAsset, WorkspaceContext


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestCaptionAnimateTabIdentity:
    def test_tab_id(self):
        tab = CaptionAnimateTab()
        assert tab.tab_id == "caption_animate"

    def test_tab_title(self):
        tab = CaptionAnimateTab()
        assert tab.tab_title == "Caption Animate"

    def test_isinstance_base_tab(self):
        tab = CaptionAnimateTab()
        assert isinstance(tab, BaseTab)


class TestCaptionAnimateTabSettings:
    def test_collect_settings_structure(self):
        tab = CaptionAnimateTab()
        settings = tab.collect_settings()

        expected_keys = {
            "subtitle_path",
            "session_subtitle",
            "output_dir",
            "fps",
            "quality",
            "safety_scale",
            "reskin",
            "preset_source",
            "builtin_preset",
            "preset_file",
            "library_preset",
            "font",
            "colors",
            "styling",
            "layout",
            "animation",
            "input_audio_path",
            "mux_audio",
            "audio_reactive",
        }
        assert set(settings.keys()) == expected_keys

        # Font sub-keys
        assert set(settings["font"].keys()) == {"name", "size", "bold", "italic", "file"}

        # Colors sub-keys
        assert set(settings["colors"].keys()) == {"primary", "outline", "shadow"}

        # Styling sub-keys
        assert set(settings["styling"].keys()) == {"outline_px", "shadow_px", "blur_px"}

        # Layout sub-keys
        layout_keys = {
            "line_spacing", "max_width_px", "padding", "alignment",
            "margin_l", "margin_r", "margin_v", "wrap_style",
        }
        assert set(settings["layout"].keys()) == layout_keys

        # Animation sub-keys
        assert set(settings["animation"].keys()) == {"apply", "type", "params"}

        # Audio-reactive sub-keys
        assert set(settings["audio_reactive"].keys()) == {
            "enabled", "audio_path", "session_audio",
        }

    def test_apply_settings_roundtrip(self):
        tab = CaptionAnimateTab()

        custom = {
            "subtitle_path": "/tmp/test.srt",
            "session_subtitle": "(none)",
            "output_dir": "/tmp/output",
            "fps": "60",
            "quality": "large",
            "safety_scale": 1.25,
            "reskin": True,
            "preset_source": "Built-in",
            "builtin_preset": "clean_outline",
            "preset_file": "/tmp/my_preset.json",
            "library_preset": "",
            "font": {
                "name": "Helvetica",
                "size": 48,
                "bold": True,
                "italic": True,
                "file": "/tmp/font.ttf",
            },
            "colors": {
                "primary": "#FF0000",
                "outline": "#00FF00",
                "shadow": "#0000FF",
            },
            "styling": {
                "outline_px": 6.0,
                "shadow_px": 3.5,
                "blur_px": 1.0,
            },
            "layout": {
                "line_spacing": 12,
                "max_width_px": 800,
                "padding": [10, 20, 30, 40],
                "alignment": 5,
                "margin_l": 10,
                "margin_r": 20,
                "margin_v": 30,
                "wrap_style": 1,
            },
            "animation": {
                "apply": False,
                "type": "fade",
                "params": {"in_ms": 200.0, "out_ms": 300.0},
            },
            "mux_audio": True,
            "audio_reactive": {
                "enabled": True,
                "audio_path": "/tmp/audio.mp3",
                "session_audio": "(none)",
            },
        }

        tab.apply_settings(custom)
        restored = tab.collect_settings()

        assert restored["subtitle_path"] == custom["subtitle_path"]
        assert restored["output_dir"] == custom["output_dir"]
        assert restored["fps"] == custom["fps"]
        assert restored["quality"] == custom["quality"]
        assert restored["safety_scale"] == custom["safety_scale"]
        assert restored["reskin"] == custom["reskin"]
        assert restored["preset_file"] == custom["preset_file"]

        assert restored["font"]["name"] == custom["font"]["name"]
        assert restored["font"]["size"] == custom["font"]["size"]
        assert restored["font"]["bold"] == custom["font"]["bold"]
        assert restored["font"]["italic"] == custom["font"]["italic"]
        assert restored["font"]["file"] == custom["font"]["file"]

        assert restored["colors"] == custom["colors"]
        assert restored["styling"]["outline_px"] == custom["styling"]["outline_px"]
        assert restored["styling"]["shadow_px"] == custom["styling"]["shadow_px"]
        assert restored["styling"]["blur_px"] == custom["styling"]["blur_px"]

        assert restored["layout"]["line_spacing"] == custom["layout"]["line_spacing"]
        assert restored["layout"]["max_width_px"] == custom["layout"]["max_width_px"]
        assert restored["layout"]["padding"] == custom["layout"]["padding"]
        assert restored["layout"]["alignment"] == custom["layout"]["alignment"]
        assert restored["layout"]["margin_l"] == custom["layout"]["margin_l"]
        assert restored["layout"]["margin_r"] == custom["layout"]["margin_r"]
        assert restored["layout"]["margin_v"] == custom["layout"]["margin_v"]
        assert restored["layout"]["wrap_style"] == custom["layout"]["wrap_style"]

        assert restored["animation"]["apply"] == custom["animation"]["apply"]
        assert restored["animation"]["type"] == custom["animation"]["type"]
        assert restored["animation"]["params"]["in_ms"] == custom["animation"]["params"]["in_ms"]
        assert restored["animation"]["params"]["out_ms"] == custom["animation"]["params"]["out_ms"]

        assert restored["mux_audio"] == custom["mux_audio"]
        assert restored["audio_reactive"]["enabled"] == custom["audio_reactive"]["enabled"]
        assert restored["audio_reactive"]["audio_path"] == custom["audio_reactive"]["audio_path"]


class TestCaptionAnimateTabValidation:
    def test_validate_empty_fails(self):
        tab = CaptionAnimateTab()
        valid, msg = tab.validate_settings()
        assert valid is False
        assert "subtitle" in msg.lower()

    def test_validate_with_srt_path_passes(self):
        tab = CaptionAnimateTab()
        tab._subtitle_edit.setText("/tmp/test.srt")
        valid, msg = tab.validate_settings()
        assert valid is True
        assert msg == ""

    def test_validate_with_ass_path_passes(self):
        tab = CaptionAnimateTab()
        tab._subtitle_edit.setText("/tmp/test.ass")
        valid, msg = tab.validate_settings()
        assert valid is True
        assert msg == ""

    def test_validate_wrong_extension_fails(self):
        tab = CaptionAnimateTab()
        tab._subtitle_edit.setText("/tmp/test.txt")
        valid, msg = tab.validate_settings()
        assert valid is False
        assert ".srt" in msg or ".ass" in msg

    def test_validate_mux_audio_requires_audio_path(self):
        tab = CaptionAnimateTab()
        tab._subtitle_edit.setText("/tmp/test.srt")
        tab._mux_audio_cb.setChecked(True)

        valid, msg = tab.validate_settings()

        assert valid is False
        assert "audio" in msg.lower()


class _FakeSignal:
    def connect(self, _slot):
        return None


class _FakeCaptionWorker:
    def __init__(self, *, spec, emitter):
        self.spec = spec
        self.emitter = emitter
        self.signals = MagicMock(
            progress=_FakeSignal(),
            stage=_FakeSignal(),
            log=_FakeSignal(),
            completed=_FakeSignal(),
            failed=_FakeSignal(),
            canceled=_FakeSignal(),
        )

    def cancel(self):
        return None


class _FakeCaptionMainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.render_thread_pool = MagicMock()

    def try_start_job(self, _owner_tab_id):
        return True

    def show_job_status(self, *_args):
        return None


class TestCaptionAnimateTabWorkspaceContext:
    def test_set_workspace_context(self):
        tab = CaptionAnimateTab()
        ctx = WorkspaceContext()
        tab.set_workspace_context(ctx)
        assert tab.workspace_context is ctx

    def test_session_subtitle_assets_populate(self):
        tab = CaptionAnimateTab()
        ctx = WorkspaceContext()
        tab.set_workspace_context(ctx)

        # Add a subtitle asset
        ctx.register_asset(SessionAsset(
            id="sub1",
            display_name="test.srt",
            path=Path("/tmp/test.srt"),
            category="subtitle",
            source_tab="srt_gen",
        ))

        # The combo should now have (none) + test.srt
        assert tab._session_subtitle_combo.count() == 2
        assert tab._session_subtitle_combo.itemText(1) == "test.srt"

    def test_session_audio_assets_populate(self):
        tab = CaptionAnimateTab()
        ctx = WorkspaceContext()
        tab.set_workspace_context(ctx)

        ctx.register_asset(SessionAsset(
            id="audio1",
            display_name="music.mp3",
            path=Path("/tmp/music.mp3"),
            category="audio",
            source_tab="audio_visualizer",
        ))

        assert tab._input_session_audio_combo.count() == 2
        assert tab._input_session_audio_combo.itemText(1) == "music.mp3"

    def test_render_defaults_to_project_folder_when_output_dir_blank(self, tmp_path, monkeypatch):
        main_window = _FakeCaptionMainWindow()
        tab = CaptionAnimateTab(main_window)
        ctx = WorkspaceContext()
        project_folder = tmp_path / "project"
        project_folder.mkdir()
        ctx.set_project_folder(project_folder)
        tab.set_workspace_context(ctx)
        tab._subtitle_edit.setText(str(tmp_path / "example.srt"))

        captured = []

        class _CapturingWorker(_FakeCaptionWorker):
            def __init__(self, *, spec, emitter):
                super().__init__(spec=spec, emitter=emitter)
                captured.append(spec)

        monkeypatch.setattr(
            "audio_visualizer.ui.tabs.captionAnimateTab.CaptionRenderWorker",
            _CapturingWorker,
        )

        tab._start_render()

        assert len(captured) == 1
        assert captured[0].output_path.parent == project_folder
        assert captured[0].delivery_output_path.parent == project_folder


class TestCaptionAnimateTabGlobalBusy:
    def test_set_global_busy_disables_start(self):
        tab = CaptionAnimateTab()
        assert tab._start_btn.isEnabled() is True

        tab.set_global_busy(True, owner_tab_id="audio_visualizer")
        assert tab._start_btn.isEnabled() is False

        tab.set_global_busy(False, owner_tab_id="audio_visualizer")
        assert tab._start_btn.isEnabled() is True

    def test_set_global_busy_own_tab_ignored(self):
        tab = CaptionAnimateTab()
        tab.set_global_busy(True, owner_tab_id="caption_animate")
        assert tab._start_btn.isEnabled() is True


class _FakeMainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.completed_calls = []

    def show_job_completed(self, message, output_path=None, owner_tab_id=None):
        self.completed_calls.append((message, output_path, owner_tab_id))

    def update_job_progress(self, percent, message):
        return None

    def update_job_status(self, message):
        return None

    def try_start_job(self, owner_tab_id):
        return True


class TestCaptionAnimateOutputs:
    def test_render_completion_registers_delivery_and_overlay_assets(self, tmp_path):
        main_window = _FakeMainWindow()
        tab = CaptionAnimateTab(main_window)
        ctx = WorkspaceContext()
        tab.set_workspace_context(ctx)
        tab._subtitle_edit.setText(str(tmp_path / "sample.srt"))

        delivery = tmp_path / "sample_caption.mp4"
        overlay = tmp_path / "sample_caption_overlay.mov"
        delivery.write_bytes(b"delivery")
        overlay.write_bytes(b"overlay")

        tab._on_render_completed(
            {
                "output_path": str(delivery),
                "delivery_path": str(delivery),
                "overlay_path": str(overlay),
                "width": 1920,
                "height": 200,
                "duration_ms": 5000,
                "quality": "large",
                "overlay_has_alpha": True,
                "delivery_has_audio": True,
            }
        )

        video_assets = ctx.list_assets(category="video")
        assert len(video_assets) == 2

        delivery_asset = next(asset for asset in video_assets if asset.path == delivery)
        overlay_asset = next(asset for asset in video_assets if asset.path == overlay)

        assert delivery_asset.role is None
        assert delivery_asset.has_audio is True
        assert delivery_asset.metadata["delivery"] is True

        assert overlay_asset.role == "caption_overlay"
        assert overlay_asset.has_alpha is True
        assert overlay_asset.is_overlay_ready is True
        assert overlay_asset.preferred_for_overlay is True


class TestCaptionAnimateTabPresetLoading:
    def test_builtin_preset_combo_populated(self):
        tab = CaptionAnimateTab()
        count = tab._builtin_preset_combo.count()
        assert count >= 2  # At least clean_outline and modern_box

        items = [tab._builtin_preset_combo.itemText(i) for i in range(count)]
        assert "clean_outline" in items
        assert "modern_box" in items

    def test_animation_type_combo_populated(self):
        tab = CaptionAnimateTab()
        count = tab._animation_type_combo.count()
        assert count >= 6  # (none) + at least 5 base types

        items = [tab._animation_type_combo.itemText(i) for i in range(count)]
        assert "(none)" in items
        assert "fade" in items

    def test_collect_preset_config(self):
        tab = CaptionAnimateTab()
        preset = tab._collect_preset_config()
        assert preset.font_name == "Arial"
        assert preset.font_size == 64
        assert isinstance(preset.padding, list)
        assert len(preset.padding) == 4

    def test_apply_preset_to_ui_roundtrip(self):
        from audio_visualizer.caption.core.config import PresetConfig, AnimationConfig

        tab = CaptionAnimateTab()
        preset = PresetConfig(
            font_name="Courier",
            font_size=72,
            bold=True,
            italic=True,
            primary_color="#FF0000",
            outline_color="#00FF00",
            shadow_color="#0000FF",
            outline_px=8.0,
            shadow_px=4.0,
            blur_px=2.0,
            line_spacing=15,
            max_width_px=900,
            padding=[5, 10, 15, 20],
            alignment=5,
            margin_l=5,
            margin_r=10,
            margin_v=15,
            wrap_style=1,
            animation=AnimationConfig(type="fade", params={"in_ms": 200, "out_ms": 300}),
        )

        tab._apply_preset_to_ui(preset)

        assert tab._font_name_edit.text() == "Courier"
        assert tab._font_size_spin.value() == 72
        assert tab._bold_cb.isChecked() is True
        assert tab._italic_cb.isChecked() is True
        assert tab._primary_color_edit.text() == "#FF0000"
        assert tab._outline_px_spin.value() == 8.0
        assert tab._line_spacing_spin.value() == 15
        assert tab._max_width_spin.value() == 900
        assert tab._pad_top_spin.value() == 5
        assert tab._margin_l_spin.value() == 5


class TestMixedAnimationParamWidgets:
    """Verify that animation parameter controls handle numeric, string, and None defaults."""

    def test_fade_creates_only_spin_boxes(self):
        tab = CaptionAnimateTab()
        tab._animation_type_combo.setCurrentText("fade")
        # fade has in_ms and out_ms — both numeric
        assert "in_ms" in tab._anim_param_controls
        assert "out_ms" in tab._anim_param_controls
        assert isinstance(tab._anim_param_controls["in_ms"], QDoubleSpinBox)
        assert isinstance(tab._anim_param_controls["out_ms"], QDoubleSpinBox)

    def test_word_reveal_creates_mixed_controls(self):
        tab = CaptionAnimateTab()
        tab._animation_type_combo.setCurrentText("word_reveal")
        controls = tab._anim_param_controls
        # word_reveal has: mode (str "even"), lead_in_ms (int), min_word_ms (int),
        # max_word_ms (int), unrevealed_color (None)
        assert isinstance(controls["mode"], QLineEdit)
        assert controls["mode"].text() == "even"
        assert isinstance(controls["lead_in_ms"], QDoubleSpinBox)
        assert isinstance(controls["min_word_ms"], QDoubleSpinBox)
        assert isinstance(controls["max_word_ms"], QDoubleSpinBox)
        assert isinstance(controls["unrevealed_color"], QLineEdit)
        # None default results in empty text with placeholder
        assert controls["unrevealed_color"].text() == ""

    def test_none_animation_type_clears_controls(self):
        tab = CaptionAnimateTab()
        tab._animation_type_combo.setCurrentText("fade")
        assert len(tab._anim_param_controls) > 0
        tab._animation_type_combo.setCurrentText("(none)")
        assert len(tab._anim_param_controls) == 0


class TestMixedAnimationParamRoundTrip:
    """Settings round-trip with mixed animation param types."""

    def test_word_reveal_settings_roundtrip(self):
        tab = CaptionAnimateTab()

        custom = {
            "subtitle_path": "/tmp/test.srt",
            "session_subtitle": "(none)",
            "output_dir": "/tmp/output",
            "fps": "30",
            "quality": "small",
            "safety_scale": 1.12,
            "reskin": False,
            "preset_source": "Built-in",
            "builtin_preset": "clean_outline",
            "preset_file": "",
            "library_preset": "",
            "font": {
                "name": "Arial",
                "size": 64,
                "bold": False,
                "italic": False,
                "file": "",
            },
            "colors": {
                "primary": "#FFFFFF",
                "outline": "#000000",
                "shadow": "#000000",
            },
            "styling": {
                "outline_px": 4.0,
                "shadow_px": 2.0,
                "blur_px": 0.0,
            },
            "layout": {
                "line_spacing": 8,
                "max_width_px": 1200,
                "padding": [40, 60, 50, 60],
                "alignment": 2,
                "margin_l": 0,
                "margin_r": 0,
                "margin_v": 0,
                "wrap_style": 2,
            },
            "animation": {
                "apply": True,
                "type": "word_reveal",
                "params": {
                    "mode": "even",
                    "lead_in_ms": 0.0,
                    "min_word_ms": 60.0,
                    "max_word_ms": 400.0,
                    "unrevealed_color": None,
                },
            },
            "mux_audio": False,
            "audio_reactive": {
                "enabled": False,
                "audio_path": "",
                "session_audio": "(none)",
            },
        }

        tab.apply_settings(custom)
        restored = tab.collect_settings()

        assert restored["animation"]["type"] == "word_reveal"
        params = restored["animation"]["params"]
        assert params["mode"] == "even"
        assert params["lead_in_ms"] == 0.0
        assert params["min_word_ms"] == 60.0
        assert params["max_word_ms"] == 400.0
        assert params["unrevealed_color"] is None

    def test_collect_preset_config_with_word_reveal(self):
        tab = CaptionAnimateTab()
        tab._animation_type_combo.setCurrentText("word_reveal")
        preset = tab._collect_preset_config()
        assert preset.animation is not None
        assert preset.animation.type == "word_reveal"
        assert preset.animation.params["mode"] == "even"
        assert preset.animation.params["unrevealed_color"] is None

    def test_string_param_roundtrip_via_preset(self):
        from audio_visualizer.caption.core.config import PresetConfig, AnimationConfig

        tab = CaptionAnimateTab()
        preset = PresetConfig(
            animation=AnimationConfig(
                type="word_reveal",
                params={
                    "mode": "timed",
                    "lead_in_ms": 50,
                    "min_word_ms": 80,
                    "max_word_ms": 500,
                    "unrevealed_color": "#808080",
                },
            ),
        )
        tab._apply_preset_to_ui(preset)

        controls = tab._anim_param_controls
        assert controls["mode"].text() == "timed"
        assert controls["unrevealed_color"].text() == "#808080"
        assert controls["lead_in_ms"].value() == 50.0


class TestGuardedRenderLifecycle:
    """Ensure no crash when _main_window is None (no MainWindow available)."""

    def test_safe_main_window_returns_none_for_bare_tab(self):
        tab = CaptionAnimateTab()
        assert tab._safe_main_window() is None

    def test_safe_main_window_returns_none_for_plain_qwidget_parent(self):
        parent = QWidget()
        tab = CaptionAnimateTab(parent)
        assert tab._safe_main_window() is None

    def test_safe_main_window_returns_fake_main_window(self):
        mw = _FakeMainWindow()
        tab = CaptionAnimateTab(mw)
        assert tab._safe_main_window() is mw

    def test_on_progress_no_crash_without_main_window(self):
        tab = CaptionAnimateTab()
        # Should not raise even though _main_window is None
        tab._on_progress(50.0, "half done", {})
        assert tab._progress_bar.value() == 50
        assert tab._status_label.text() == "half done"

    def test_on_stage_no_crash_without_main_window(self):
        tab = CaptionAnimateTab()
        tab._on_stage("Encoding", 1, 3, {})
        assert tab._status_label.text() == "Encoding"

    def test_on_render_completed_no_crash_without_main_window(self, tmp_path):
        tab = CaptionAnimateTab()
        ctx = WorkspaceContext()
        tab.set_workspace_context(ctx)
        tab._subtitle_edit.setText(str(tmp_path / "sample.srt"))

        delivery = tmp_path / "sample_caption.mp4"
        delivery.write_bytes(b"delivery")

        # Should not raise
        tab._on_render_completed(
            {
                "output_path": str(delivery),
                "delivery_path": str(delivery),
                "width": 1920,
                "height": 200,
                "duration_ms": 5000,
                "quality": "large",
            }
        )
        assert tab._progress_bar.value() == 100
        assert tab._start_btn.isEnabled() is True
        assert tab._cancel_btn.isEnabled() is False

    def test_on_render_failed_no_crash_without_main_window(self):
        tab = CaptionAnimateTab()
        tab._on_render_failed("something went wrong", {})
        assert "Failed" in tab._status_label.text()
        assert tab._start_btn.isEnabled() is True
        assert tab._cancel_btn.isEnabled() is False

    def test_on_render_canceled_no_crash_without_main_window(self):
        tab = CaptionAnimateTab()
        tab._on_render_canceled("user cancelled")
        assert "Cancelled" in tab._status_label.text()
        assert tab._start_btn.isEnabled() is True
        assert tab._cancel_btn.isEnabled() is False

    def test_on_render_failed_resets_preview_state(self):
        tab = CaptionAnimateTab()
        tab._is_preview_render = True
        tab._preview_render_btn.setEnabled(False)
        tab._on_render_failed("something went wrong", {})
        assert tab._is_preview_render is False
        assert tab._preview_render_btn.isEnabled() is True

    def test_on_render_canceled_resets_preview_state(self):
        tab = CaptionAnimateTab()
        tab._is_preview_render = True
        tab._preview_render_btn.setEnabled(False)
        tab._on_render_canceled("user cancelled")
        assert tab._is_preview_render is False
        assert tab._preview_render_btn.isEnabled() is True


class TestCaptionAnimateRenderPreview:
    """Tests for the Render Preview panel."""

    def test_render_preview_section_exists(self):
        tab = CaptionAnimateTab()
        assert hasattr(tab, "_preview_render_btn")
        assert hasattr(tab, "_preview_duration_label")
        assert tab._preview_render_btn.text() == "Render Preview"
        assert "~5 second" in tab._preview_duration_label.text()

    def test_render_preview_initial_state(self):
        tab = CaptionAnimateTab()
        assert tab._is_preview_render is False
        assert tab._preview_temp_dir is None
        assert tab._preview_render_btn.isEnabled() is True

    def test_preview_completed_does_not_register_assets(self, tmp_path):
        tab = CaptionAnimateTab()
        ctx = WorkspaceContext()
        tab.set_workspace_context(ctx)
        tab._subtitle_edit.setText(str(tmp_path / "sample.srt"))

        preview_file = tmp_path / "preview.mp4"
        preview_file.write_bytes(b"preview")

        tab._on_preview_completed(
            {
                "output_path": str(preview_file),
                "width": 1920,
                "height": 200,
                "duration_ms": 5000,
                "quality": "small",
            }
        )

        # No assets should be registered for a preview render
        video_assets = ctx.list_assets(category="video")
        assert len(video_assets) == 0

    def test_preview_completed_updates_status(self, tmp_path):
        tab = CaptionAnimateTab()
        preview_file = tmp_path / "preview.mp4"
        preview_file.write_bytes(b"preview")

        tab._on_preview_completed({"output_path": str(preview_file)})

        assert tab._status_label.text() == "Preview ready"
        assert tab._progress_bar.value() == 100

    def test_preview_completed_resets_button_state(self):
        tab = CaptionAnimateTab()
        tab._start_btn.setEnabled(False)
        tab._preview_render_btn.setEnabled(False)
        tab._cancel_btn.setEnabled(True)
        tab._is_preview_render = True

        tab._on_preview_completed({"output_path": ""})

        assert tab._start_btn.isEnabled() is True
        assert tab._preview_render_btn.isEnabled() is True
        assert tab._cancel_btn.isEnabled() is False
        assert tab._is_preview_render is False

    def test_global_busy_disables_preview_render_btn(self):
        tab = CaptionAnimateTab()
        assert tab._preview_render_btn.isEnabled() is True

        tab.set_global_busy(True, owner_tab_id="audio_visualizer")
        assert tab._preview_render_btn.isEnabled() is False

        tab.set_global_busy(False, owner_tab_id="audio_visualizer")
        assert tab._preview_render_btn.isEnabled() is True

    def test_global_busy_own_tab_does_not_disable_preview_btn(self):
        tab = CaptionAnimateTab()
        tab.set_global_busy(True, owner_tab_id="caption_animate")
        assert tab._preview_render_btn.isEnabled() is True


class TestCaptionAnimatePreviewTempCleanup:
    def test_cleanup_on_rerender(self, tmp_path):
        """Starting a new preview cleans up the previous temp dir."""
        tab = CaptionAnimateTab()
        # Simulate a previous preview temp dir
        old_dir = tmp_path / "caption_preview_old"
        old_dir.mkdir()
        tab._preview_temp_dir = str(old_dir)

        tab._cleanup_preview_temp()

        assert not old_dir.exists()
        assert tab._preview_temp_dir is None

    def test_cleanup_on_failure(self, tmp_path):
        """Preview temp dir is cleaned on render failure when it was a preview."""
        tab = CaptionAnimateTab()
        temp_dir = tmp_path / "caption_preview_fail"
        temp_dir.mkdir()
        tab._preview_temp_dir = str(temp_dir)
        tab._is_preview_render = True

        tab._on_render_failed("test error", {})

        assert not temp_dir.exists()
        assert tab._preview_temp_dir is None

    def test_cleanup_on_cancel(self, tmp_path):
        """Preview temp dir is cleaned on render cancel when it was a preview."""
        tab = CaptionAnimateTab()
        temp_dir = tmp_path / "caption_preview_cancel"
        temp_dir.mkdir()
        tab._preview_temp_dir = str(temp_dir)
        tab._is_preview_render = True

        tab._on_render_canceled("user cancelled")

        assert not temp_dir.exists()
        assert tab._preview_temp_dir is None

    def test_no_cleanup_on_non_preview_failure(self, tmp_path):
        """Preview temp dir is NOT cleaned on failure if it was NOT a preview render."""
        tab = CaptionAnimateTab()
        temp_dir = tmp_path / "caption_preview_keep"
        temp_dir.mkdir()
        tab._preview_temp_dir = str(temp_dir)
        tab._is_preview_render = False

        tab._on_render_failed("test error", {})

        # Should still exist since it wasn't a preview render
        assert temp_dir.exists()

    def test_cleanup_on_close_event(self, tmp_path):
        """Preview temp dir is cleaned on tab close."""
        tab = CaptionAnimateTab()
        temp_dir = tmp_path / "caption_preview_close"
        temp_dir.mkdir()
        tab._preview_temp_dir = str(temp_dir)

        from PySide6.QtGui import QCloseEvent
        event = QCloseEvent()
        tab.closeEvent(event)

        assert not temp_dir.exists()
        assert tab._preview_temp_dir is None

    def test_close_event_stops_preview_media_player(self):
        """Tab teardown stops the preview player when preview playback is available."""
        tab = CaptionAnimateTab()
        tab._preview_available = True
        tab._preview_media_player = MagicMock()

        from PySide6.QtGui import QCloseEvent
        event = QCloseEvent()
        tab.closeEvent(event)

        tab._preview_media_player.stop.assert_called_once()
