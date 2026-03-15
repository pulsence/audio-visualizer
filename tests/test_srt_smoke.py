"""Host-level smoke tests for the audio_visualizer.srt package."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from audio_visualizer.events import AppEventEmitter, EventType
from audio_visualizer.srt import ModelManager, transcribe_file
from audio_visualizer.srt.config import PRESETS, apply_overrides
from audio_visualizer.srt.models import ResolvedConfig

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
FIXTURE_AUDIO = ROOT / "tests" / "fixtures" / "srt" / "audio" / "single_sentence.wav"


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


class _FakeModel:
    def transcribe(self, *_args, **_kwargs):
        segment = SimpleNamespace(
            start=0.0,
            end=1.2,
            text="Hello world.",
            words=[
                SimpleNamespace(start=0.0, end=0.5, word="Hello"),
                SimpleNamespace(start=0.5, end=1.2, word="world."),
            ],
        )
        return iter([segment]), SimpleNamespace(language="en")


def _patch_srt_pipeline(monkeypatch) -> None:
    from audio_visualizer.srt.core import pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "ffmpeg_ok", lambda: True)
    monkeypatch.setattr(
        pipeline_module,
        "to_wav_16k_mono",
        lambda _input_path, output_path: Path(output_path).write_bytes(b"RIFFFAKEWAVE"),
    )
    monkeypatch.setattr(pipeline_module, "probe_duration_seconds", lambda _path: 1.2)
    monkeypatch.setattr(pipeline_module, "detect_silences", lambda *_args, **_kwargs: [])


class TestSrtImportSmoke:
    def test_import_srt_package(self):
        import audio_visualizer.srt
        assert hasattr(audio_visualizer.srt, "__all__")

    def test_lazy_loading_no_faster_whisper(self):
        """Importing audio_visualizer.srt should not load faster_whisper."""
        _import_keeps_dependency_unloaded("audio_visualizer.srt", "faster_whisper")

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
        mgr = ModelManager()
        assert not mgr.is_loaded()
        assert mgr.get_model() is None
        assert mgr.model_info() is None

    def test_model_manager_unload_when_not_loaded(self):
        mgr = ModelManager()
        mgr.unload()  # Should not raise


class TestSrtApiSmoke:
    def test_transcribe_file_uses_host_api_and_shared_emitter(self, monkeypatch, tmp_path):
        """The public transcribe_file API should emit shared events and write output."""
        _patch_srt_pipeline(monkeypatch)

        emitter = AppEventEmitter()
        received = []
        emitter.subscribe(received.append)

        output_path = tmp_path / "output.srt"
        result = transcribe_file(
            input_path=FIXTURE_AUDIO,
            output_path=output_path,
            fmt="srt",
            cfg=apply_overrides(ResolvedConfig(), PRESETS["yt"]),
            model=_FakeModel(),
            device_used="cpu",
            compute_type_used="int8",
            emitter=emitter,
        )

        assert result.success is True
        assert output_path.exists()
        assert "Hello world." in output_path.read_text(encoding="utf-8")

        event_types = [event.event_type for event in received]
        assert EventType.JOB_START in event_types
        assert EventType.STAGE in event_types
        assert EventType.PROGRESS in event_types
        assert EventType.JOB_COMPLETE in event_types


class TestSrtMissingBinarySmoke:
    def test_transcribe_file_reports_missing_ffmpeg(self, monkeypatch, tmp_path):
        from audio_visualizer.srt.core import pipeline as pipeline_module

        monkeypatch.setattr(pipeline_module, "ffmpeg_ok", lambda: False)

        result = transcribe_file(
            input_path=FIXTURE_AUDIO,
            output_path=tmp_path / "output.srt",
            fmt="srt",
            cfg=ResolvedConfig(),
            model=_FakeModel(),
            device_used="cpu",
            compute_type_used="int8",
        )

        assert result.success is False
        assert result.error is not None
        assert "ffmpeg" in result.error.lower()
