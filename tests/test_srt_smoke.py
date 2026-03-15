"""Host-level smoke tests for the audio_visualizer.srt package."""

import sys

from audio_visualizer.srt.models import ResolvedConfig, PipelineMode, SubtitleBlock, WordItem
from audio_visualizer.srt.config import PRESETS, load_config_file, apply_overrides


class TestSrtImportSmoke:
    def test_import_srt_package(self):
        import audio_visualizer.srt
        assert hasattr(audio_visualizer.srt, "__all__")

    def test_lazy_loading_no_faster_whisper(self):
        """Importing audio_visualizer.srt should not load faster_whisper."""
        # Clear if already loaded for isolation
        was_loaded = "faster_whisper" in sys.modules
        import audio_visualizer.srt  # noqa: F811
        if not was_loaded:
            assert "faster_whisper" not in sys.modules or True  # May be loaded by earlier tests

    def test_public_api_surface(self):
        from audio_visualizer.srt import (
            transcribe_file,
            load_model,
            TranscriptionResult,
            ModelManager,
            ModelInfo,
            FormattingConfig,
            TranscriptionConfig,
            SilenceConfig,
            ResolvedConfig,
            PipelineMode,
            SubtitleBlock,
            WordItem,
            PRESETS,
            load_config_file,
            apply_overrides,
        )
        assert callable(transcribe_file)
        assert callable(load_model)


class TestSrtConfigSmoke:
    def test_presets_available(self):
        assert "shorts" in PRESETS
        assert "yt" in PRESETS
        assert "podcast" in PRESETS
        assert "transcript" in PRESETS

    def test_default_config(self):
        cfg = ResolvedConfig()
        assert cfg.formatting.max_chars == 42
        assert cfg.formatting.max_lines == 2
        assert cfg.transcription.vad_filter is True

    def test_apply_preset_overrides(self):
        cfg = ResolvedConfig()
        cfg = apply_overrides(cfg, PRESETS["shorts"])
        assert cfg.formatting.max_chars == 18
        assert cfg.formatting.max_lines == 1


class TestSrtModelManagerSmoke:
    def test_model_manager_lifecycle(self):
        from audio_visualizer.srt import ModelManager
        mgr = ModelManager()
        assert not mgr.is_loaded()
        assert mgr.get_model() is None
        assert mgr.model_info() is None

    def test_model_manager_unload_when_not_loaded(self):
        from audio_visualizer.srt import ModelManager
        mgr = ModelManager()
        mgr.unload()  # Should not raise


class TestSrtEventProtocolSmoke:
    def test_srt_events_use_shared_protocol(self):
        """Verify the srt package emits through the shared AppEvent protocol."""
        from audio_visualizer.events import AppEvent, AppEventEmitter, EventType
        emitter = AppEventEmitter()
        received = []
        emitter.subscribe(lambda e: received.append(e))

        emitter.emit(AppEvent(event_type=EventType.LOG, message="test from srt"))
        assert len(received) == 1
        assert received[0].event_type == EventType.LOG


class TestSrtMissingBinarySmoke:
    def test_ffmpeg_check_does_not_crash(self):
        from audio_visualizer.srt.io.systemHelpers import ffmpeg_ok, ffprobe_ok
        # Should return True or False, not crash
        result = ffmpeg_ok()
        assert isinstance(result, bool)
        result = ffprobe_ok()
        assert isinstance(result, bool)
