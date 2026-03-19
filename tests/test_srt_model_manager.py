"""Tests for the shared Whisper ModelManager."""

from unittest.mock import patch

from audio_visualizer.events import AppEventEmitter, EventType
from audio_visualizer.srt.core.whisperWrapper import _check_cuda_runtime
from audio_visualizer.srt.modelManager import ModelManager


class TestModelManager:
    def test_reload_when_same_model_is_requested_on_different_device(self, monkeypatch):
        calls = []

        def fake_init(model_name, device, strict_cuda, emitter):
            calls.append((model_name, device))
            return object(), device, "float16"

        monkeypatch.setattr(
            "audio_visualizer.srt.modelManager.init_whisper_model_internal",
            fake_init,
        )

        manager = ModelManager()
        first = manager.load("base", device="cpu")
        second = manager.load("base", device="cuda")

        assert first is not second
        assert calls == [("base", "cpu"), ("base", "cuda")]
        assert manager.model_info() is not None
        assert manager.model_info().device == "cuda"

    def test_emits_model_load_events_for_success_and_failure(self, monkeypatch):
        emitter = AppEventEmitter()
        seen = []
        emitter.subscribe(seen.append)

        def fake_init(model_name, device, strict_cuda, emitter):
            raise RuntimeError("load failed")

        monkeypatch.setattr(
            "audio_visualizer.srt.modelManager.init_whisper_model_internal",
            fake_init,
        )

        manager = ModelManager()

        try:
            manager.load("base", device="cpu", emitter=emitter)
        except RuntimeError:
            pass

        assert any(
            event.event_type is EventType.MODEL_LOAD and event.data.get("success") is False
            for event in seen
        )


class TestCudaPreCheck:
    def test_cuda_precheck_triggers_fallback_when_cublas_missing(self, monkeypatch):
        """When ctypes.cdll.LoadLibrary raises OSError, CUDA pre-check returns False."""
        with patch("audio_visualizer.srt.core.whisperWrapper.ctypes") as mock_ctypes:
            mock_ctypes.cdll.LoadLibrary.side_effect = OSError("lib not found")
            available, msg = _check_cuda_runtime()
            assert available is False
            assert "pip install nvidia-cublas-cu12" in msg

    def test_cuda_precheck_succeeds_when_cublas_present(self, monkeypatch):
        """When ctypes.cdll.LoadLibrary succeeds, CUDA pre-check returns True."""
        with patch("audio_visualizer.srt.core.whisperWrapper.ctypes") as mock_ctypes:
            mock_ctypes.cdll.LoadLibrary.return_value = True
            available, msg = _check_cuda_runtime()
            assert available is True
            assert msg == ""

    def test_cuda_precheck_fallback_in_init_whisper(self, monkeypatch):
        """init_whisper_model_internal falls back to CPU when pre-check fails."""
        monkeypatch.setattr(
            "audio_visualizer.srt.core.whisperWrapper._check_cuda_runtime",
            lambda: (False, "cuBLAS not found"),
        )

        model_sentinel = object()
        monkeypatch.setattr(
            "faster_whisper.WhisperModel",
            lambda model_name, device, compute_type: model_sentinel,
        )

        from audio_visualizer.srt.core.whisperWrapper import init_whisper_model_internal

        emitter = AppEventEmitter()
        events = []
        emitter.subscribe(events.append)

        model, device_used, compute_type = init_whisper_model_internal(
            model_name="tiny",
            device="cuda",
            strict_cuda=False,
            emitter=emitter,
        )
        assert device_used == "cpu"
        assert compute_type == "int8"
        assert any("cuBLAS not found" in e.message for e in events)
