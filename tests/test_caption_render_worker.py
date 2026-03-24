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

    def test_delivery_output_when_overlay_equals_delivery(self, tmp_path):
        """delivery output succeeds when overlay_path == delivery_path via temp+rename."""
        overlay_path = tmp_path / "preview.mp4"
        overlay_path.write_bytes(b"overlay-data")

        spec = CaptionRenderJobSpec(
            subtitle_path=Path("/tmp/test.srt"),
            output_path=overlay_path,
            delivery_output_path=overlay_path,
            config=RenderConfig(),
        )
        emitter = AppEventEmitter()
        worker = CaptionRenderWorker(spec=spec, emitter=emitter)

        mock_result = RenderResult(
            success=True,
            output_path=overlay_path,
            width=1920,
            height=200,
            duration_ms=5000,
        )

        completed = []
        worker.signals.completed.connect(completed.append)

        # Mock render_subtitle and _create_delivery_output to verify the pattern
        with patch(
            "audio_visualizer.ui.workers.captionRenderWorker.render_subtitle",
            return_value=mock_result,
        ):
            # _create_delivery_output will be called with overlay_path == delivery_path
            # Just verify the worker calls it without crashing
            with patch.object(worker, "_create_delivery_output") as mock_delivery:
                worker.run()
                mock_delivery.assert_called_once_with(
                    overlay_path=overlay_path,
                    delivery_path=overlay_path,
                    audio_path=None,
                )

    def test_cancel_before_subprocess_aborts_via_flag(self):
        """Cancel before subprocess starts aborts via the cancel flag."""
        spec = CaptionRenderJobSpec(
            subtitle_path=Path("/tmp/test.srt"),
            output_path=Path("/tmp/out.mov"),
            config=RenderConfig(),
        )
        emitter = AppEventEmitter()
        worker = CaptionRenderWorker(spec=spec, emitter=emitter)

        canceled_msgs = []
        worker.signals.canceled.connect(lambda msg: canceled_msgs.append(msg))

        worker.cancel()
        worker.run()

        assert len(canceled_msgs) == 1
        assert worker._captured_process is None

    def test_process_lock_exists(self):
        """Worker has a threading lock for process access."""
        spec = CaptionRenderJobSpec(
            subtitle_path=Path("/tmp/test.srt"),
            output_path=Path("/tmp/out.mov"),
            config=RenderConfig(),
        )
        emitter = AppEventEmitter()
        worker = CaptionRenderWorker(spec=spec, emitter=emitter)
        assert hasattr(worker, "_process_lock")
        import threading
        assert isinstance(worker._process_lock, type(threading.Lock()))

    def test_worker_can_emit_separate_delivery_and_overlay_outputs(self, monkeypatch, tmp_path):
        overlay_path = tmp_path / "overlay.mov"
        delivery_path = tmp_path / "delivery.mp4"
        spec = CaptionRenderJobSpec(
            subtitle_path=Path("/tmp/test.srt"),
            output_path=overlay_path,
            delivery_output_path=delivery_path,
            config=RenderConfig(),
        )
        emitter = AppEventEmitter()
        worker = CaptionRenderWorker(spec=spec, emitter=emitter)

        completed = []
        worker.signals.completed.connect(completed.append)

        monkeypatch.setattr(
            "audio_visualizer.ui.workers.captionRenderWorker.render_subtitle",
            lambda **kwargs: RenderResult(
                success=True,
                output_path=overlay_path,
                width=1280,
                height=180,
                duration_ms=4000,
            ),
        )
        monkeypatch.setattr(
            worker,
            "_create_delivery_output",
            lambda overlay_path, delivery_path, audio_path: delivery_path.write_bytes(b"mp4"),
        )

        worker.run()

        assert len(completed) == 1
        assert completed[0]["delivery_path"] == str(delivery_path)
        assert completed[0]["overlay_path"] == str(overlay_path)

    def test_delivery_output_uses_selected_encoder_and_decode_flags(self, monkeypatch, tmp_path):
        overlay_path = tmp_path / "overlay.mov"
        overlay_path.write_bytes(b"overlay")
        delivery_path = tmp_path / "delivery.mp4"

        spec = CaptionRenderJobSpec(
            subtitle_path=Path("/tmp/test.srt"),
            output_path=overlay_path,
            delivery_output_path=delivery_path,
            config=RenderConfig(),
        )
        emitter = AppEventEmitter()
        worker = CaptionRenderWorker(spec=spec, emitter=emitter)

        commands = []

        class _FakeProc:
            def __init__(self, cmd):
                self.cmd = cmd
                self.returncode = 0

            def communicate(self):
                Path(self.cmd[-1]).write_bytes(b"mp4")
                return "", ""

        monkeypatch.setattr(
            "audio_visualizer.hwaccel.select_encoder",
            lambda codec="h264": "h264_nvenc",
        )
        monkeypatch.setattr(
            "audio_visualizer.hwaccel.get_decode_flags",
            lambda: ["-hwaccel", "auto"],
        )
        monkeypatch.setattr(
            "audio_visualizer.hwaccel.is_hardware_encoder",
            lambda encoder: encoder != "libx264",
        )
        monkeypatch.setattr(
            "audio_visualizer.ui.workers.captionRenderWorker.subprocess.Popen",
            lambda cmd, **kwargs: commands.append(cmd) or _FakeProc(cmd),
        )

        worker._create_delivery_output(overlay_path, delivery_path, None)

        assert len(commands) == 1
        assert commands[0][:4] == ["ffmpeg", "-y", "-hwaccel", "auto"]
        assert commands[0][commands[0].index("-c:v") + 1] == "h264_nvenc"
        assert delivery_path.exists()

    def test_delivery_output_falls_back_to_software_encoder(self, monkeypatch, tmp_path):
        overlay_path = tmp_path / "overlay.mov"
        overlay_path.write_bytes(b"overlay")
        delivery_path = tmp_path / "delivery.mp4"

        spec = CaptionRenderJobSpec(
            subtitle_path=Path("/tmp/test.srt"),
            output_path=overlay_path,
            delivery_output_path=delivery_path,
            config=RenderConfig(),
        )
        emitter = AppEventEmitter()
        worker = CaptionRenderWorker(spec=spec, emitter=emitter)

        commands = []
        events = []
        emitter.subscribe(events.append)

        class _FakeProc:
            def __init__(self, cmd, returncode, stderr):
                self.cmd = cmd
                self.returncode = returncode
                self._stderr = stderr

            def communicate(self):
                if self.returncode == 0:
                    Path(self.cmd[-1]).write_bytes(b"mp4")
                return "", self._stderr

        def _fake_popen(cmd, **kwargs):
            commands.append(cmd)
            if len(commands) == 1:
                return _FakeProc(cmd, 1, "hardware failed")
            return _FakeProc(cmd, 0, "")

        monkeypatch.setattr(
            "audio_visualizer.hwaccel.select_encoder",
            lambda codec="h264": "h264_nvenc",
        )
        monkeypatch.setattr(
            "audio_visualizer.hwaccel.get_decode_flags",
            lambda: ["-hwaccel", "auto"],
        )
        monkeypatch.setattr(
            "audio_visualizer.hwaccel.is_hardware_encoder",
            lambda encoder: encoder != "libx264",
        )
        monkeypatch.setattr(
            "audio_visualizer.ui.workers.captionRenderWorker.subprocess.Popen",
            _fake_popen,
        )

        worker._create_delivery_output(overlay_path, delivery_path, None)

        assert [cmd[cmd.index("-c:v") + 1] for cmd in commands] == ["h264_nvenc", "libx264"]
        assert any(
            "retrying with software encoder libx264" in event.message.lower()
            for event in events
        )
        assert delivery_path.exists()
