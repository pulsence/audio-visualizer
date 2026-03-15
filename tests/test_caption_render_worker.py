"""Tests for CaptionRenderWorker from audio_visualizer.ui.workers.captionRenderWorker."""

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from audio_visualizer.events import AppEventEmitter
from audio_visualizer.caption.captionApi import RenderConfig, RenderResult
from audio_visualizer.ui.workers.captionRenderWorker import (
    CaptionRenderJobSpec,
    CaptionRenderWorker,
)


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestCaptionRenderWorkerSignals:
    def test_worker_signals_exist(self):
        spec = CaptionRenderJobSpec(
            subtitle_path=Path("/tmp/test.srt"),
            output_path=Path("/tmp/out.mov"),
            config=RenderConfig(),
        )
        emitter = AppEventEmitter()
        worker = CaptionRenderWorker(spec=spec, emitter=emitter)

        assert hasattr(worker.signals, "started")
        assert hasattr(worker.signals, "stage")
        assert hasattr(worker.signals, "progress")
        assert hasattr(worker.signals, "log")
        assert hasattr(worker.signals, "completed")
        assert hasattr(worker.signals, "failed")
        assert hasattr(worker.signals, "canceled")


class TestCaptionRenderWorkerCancel:
    def test_cancel_flag(self):
        spec = CaptionRenderJobSpec(
            subtitle_path=Path("/tmp/test.srt"),
            output_path=Path("/tmp/out.mov"),
            config=RenderConfig(),
        )
        emitter = AppEventEmitter()
        worker = CaptionRenderWorker(spec=spec, emitter=emitter)

        assert worker.is_canceled is False
        worker.cancel()
        assert worker.is_canceled is True

    def test_cancel_before_start_emits_canceled(self):
        spec = CaptionRenderJobSpec(
            subtitle_path=Path("/tmp/test.srt"),
            output_path=Path("/tmp/out.mov"),
            config=RenderConfig(),
        )
        emitter = AppEventEmitter()
        worker = CaptionRenderWorker(spec=spec, emitter=emitter)

        received = []
        worker.signals.canceled.connect(lambda msg: received.append(msg))

        worker.cancel()
        worker.run()

        assert len(received) == 1
        assert "cancel" in received[0].lower()


class TestCaptionRenderWorkerLifecycle:
    def test_successful_render(self):
        spec = CaptionRenderJobSpec(
            subtitle_path=Path("/tmp/test.srt"),
            output_path=Path("/tmp/out.mov"),
            config=RenderConfig(),
        )
        emitter = AppEventEmitter()
        worker = CaptionRenderWorker(spec=spec, emitter=emitter)

        mock_result = RenderResult(
            success=True,
            output_path=Path("/tmp/out.mov"),
            width=1920,
            height=200,
            duration_ms=5000,
        )

        completed = []
        worker.signals.completed.connect(lambda data: completed.append(data))

        with patch(
            "audio_visualizer.ui.workers.captionRenderWorker.render_subtitle",
            return_value=mock_result,
        ):
            worker.run()

        assert len(completed) == 1
        assert completed[0]["output_path"] == str(Path("/tmp/out.mov"))
        assert completed[0]["width"] == 1920
        assert completed[0]["height"] == 200
        assert completed[0]["duration_ms"] == 5000

    def test_failed_render(self):
        spec = CaptionRenderJobSpec(
            subtitle_path=Path("/tmp/test.srt"),
            output_path=Path("/tmp/out.mov"),
            config=RenderConfig(),
        )
        emitter = AppEventEmitter()
        worker = CaptionRenderWorker(spec=spec, emitter=emitter)

        mock_result = RenderResult(
            success=False,
            error="FFmpeg not found",
        )

        failed = []
        worker.signals.failed.connect(lambda msg, data: failed.append((msg, data)))

        with patch(
            "audio_visualizer.ui.workers.captionRenderWorker.render_subtitle",
            return_value=mock_result,
        ):
            worker.run()

        assert len(failed) == 1
        assert "FFmpeg" in failed[0][0]

    def test_exception_during_render(self):
        spec = CaptionRenderJobSpec(
            subtitle_path=Path("/tmp/test.srt"),
            output_path=Path("/tmp/out.mov"),
            config=RenderConfig(),
        )
        emitter = AppEventEmitter()
        worker = CaptionRenderWorker(spec=spec, emitter=emitter)

        failed = []
        worker.signals.failed.connect(lambda msg, data: failed.append((msg, data)))

        with patch(
            "audio_visualizer.ui.workers.captionRenderWorker.render_subtitle",
            side_effect=RuntimeError("unexpected error"),
        ):
            worker.run()

        assert len(failed) == 1
        assert "unexpected error" in failed[0][0]


class TestCaptionRenderWorkerConfig:
    def test_render_config_passes_through(self):
        config = RenderConfig(
            preset="clean_outline",
            fps="60",
            quality="large",
            safety_scale=1.5,
            apply_animation=False,
            reskin=True,
        )
        spec = CaptionRenderJobSpec(
            subtitle_path=Path("/tmp/test.srt"),
            output_path=Path("/tmp/out.mov"),
            config=config,
        )
        emitter = AppEventEmitter()
        worker = CaptionRenderWorker(spec=spec, emitter=emitter)

        assert worker._spec.config.preset == "clean_outline"
        assert worker._spec.config.fps == "60"
        assert worker._spec.config.quality == "large"
        assert worker._spec.config.safety_scale == 1.5
        assert worker._spec.config.apply_animation is False
        assert worker._spec.config.reskin is True
