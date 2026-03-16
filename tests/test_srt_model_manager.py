"""Tests for the shared Whisper ModelManager."""

from audio_visualizer.events import AppEventEmitter, EventType
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
