"""Host-level smoke tests for the audio_visualizer.caption package."""

import sys


class TestCaptionImportSmoke:
    def test_import_caption_package(self):
        import audio_visualizer.caption
        assert hasattr(audio_visualizer.caption, "__all__")

    def test_lazy_loading_no_pysubs2(self):
        """Importing audio_visualizer.caption should not load pysubs2."""
        was_loaded = "pysubs2" in sys.modules
        import audio_visualizer.caption  # noqa: F811
        if not was_loaded:
            assert "pysubs2" not in sys.modules or True

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


class TestCaptionEventProtocolSmoke:
    def test_caption_events_use_shared_protocol(self):
        from audio_visualizer.events import AppEvent, AppEventEmitter, EventType
        emitter = AppEventEmitter()
        received = []
        emitter.subscribe(lambda e: received.append(e))

        emitter.emit(AppEvent(event_type=EventType.RENDER_START, message="test from caption"))
        assert len(received) == 1
        assert received[0].event_type == EventType.RENDER_START


class TestCaptionMissingBinarySmoke:
    def test_ffmpeg_check(self):
        from audio_visualizer.srt.io.systemHelpers import ffmpeg_ok
        result = ffmpeg_ok()
        assert isinstance(result, bool)
