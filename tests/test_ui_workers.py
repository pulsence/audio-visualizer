"""Tests for WorkerBridge and WorkerSignals from audio_visualizer.ui.workers.workerBridge."""

import io
import logging

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from audio_visualizer.events import (
    AppEvent,
    AppEventEmitter,
    EventLevel,
    EventType,
)
from audio_visualizer.ui.tabs.renderComposition.model import CompositionModel
from audio_visualizer.ui.workers.compositionWorker import CompositionWorker
from audio_visualizer.ui.workers.workerBridge import WorkerBridge, WorkerSignals


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestWorkerBridgeLifecycle:
    def test_attach_detach(self):
        emitter = AppEventEmitter()
        signals = WorkerSignals()
        bridge = WorkerBridge(emitter, signals)

        assert bridge._attached is False
        bridge.attach()
        assert bridge._attached is True

        # Attaching again is a no-op
        bridge.attach()
        assert bridge._attached is True

        bridge.detach()
        assert bridge._attached is False

        # Detaching again is a no-op
        bridge.detach()
        assert bridge._attached is False


class TestWorkerBridgeEventForwarding:
    def test_progress_event_forwarded(self):
        emitter = AppEventEmitter()
        signals = WorkerSignals()
        bridge = WorkerBridge(emitter, signals)
        bridge.attach()

        received: list[tuple] = []
        signals.progress.connect(lambda pct, msg, data: received.append((pct, msg, data)))

        emitter.emit(AppEvent(
            event_type=EventType.PROGRESS,
            message="halfway",
            data={"percent": 50.0},
        ))

        assert len(received) == 1
        pct, msg, data = received[0]
        assert pct == 50.0
        assert msg == "halfway"
        assert data["percent"] == 50.0

    def test_stage_event_forwarded(self):
        emitter = AppEventEmitter()
        signals = WorkerSignals()
        bridge = WorkerBridge(emitter, signals)
        bridge.attach()

        received: list[tuple] = []
        signals.stage.connect(lambda name, idx, total, data: received.append((name, idx, total, data)))

        emitter.emit(AppEvent(
            event_type=EventType.STAGE,
            message="transcribing",
            data={"stage_number": 2, "total_stages": 5},
        ))

        assert len(received) == 1
        name, idx, total, data = received[0]
        assert name == "transcribing"
        assert idx == 2
        assert total == 5

    def test_log_event_forwarded(self):
        emitter = AppEventEmitter()
        signals = WorkerSignals()
        bridge = WorkerBridge(emitter, signals)
        bridge.attach()

        received: list[tuple] = []
        signals.log.connect(lambda level, msg, data: received.append((level, msg, data)))

        emitter.emit(AppEvent(
            event_type=EventType.LOG,
            message="info message",
            level=EventLevel.INFO,
        ))

        assert len(received) == 1
        level, msg, data = received[0]
        assert level == "INFO"
        assert msg == "info message"

    def test_completed_event_forwarded(self):
        emitter = AppEventEmitter()
        signals = WorkerSignals()
        bridge = WorkerBridge(emitter, signals)
        bridge.attach()

        received: list[dict] = []
        signals.completed.connect(lambda result: received.append(result))

        emitter.emit(AppEvent(
            event_type=EventType.JOB_COMPLETE,
            message="done",
            level=EventLevel.INFO,
            data={"output_path": "/tmp/out.mp4"},
        ))

        assert len(received) == 1
        assert received[0]["output_path"] == "/tmp/out.mp4"

    def test_error_logs_do_not_auto_emit_failed(self):
        emitter = AppEventEmitter()
        signals = WorkerSignals()
        bridge = WorkerBridge(emitter, signals)
        bridge.attach()

        received: list[tuple] = []
        signals.failed.connect(lambda msg, data: received.append((msg, data)))

        emitter.emit(AppEvent(
            event_type=EventType.LOG,
            message="something broke",
            level=EventLevel.ERROR,
            data={"detail": "disk full"},
        ))

        assert received == []

    def test_started_event_forwarded(self):
        emitter = AppEventEmitter()
        signals = WorkerSignals()
        bridge = WorkerBridge(emitter, signals)
        bridge.attach()

        received: list[tuple] = []
        signals.started.connect(lambda jt, ot, lbl: received.append((jt, ot, lbl)))

        emitter.emit(AppEvent(
            event_type=EventType.JOB_START,
            message="Render starting",
            data={"job_type": "render", "owner_tab_id": "viz"},
        ))

        assert len(received) == 1
        job_type, owner_tab_id, label = received[0]
        assert job_type == "render"
        assert owner_tab_id == "viz"
        assert label == "Render starting"

    def test_canceled_signal_exists(self):
        signals = WorkerSignals()
        received: list[str] = []
        signals.canceled.connect(lambda msg: received.append(msg))

        signals.canceled.emit("user canceled")
        assert received == ["user canceled"]


class TestCompositionWorkerSignalContract:
    def test_uses_shared_worker_signals_and_emits_started(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "audio_visualizer.ui.workers.compositionWorker.shutil.which",
            lambda _name: None,
        )

        worker = CompositionWorker(CompositionModel(), tmp_path / "out.mp4")
        assert isinstance(worker.signals, WorkerSignals)

        started: list[tuple[str, str, str]] = []
        stages: list[tuple[str, int, int, dict]] = []
        failed: list[tuple[str, dict]] = []
        logs: list[tuple[str, str, dict]] = []

        worker.signals.started.connect(
            lambda job_type, owner_tab_id, label: started.append((job_type, owner_tab_id, label))
        )
        worker.signals.stage.connect(
            lambda name, index, total, data: stages.append((name, index, total, data))
        )
        worker.signals.failed.connect(lambda message, data: failed.append((message, data)))
        worker.signals.log.connect(lambda level, message, data: logs.append((level, message, data)))

        worker.run()

        assert started == [
            ("composition", "render_composition", "Rendering composition to out.mp4")
        ]
        assert stages == [
            (
                "Preparing FFmpeg command",
                0,
                2,
                {"output_path": str(tmp_path / "out.mp4")},
            )
        ]
        assert logs == [
            (
                "ERROR",
                "ffmpeg not found on PATH.",
                {"output_path": str(tmp_path / "out.mp4")},
            )
        ]
        assert len(failed) == 1
        assert "ffmpeg not found on PATH" in failed[0][0]

    def test_emits_log_and_running_stage_before_spawn_failure(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "audio_visualizer.ui.workers.compositionWorker.shutil.which",
            lambda _name: "/usr/bin/ffmpeg",
        )
        monkeypatch.setattr(
            "audio_visualizer.ui.workers.compositionWorker.build_ffmpeg_command",
            lambda model, output_path: ["ffmpeg", "-y", str(output_path)],
        )

        def _raise_spawn(*_args, **_kwargs):
            raise OSError("spawn failed")

        monkeypatch.setattr(
            "audio_visualizer.ui.workers.compositionWorker.subprocess.Popen",
            _raise_spawn,
        )

        worker = CompositionWorker(CompositionModel(), tmp_path / "out.mp4")

        stages: list[tuple[str, int, int, dict]] = []
        logs: list[tuple[str, str, dict]] = []
        failed: list[tuple[str, dict]] = []

        worker.signals.stage.connect(
            lambda name, index, total, data: stages.append((name, index, total, data))
        )
        worker.signals.log.connect(lambda level, message, data: logs.append((level, message, data)))
        worker.signals.failed.connect(lambda message, data: failed.append((message, data)))

        worker.run()

        assert stages == [
            (
                "Preparing FFmpeg command",
                0,
                2,
                {"output_path": str(tmp_path / "out.mp4")},
            ),
            (
                "Running FFmpeg",
                1,
                2,
                {"output_path": str(tmp_path / "out.mp4")},
            ),
        ]
        assert logs[0] == (
            "INFO",
            "Prepared FFmpeg composition command.",
            {
                "command": ["ffmpeg", "-y", str(tmp_path / "out.mp4")],
                "output_path": str(tmp_path / "out.mp4"),
            },
        )
        assert any(
            level == "ERROR"
            and message == "Failed to start FFmpeg."
            and data["error"] == "spawn failed"
            for level, message, data in logs
        )
        assert failed == [
            (
                "Failed to start FFmpeg: spawn failed",
                {"output_path": str(tmp_path / "out.mp4")},
            )
        ]

    def test_retries_with_software_encoder_after_hardware_failure(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "audio_visualizer.ui.workers.compositionWorker.shutil.which",
            lambda _name: "/usr/bin/ffmpeg",
        )

        built_encoders: list[str] = []

        def _build_cmd(model, output_path, encoder_override=None):
            encoder = encoder_override or "h264_nvenc"
            built_encoders.append(encoder)
            return ["ffmpeg", "-y", "-c:v", encoder, str(output_path)]

        class _Proc:
            def __init__(self, returncode, stderr_lines):
                self._returncode = returncode
                self.stderr = iter(stderr_lines)

            def wait(self):
                return self._returncode

            def terminate(self):
                return None

        procs = [
            _Proc(1, ["Encoder init failed\n"]),
            _Proc(0, ["time=00:00:01.00\n"]),
        ]

        monkeypatch.setattr(
            "audio_visualizer.ui.workers.compositionWorker.build_ffmpeg_command",
            _build_cmd,
        )
        monkeypatch.setattr(
            "audio_visualizer.ui.workers.compositionWorker.subprocess.Popen",
            lambda *args, **kwargs: procs.pop(0),
        )

        worker = CompositionWorker(CompositionModel(), tmp_path / "out.mp4")

        logs: list[tuple[str, str, dict]] = []
        progress: list[tuple[float, str, dict]] = []
        stages: list[tuple[str, int, int, dict]] = []
        completed: list[dict] = []
        failed: list[tuple[str, dict]] = []

        worker.signals.log.connect(lambda level, message, data: logs.append((level, message, data)))
        worker.signals.progress.connect(lambda pct, msg, data: progress.append((pct, msg, data)))
        worker.signals.stage.connect(lambda name, index, total, data: stages.append((name, index, total, data)))
        worker.signals.completed.connect(lambda result: completed.append(result))
        worker.signals.failed.connect(lambda message, data: failed.append((message, data)))

        worker.run()

        assert built_encoders == ["h264_nvenc", "libx264"]
        assert failed == []
        assert completed == [
            {
                "output_path": str(tmp_path / "out.mp4"),
                "video_encoder": "libx264",
            }
        ]
        assert any(
            level == "WARNING" and "retrying with software encoder" in message.lower()
            for level, message, _data in logs
        )
        assert any(
            name == "Retrying FFmpeg with software encoder"
            and data["video_encoder"] == "libx264"
            for name, _index, _total, data in stages
        )
        assert any(
            message == "Retrying with libx264..."
            and data["video_encoder"] == "libx264"
            for _pct, message, data in progress
        )

    def test_nonzero_exit_emits_diagnostic_log(self, monkeypatch, tmp_path, caplog):
        monkeypatch.setattr(
            "audio_visualizer.ui.workers.compositionWorker.shutil.which",
            lambda _name: "/usr/bin/ffmpeg",
        )
        monkeypatch.setattr(
            "audio_visualizer.ui.workers.compositionWorker.build_ffmpeg_command",
            lambda model, output_path: ["ffmpeg", "-y", "-c:v", "libx264", str(output_path)],
        )

        class _Proc:
            def __init__(self):
                self.stderr = iter(["Encoder init failed\n", "Bad option\n"])
                self.stdout = io.StringIO("stdout details\n")

            def wait(self):
                return 1

            def terminate(self):
                return None

        monkeypatch.setattr(
            "audio_visualizer.ui.workers.compositionWorker.subprocess.Popen",
            lambda *args, **kwargs: _Proc(),
        )

        worker = CompositionWorker(CompositionModel(), tmp_path / "out.mp4")
        logs: list[tuple[str, str, dict]] = []
        failed: list[tuple[str, dict]] = []
        worker.signals.log.connect(lambda level, message, data: logs.append((level, message, data)))
        worker.signals.failed.connect(lambda message, data: failed.append((message, data)))
        caplog.set_level(
            logging.ERROR,
            logger="audio_visualizer.ui.workers.compositionWorker",
        )

        worker.run()

        assert failed == [
            (
                "FFmpeg exited with code 1:\nEncoder init failed\nBad option",
                {"output_path": str(tmp_path / "out.mp4"), "video_encoder": "libx264"},
            )
        ]
        assert any(
            level == "ERROR"
            and message == "FFmpeg exited with a non-zero status."
            and data["stderr_tail"] == "Encoder init failed\nBad option"
            and data["stdout_tail"] == "stdout details"
            for level, message, data in logs
        )
        assert "FFmpeg exited with code 1 for composition render" in caplog.text
