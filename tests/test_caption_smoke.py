"""Host-level smoke tests for the audio_visualizer.caption package."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from audio_visualizer.caption import RenderConfig, render_subtitle
from audio_visualizer.events import AppEvent, AppEventEmitter, EventType

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
FIXTURE_SRT = ROOT / "tests" / "fixtures" / "caption" / "sample.srt"


def _import_keeps_dependency_unloaded(module_name: str, dependency_name: str) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        str(SRC) if not env.get("PYTHONPATH") else str(SRC) + os.pathsep + env["PYTHONPATH"]
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                f"import {module_name}; "
                f"print('loaded' if '{dependency_name}' in sys.modules else 'not_loaded')"
            ),
        ],
        check=True,
        capture_output=True,
        cwd=ROOT,
        env=env,
        text=True,
    )
    assert result.stdout.strip() == "not_loaded"


def _patch_caption_renderer(monkeypatch) -> None:
    from audio_visualizer.caption.rendering.ffmpegRenderer import FFmpegRenderer

    monkeypatch.setattr(FFmpegRenderer, "_find_ffmpeg", lambda self: "ffmpeg")

    def fake_render(self, ass_path, output_path, size, fps, duration_sec):
        assert ass_path.exists()
        assert size.width > 0
        assert size.height > 0
        assert fps
        assert duration_sec > 0
        self.emitter.emit(
            AppEvent(
                event_type=EventType.RENDER_START,
                message="Fake FFmpeg render start",
            )
        )
        output_path.write_bytes(b"0" * 2048)
        self.emitter.emit(
            AppEvent(
                event_type=EventType.RENDER_COMPLETE,
                message="Fake FFmpeg render complete",
            )
        )

    monkeypatch.setattr(FFmpegRenderer, "render", fake_render)


class TestCaptionImportSmoke:
    def test_import_caption_package(self):
        import audio_visualizer.caption
        assert hasattr(audio_visualizer.caption, "__all__")

    def test_lazy_loading_no_pysubs2(self):
        """Importing audio_visualizer.caption should not load pysubs2."""
        _import_keeps_dependency_unloaded("audio_visualizer.caption", "pysubs2")

    def test_public_api_surface(self):
        from audio_visualizer.caption import (
            render_subtitle,
            RenderConfig,
            RenderResult,
            list_presets,
            list_animations,
            PresetConfig,
            AnimationConfig,
            SubtitleFile,
            SizeCalculator,
            StyleBuilder,
            FFmpegRenderer,
            PresetLoader,
            AnimationRegistry,
            BaseAnimation,
        )
        assert callable(render_subtitle)
        assert callable(list_presets)
        assert callable(list_animations)


class TestCaptionPresetSmoke:
    def test_builtin_presets_available(self):
        from audio_visualizer.caption.presets.defaults import BUILTIN_PRESETS
        assert "clean_outline" in BUILTIN_PRESETS
        assert "modern_box" in BUILTIN_PRESETS

    def test_preset_config_creation(self):
        from audio_visualizer.caption.core.config import PresetConfig
        config = PresetConfig()
        assert config.font_size > 0

    def test_list_presets(self):
        from audio_visualizer.caption import list_presets
        presets = list_presets()
        assert isinstance(presets, dict)
        assert len(presets) >= 2  # clean_outline, modern_box


class TestCaptionAnimationSmoke:
    def test_animation_registry(self):
        from audio_visualizer.caption.animations import AnimationRegistry
        types = AnimationRegistry.list_types()
        assert isinstance(types, list)
        assert len(types) >= 5  # fade, slide, scale, blur, word_reveal

    def test_list_animations(self):
        from audio_visualizer.caption import list_animations
        animations = list_animations()
        assert isinstance(animations, dict)
        assert len(animations) >= 5


class TestCaptionApiSmoke:
    def test_render_subtitle_uses_host_api_and_shared_emitter(self, monkeypatch, tmp_path):
        _patch_caption_renderer(monkeypatch)

        emitter = AppEventEmitter()
        received = []
        progress_messages = []
        on_events = []
        emitter.subscribe(received.append)

        result = render_subtitle(
            FIXTURE_SRT,
            tmp_path / "overlay.mov",
            config=RenderConfig(preset="modern_box", quality="small"),
            on_progress=progress_messages.append,
            on_event=on_events.append,
            emitter=emitter,
        )

        assert result.success is True
        assert result.output_path is not None
        assert result.output_path.exists()
        assert result.width > 0
        assert result.height > 0
        assert progress_messages
        assert on_events

        event_types = [event.event_type for event in received]
        assert EventType.STAGE in event_types
        assert EventType.RENDER_START in event_types
        assert EventType.RENDER_COMPLETE in event_types


class TestCaptionMissingBinarySmoke:
    def test_render_subtitle_reports_missing_ffmpeg(self, monkeypatch, tmp_path):
        from audio_visualizer.caption.rendering.ffmpegRenderer import FFmpegRenderer

        def raise_missing_ffmpeg(self):
            raise RuntimeError("FFmpeg not found on PATH.")

        monkeypatch.setattr(FFmpegRenderer, "_find_ffmpeg", raise_missing_ffmpeg)

        result = render_subtitle(
            FIXTURE_SRT,
            tmp_path / "overlay.mov",
            config=RenderConfig(preset="clean_outline", quality="small"),
        )

        assert result.success is False
        assert result.error is not None
        assert "ffmpeg" in result.error.lower()
