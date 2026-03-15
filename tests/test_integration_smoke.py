"""Cross-package integration smoke tests.

Tests the shared event protocol works end-to-end with the logging bridge
and verifies both packages can coexist.
"""

import logging
from pathlib import Path
from types import SimpleNamespace

from audio_visualizer.caption import RenderConfig, render_subtitle
from audio_visualizer.events import (
    AppEvent,
    AppEventEmitter,
    EventLevel,
    EventType,
    LoggingBridge,
)
from audio_visualizer.srt import transcribe_file
from audio_visualizer.srt.models import ResolvedConfig

ROOT = Path(__file__).resolve().parents[1]
SRT_FIXTURE = ROOT / "tests" / "fixtures" / "srt" / "audio" / "single_sentence.wav"
CAPTION_FIXTURE = ROOT / "tests" / "fixtures" / "caption" / "sample.srt"


class _FakeSrtModel:
    def transcribe(self, *_args, **_kwargs):
        segment = SimpleNamespace(
            start=0.0,
            end=1.0,
            text="Integration smoke.",
            words=[
                SimpleNamespace(start=0.0, end=0.45, word="Integration"),
                SimpleNamespace(start=0.45, end=1.0, word="smoke."),
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
    monkeypatch.setattr(pipeline_module, "probe_duration_seconds", lambda _path: 1.0)
    monkeypatch.setattr(pipeline_module, "detect_silences", lambda *_args, **_kwargs: [])


def _patch_caption_renderer(monkeypatch) -> None:
    from audio_visualizer.caption.rendering.ffmpegRenderer import FFmpegRenderer

    monkeypatch.setattr(FFmpegRenderer, "_find_ffmpeg", lambda self: "ffmpeg")

    def fake_render(self, ass_path, output_path, size, fps, duration_sec):
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


class TestCrossPackageEventSmoke:
    def test_both_package_apis_share_emitter(self, monkeypatch, tmp_path):
        """Both public APIs can emit through the same AppEventEmitter."""
        _patch_srt_pipeline(monkeypatch)
        _patch_caption_renderer(monkeypatch)

        emitter = AppEventEmitter()
        received = []
        emitter.subscribe(received.append)

        srt_result = transcribe_file(
            input_path=SRT_FIXTURE,
            output_path=tmp_path / "smoke.srt",
            fmt="srt",
            cfg=ResolvedConfig(),
            model=_FakeSrtModel(),
            device_used="cpu",
            compute_type_used="int8",
            emitter=emitter,
        )
        caption_result = render_subtitle(
            CAPTION_FIXTURE,
            tmp_path / "smoke.mov",
            config=RenderConfig(preset="clean_outline", quality="small"),
            emitter=emitter,
        )

        assert srt_result.success is True
        assert caption_result.success is True

        event_types = [event.event_type for event in received]
        assert EventType.JOB_START in event_types
        assert EventType.JOB_COMPLETE in event_types
        assert EventType.RENDER_START in event_types
        assert EventType.RENDER_COMPLETE in event_types

    def test_logging_bridge_captures_both_package_apis(self, monkeypatch, tmp_path, caplog):
        """LoggingBridge captures real API events from both packages in one log."""
        _patch_srt_pipeline(monkeypatch)
        _patch_caption_renderer(monkeypatch)

        emitter = AppEventEmitter()
        logger = logging.getLogger("test.integration.bridge")
        LoggingBridge(logger, emitter)

        with caplog.at_level(logging.DEBUG, logger="test.integration.bridge"):
            transcribe_file(
                input_path=SRT_FIXTURE,
                output_path=tmp_path / "bridge.srt",
                fmt="srt",
                cfg=ResolvedConfig(),
                model=_FakeSrtModel(),
                device_used="cpu",
                compute_type_used="int8",
                emitter=emitter,
            )
            render_subtitle(
                CAPTION_FIXTURE,
                tmp_path / "bridge.mov",
                config=RenderConfig(preset="clean_outline", quality="small"),
                emitter=emitter,
            )

        assert "Starting transcription" in caplog.text
        assert "Fake FFmpeg render complete" in caplog.text

    def test_progress_events_filtered_in_bridge(self, caplog):
        """Progress events from both packages are downgraded to DEBUG."""
        emitter = AppEventEmitter()
        logger = logging.getLogger("test.integration.progress")
        LoggingBridge(logger, emitter)

        with caplog.at_level(logging.DEBUG, logger="test.integration.progress"):
            emitter.emit(AppEvent(
                event_type=EventType.PROGRESS,
                message="SRT progress",
                data={"percent": 50.0},
            ))
            emitter.emit(AppEvent(
                event_type=EventType.RENDER_PROGRESS,
                message="Caption progress",
                data={"frame": 100},
            ))

        assert len(caplog.records) == 2
        assert all(r.levelno == logging.DEBUG for r in caplog.records)


class TestBothPackagesCoexist:
    def test_import_both_packages(self):
        """Both packages can be imported in the same process."""
        import audio_visualizer.srt
        import audio_visualizer.caption
        assert hasattr(audio_visualizer.srt, "__all__")
        assert hasattr(audio_visualizer.caption, "__all__")

    def test_event_types_shared(self):
        """Both packages use the same EventType enum."""
        from audio_visualizer.events import EventType
        # SRT types
        assert EventType.LOG is not None
        assert EventType.PROGRESS is not None
        assert EventType.STAGE is not None
        assert EventType.JOB_START is not None
        assert EventType.MODEL_LOAD is not None
        # Caption types
        assert EventType.RENDER_START is not None
        assert EventType.RENDER_PROGRESS is not None
        assert EventType.RENDER_COMPLETE is not None
