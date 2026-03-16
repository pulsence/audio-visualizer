"""Tests for WorkerBridge and WorkerSignals from audio_visualizer.ui.workers.workerBridge."""

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from audio_visualizer.events import (
    AppEvent,
    AppEventEmitter,
    EventLevel,
    EventType,
)
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
