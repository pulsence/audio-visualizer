"""Tests for SrtGenWorker from audio_visualizer.ui.workers.srtGenWorker."""

import inspect
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from audio_visualizer.events import AppEventEmitter
from audio_visualizer.srt.models import PipelineMode, ResolvedConfig
from audio_visualizer.ui.workers.srtGenWorker import SrtGenWorker, SrtGenJobSpec


def _make_job(**overrides):
    """Create a minimal SrtGenJobSpec for testing."""
    defaults = dict(
        input_path=Path("/tmp/test.mp3"),
        output_path=Path("/tmp/test.srt"),
        fmt="srt",
        cfg=MagicMock(spec=ResolvedConfig),
        model_name="tiny",
        device="cpu",
        language=None,
        word_level=False,
        mode=PipelineMode.GENERAL,
    )
    defaults.update(overrides)
    return SrtGenJobSpec(**defaults)


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


class TestSrtGenWorkerNoModelManager:
    """The worker must NOT accept a model_manager parameter."""

    def test_no_model_manager_param(self):
        sig = inspect.signature(SrtGenWorker.__init__)
        assert "model_manager" not in sig.parameters


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

    def test_cancel_before_model_load(self):
        """Cancelling before run starts model load emits canceled signal."""
        emitter = AppEventEmitter()
        job = _make_job()
        worker = SrtGenWorker(jobs=[job], emitter=emitter)

        canceled_msgs = []
        worker.signals.canceled.connect(lambda msg: canceled_msgs.append(msg))

        worker.cancel()
        worker.run()

        assert len(canceled_msgs) == 1
        assert "before model load" in canceled_msgs[0].lower()

    @patch("audio_visualizer.ui.workers.srtGenWorker.load_model")
    def test_cancel_during_model_load(self, mock_load):
        """Cancelling while load_model is running emits canceled signal."""
        emitter = AppEventEmitter()
        job = _make_job()
        worker = SrtGenWorker(jobs=[job], emitter=emitter)

        # Use a thread-safe container since signal is emitted from bg thread
        canceled_msgs = []
        lock = threading.Lock()

        def _capture(msg):
            with lock:
                canceled_msgs.append(msg)

        worker.signals.canceled.connect(_capture, Qt.DirectConnection)

        # Make load_model block until we signal it
        load_started = threading.Event()
        load_release = threading.Event()

        def slow_load(*args, **kwargs):
            load_started.set()
            load_release.wait(timeout=5)
            return MagicMock(), "cpu", "int8"

        mock_load.side_effect = slow_load

        # Run the worker on a background thread
        t = threading.Thread(target=worker.run, daemon=True)
        t.start()

        # Wait for load_model to start, then cancel
        load_started.wait(timeout=5)
        worker.cancel()
        load_release.set()
        t.join(timeout=5)

        with lock:
            assert len(canceled_msgs) == 1
            assert "during model load" in canceled_msgs[0].lower()


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


class TestSrtGenWorkerUsesLoadModelDirectly:
    """The worker must call load_model directly, never via ModelManager."""

    @patch("audio_visualizer.ui.workers.srtGenWorker.load_model")
    @patch("audio_visualizer.ui.workers.srtGenWorker.transcribe_file")
    def test_load_model_called_directly(self, mock_transcribe, mock_load):
        mock_load.return_value = (MagicMock(), "cpu", "int8")
        mock_transcribe.return_value = MagicMock(
            success=True,
            input_path=Path("/tmp/test.mp3"),
            output_path=Path("/tmp/test.srt"),
            error=None,
            transcript_path=None,
            segments_path=None,
            json_bundle_path=None,
            elapsed=1.0,
        )

        emitter = AppEventEmitter()
        job = _make_job()
        worker = SrtGenWorker(jobs=[job], emitter=emitter)

        completed = []
        worker.signals.completed.connect(lambda data: completed.append(data))

        worker.run()

        mock_load.assert_called_once_with(
            model_name="tiny",
            device="cpu",
            strict_cuda=False,
            emitter=emitter,
        )
        assert len(completed) == 1
        assert completed[0]["total"] == 1


class TestSrtGenJobSpecFields:
    def test_script_path_field_defaults_to_none(self):
        job = _make_job()
        assert job.script_path is None

    def test_script_path_can_be_set(self):
        job = _make_job(script_path=Path("/tmp/script.txt"))
        assert job.script_path == Path("/tmp/script.txt")

    def test_existing_srt_path_defaults_to_none(self):
        job = _make_job()
        assert job.existing_srt_path is None

    def test_existing_srt_path_can_be_set(self):
        job = _make_job(existing_srt_path=Path("/tmp/existing.srt"))
        assert job.existing_srt_path == Path("/tmp/existing.srt")


class TestSrtGenWorkerPassesScriptPath:
    """The worker passes script_path to transcribe_file."""

    @patch("audio_visualizer.ui.workers.srtGenWorker.load_model")
    @patch("audio_visualizer.ui.workers.srtGenWorker.transcribe_file")
    def test_script_path_forwarded(self, mock_transcribe, mock_load):
        mock_load.return_value = (MagicMock(), "cpu", "int8")
        mock_transcribe.return_value = MagicMock(
            success=True,
            input_path=Path("/tmp/test.mp3"),
            output_path=Path("/tmp/test.srt"),
            error=None,
            transcript_path=None,
            segments_path=None,
            json_bundle_path=None,
            elapsed=1.0,
        )

        emitter = AppEventEmitter()
        job = _make_job(script_path=Path("/tmp/script.txt"))
        worker = SrtGenWorker(jobs=[job], emitter=emitter)

        completed = []
        worker.signals.completed.connect(lambda data: completed.append(data))
        worker.run()

        assert mock_transcribe.call_count == 1
        call_kwargs = mock_transcribe.call_args[1]
        assert call_kwargs["script_path"] == Path("/tmp/script.txt")


class TestSrtGenWorkerBundleFromSrt:
    """Bundle-from-SRT mode uses _run_bundle_from_srt instead of transcribe_file."""

    @patch("audio_visualizer.ui.workers.srtGenWorker.load_model")
    @patch("audio_visualizer.ui.workers.srtGenWorker.transcribe_file")
    def test_existing_srt_path_triggers_bundle_mode(self, mock_transcribe, mock_load):
        """When existing_srt_path is set, transcribe_file should NOT be called."""
        mock_model = MagicMock()
        mock_load.return_value = (mock_model, "cpu", "int8")

        emitter = AppEventEmitter()
        job = _make_job(
            existing_srt_path=Path("/tmp/existing.srt"),
            json_bundle_path=Path("/tmp/output.bundle.json"),
        )
        worker = SrtGenWorker(jobs=[job], emitter=emitter)

        # Mock _run_bundle_from_srt
        mock_result = MagicMock(
            success=True,
            input_path=Path("/tmp/test.mp3"),
            output_path=Path("/tmp/output.bundle.json"),
            error=None,
            transcript_path=None,
            segments_path=None,
            json_bundle_path=Path("/tmp/output.bundle.json"),
            elapsed=1.0,
        )
        worker._run_bundle_from_srt = MagicMock(return_value=mock_result)

        completed = []
        worker.signals.completed.connect(lambda data: completed.append(data))

        worker.run()

        # transcribe_file should NOT have been called
        mock_transcribe.assert_not_called()
        # _run_bundle_from_srt SHOULD have been called
        worker._run_bundle_from_srt.assert_called_once()

    @patch("audio_visualizer.ui.workers.srtGenWorker.load_model")
    @patch("audio_visualizer.ui.workers.srtGenWorker.transcribe_file")
    def test_normal_job_still_uses_transcribe_file(self, mock_transcribe, mock_load):
        """Jobs without existing_srt_path should use transcribe_file normally."""
        mock_load.return_value = (MagicMock(), "cpu", "int8")
        mock_transcribe.return_value = MagicMock(
            success=True,
            input_path=Path("/tmp/test.mp3"),
            output_path=Path("/tmp/test.srt"),
            error=None,
            transcript_path=None,
            segments_path=None,
            json_bundle_path=None,
            elapsed=1.0,
        )

        emitter = AppEventEmitter()
        job = _make_job()
        worker = SrtGenWorker(jobs=[job], emitter=emitter)

        completed = []
        worker.signals.completed.connect(lambda data: completed.append(data))

        worker.run()

        mock_transcribe.assert_called_once()
        assert len(completed) == 1


class TestSrtGenWorkerDeviceMetadata:
    """Completed payload must include device_used and compute_type_used."""

    @patch("audio_visualizer.ui.workers.srtGenWorker.load_model")
    @patch("audio_visualizer.ui.workers.srtGenWorker.transcribe_file")
    def test_completed_payload_includes_device_metadata(self, mock_transcribe, mock_load):
        mock_load.return_value = (MagicMock(), "cuda", "float16")
        mock_transcribe.return_value = MagicMock(
            success=True,
            input_path=Path("/tmp/test.mp3"),
            output_path=Path("/tmp/test.srt"),
            error=None,
            transcript_path=None,
            segments_path=None,
            json_bundle_path=None,
            elapsed=1.0,
        )

        emitter = AppEventEmitter()
        job = _make_job()
        worker = SrtGenWorker(jobs=[job], emitter=emitter)

        completed = []
        worker.signals.completed.connect(lambda data: completed.append(data))

        worker.run()

        assert len(completed) == 1
        assert completed[0]["device_used"] == "cuda"
        assert completed[0]["compute_type_used"] == "float16"
