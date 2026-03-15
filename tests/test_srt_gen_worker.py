"""Tests for SrtGenWorker from audio_visualizer.ui.workers.srtGenWorker."""

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from audio_visualizer.events import AppEventEmitter
from audio_visualizer.ui.workers.srtGenWorker import SrtGenWorker, SrtGenJobSpec


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestSrtGenWorkerSignals:
    def test_worker_signals_exist(self):
        emitter = AppEventEmitter()
        worker = SrtGenWorker(jobs=[], emitter=emitter)

        # Verify all expected signals are present
        assert hasattr(worker.signals, "started")
        assert hasattr(worker.signals, "stage")
        assert hasattr(worker.signals, "progress")
        assert hasattr(worker.signals, "log")
        assert hasattr(worker.signals, "completed")
        assert hasattr(worker.signals, "failed")
        assert hasattr(worker.signals, "canceled")


class TestSrtGenWorkerCancel:
    def test_cancel_flag(self):
        emitter = AppEventEmitter()
        worker = SrtGenWorker(jobs=[], emitter=emitter)

        assert worker.is_canceled is False
        worker.cancel()
        assert worker.is_canceled is True

    def test_cancel_flag_initially_false(self):
        emitter = AppEventEmitter()
        worker = SrtGenWorker(jobs=[], emitter=emitter)
        assert worker.is_canceled is False


class TestSrtGenWorkerEmptyBatch:
    def test_empty_jobs_completes(self):
        emitter = AppEventEmitter()
        worker = SrtGenWorker(jobs=[], emitter=emitter)

        received = []
        worker.signals.completed.connect(lambda data: received.append(data))

        worker.run()

        assert len(received) == 1
        assert received[0]["results"] == []
        assert received[0]["total"] == 0
