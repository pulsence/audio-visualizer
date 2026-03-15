"""Tests for the public API module."""
from pathlib import Path

from local_srt.api import load_model, transcribe_batch, transcribe_file
from local_srt.core import CoreTranscriptionResult
from local_srt.events import ErrorEvent, FileCompleteEvent, FileStartEvent, ModelLoadEvent
from local_srt.models import ResolvedConfig, SubtitleBlock


def test_load_model_emits_success(monkeypatch):
    events = []

    def handler(event):
        events.append(event)

    def fake_init(*args, **kwargs):
        return object(), "cpu", "int8"

    monkeypatch.setattr("local_srt.api.init_whisper_model_internal", fake_init)

    model, device, compute = load_model("tiny", "cpu", False, handler)

    assert model is not None
    assert device == "cpu"
    assert compute == "int8"
    assert any(isinstance(e, ModelLoadEvent) and e.success for e in events)


def test_load_model_emits_failure(monkeypatch):
    events = []

    def handler(event):
        events.append(event)

    def fake_init(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("local_srt.api.init_whisper_model_internal", fake_init)

    try:
        load_model("tiny", "cpu", False, handler)
    except RuntimeError:
        pass

    assert any(isinstance(e, ModelLoadEvent) and not e.success for e in events)
    assert any(isinstance(e, ErrorEvent) for e in events)


def test_transcribe_file_success(monkeypatch, tmp_path):
    def fake_transcribe(**kwargs):
        return CoreTranscriptionResult(
            input_path=kwargs["input_path"],
            output_path=kwargs["output_path"],
            transcript_path=None,
            segments_path=None,
            json_bundle_path=None,
            segments=[],
            subtitles=[SubtitleBlock(start=0.0, end=1.0, lines=["hi"])],
            device_used="cpu",
            compute_type_used="int8",
            elapsed=0.1,
        )

    monkeypatch.setattr("local_srt.api.transcribe_file_internal", fake_transcribe)

    result = transcribe_file(
        input_path=tmp_path / "a.mp3",
        output_path=tmp_path / "a.srt",
        fmt="srt",
        cfg=ResolvedConfig(),
        model=object(),
        device_used="cpu",
        compute_type_used="int8",
    )

    assert result.success is True
    assert result.output_path.name == "a.srt"
    assert result.subtitles


def test_transcribe_file_failure_emits_error(monkeypatch, tmp_path):
    events = []

    def handler(event):
        events.append(event)

    def fake_transcribe(**kwargs):
        raise RuntimeError("fail")

    monkeypatch.setattr("local_srt.api.transcribe_file_internal", fake_transcribe)

    result = transcribe_file(
        input_path=tmp_path / "a.mp3",
        output_path=tmp_path / "a.srt",
        fmt="srt",
        cfg=ResolvedConfig(),
        model=object(),
        device_used="cpu",
        compute_type_used="int8",
        event_handler=handler,
    )

    assert result.success is False
    assert "fail" in (result.error or "")
    assert any(isinstance(e, ErrorEvent) for e in events)


def test_transcribe_batch_emits_file_events(monkeypatch, tmp_path):
    events = []

    def handler(event):
        events.append(event)

    def fake_preflight(*args, **kwargs):
        return True, ""

    def fake_transcribe_file(**kwargs):
        return type(
            "R",
            (),
            {"success": True, "error": None, "output_path": kwargs["output_path"]},
        )()

    monkeypatch.setattr("local_srt.api.preflight_one", fake_preflight)
    monkeypatch.setattr("local_srt.api.transcribe_file", fake_transcribe_file)

    inputs = [tmp_path / "a.mp3", tmp_path / "b.mp3"]
    result = transcribe_batch(
        input_paths=inputs,
        outdir=tmp_path,
        fmt="srt",
        cfg=ResolvedConfig(),
        model=object(),
        device_used="cpu",
        compute_type_used="int8",
        event_handler=handler,
    )

    assert result.total == 2
    assert result.successful == 2
    assert any(isinstance(e, FileStartEvent) for e in events)
    assert any(isinstance(e, FileCompleteEvent) for e in events)
