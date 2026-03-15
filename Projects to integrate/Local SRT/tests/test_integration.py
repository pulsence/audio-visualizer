#!/usr/bin/env python3
"""Integration tests with real audio fixtures.

These tests are opt-in (pytest -m integration).
"""
from __future__ import annotations

import tempfile
from pathlib import Path
import re
from typing import Dict, List, Tuple

import pytest

from local_srt.audio import detect_silences, to_wav_16k_mono
from local_srt.models import ResolvedConfig
from local_srt.output_writers import write_srt
from local_srt.subtitle_generation import (
    apply_silence_alignment,
    chunk_segments_to_subtitles,
    chunk_words_to_subtitles,
    collect_words,
    hygiene_and_polish,
)
from local_srt.system import ffmpeg_ok
from local_srt.whisper_wrapper import init_whisper_model_internal
from tests.helpers import compare_srt_timing


pytestmark = [pytest.mark.integration]

AUDIO_DIR = Path(__file__).parent / "fixtures" / "audio"
BASELINE_DIR = Path(__file__).parent / "fixtures" / "baselines"

REQUIRED_AUDIO: Dict[str, str] = {
    "single_sentence": "single_sentence.wav",
    "paused_speech": "paused_speech.wav",
    "continuous_speech": "continuous_speech.wav",
    "multi_sentence": "multi_sentence.wav",
    "descending_speech": "descending_speech.wav",
}

REFERENCE_TRANSCRIPTS: Dict[str, str] = {
    "single_sentence": "single_sentence.txt",
    "paused_speech": "paused_speech.txt",
    "continuous_speech": "continuous_speech.txt",
    "multi_sentence": "multi_sentence.txt",
    "descending_speech": "descending_speech.txt",
}

MAX_WER = 0.10


def _missing_audio() -> List[str]:
    missing: List[str] = []
    for name, filename in REQUIRED_AUDIO.items():
        if not (AUDIO_DIR / filename).exists():
            missing.append(f"{name}: {filename}")
    return missing


def _missing_reference_transcripts() -> List[str]:
    missing: List[str] = []
    for name, filename in REFERENCE_TRANSCRIPTS.items():
        if not (AUDIO_DIR / filename).exists():
            missing.append(f"{name}: {filename}")
    return missing


def _normalize_transcript(text: str) -> str:
    text = text.lower().replace("...", " ").replace("\u2026", " ")
    text = re.sub(r"[^a-z0-9\\s]", " ", text)
    text = re.sub(r"\\s+", " ", text).strip()
    return text


def _word_error_rate(reference: str, hypothesis: str) -> float:
    ref_words = _normalize_transcript(reference).split()
    hyp_words = _normalize_transcript(hypothesis).split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    prev = list(range(len(hyp_words) + 1))
    for i, ref_word in enumerate(ref_words, start=1):
        cur = [i]
        for j, hyp_word in enumerate(hyp_words, start=1):
            if ref_word == hyp_word:
                cur.append(prev[j - 1])
            else:
                cur.append(1 + min(prev[j - 1], prev[j], cur[j - 1]))
        prev = cur
    dist = prev[-1]
    return dist / max(1, len(ref_words))


def _extract_srt_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return ""
    lines: List[str] = []
    for line in text.splitlines():
        if "-->" in line:
            continue
        if line.strip().isdigit():
            continue
        if not line.strip():
            continue
        lines.append(line.strip())
    return " ".join(lines)


@pytest.fixture(scope="session")
def integration_model():
    if not ffmpeg_ok():
        pytest.skip("ffmpeg not available on PATH")
    missing = _missing_audio()
    if missing:
        pytest.skip("Missing audio fixtures: " + ", ".join(missing))
    missing_refs = _missing_reference_transcripts()
    if missing_refs:
        pytest.skip("Missing reference transcripts: " + ", ".join(missing_refs))
    model, _device_used, _compute_type = init_whisper_model_internal(
        model_name="tiny",
        device="cpu",
        strict_cuda=False,
        event_handler=None,
    )
    return model


@pytest.fixture(scope="session")
def base_cfg() -> ResolvedConfig:
    cfg = ResolvedConfig()
    return cfg


def run_pipeline(
    *,
    audio_path: Path,
    model,
    cfg: ResolvedConfig,
    tmp_path: Path,
) -> Tuple[Path, List]:
    wav_path = tmp_path / f"{audio_path.stem}.wav"
    to_wav_16k_mono(str(audio_path), str(wav_path))

    silences = detect_silences(
        str(wav_path),
        min_silence_dur=cfg.silence.silence_min_dur,
        silence_threshold_db=cfg.silence.silence_threshold_db,
    )

    segments_iter, _info = model.transcribe(
        str(wav_path),
        vad_filter=cfg.transcription.vad_filter,
        language=None,
        word_timestamps=True,
        temperature=0.0,
    )
    segments = list(segments_iter)
    words = collect_words(segments)

    if words:
        subs = chunk_words_to_subtitles(words, cfg, silences)
    else:
        subs = chunk_segments_to_subtitles(segments, cfg)

    subs = apply_silence_alignment(subs, silences)

    subs = hygiene_and_polish(
        subs,
        min_gap=cfg.formatting.min_gap,
        pad=cfg.formatting.pad,
        silence_intervals=silences,
    )

    out_path = tmp_path / f"{audio_path.stem}.srt"
    write_srt(
        subs,
        out_path,
        max_chars=cfg.formatting.max_chars,
        max_lines=cfg.formatting.max_lines,
    )
    return out_path, subs


@pytest.mark.parametrize("fixture_key", list(REQUIRED_AUDIO.keys()))
def test_integration_audio_fixture(
    fixture_key: str,
    integration_model,
    base_cfg: ResolvedConfig,
    update_baselines: bool,
    tmp_path: Path,
):
    audio_path = AUDIO_DIR / REQUIRED_AUDIO[fixture_key]
    if not audio_path.exists():
        pytest.skip(f"Missing audio fixture: {audio_path}")
    reference_path = AUDIO_DIR / REFERENCE_TRANSCRIPTS[fixture_key]
    if not reference_path.exists():
        pytest.skip(f"Missing reference transcript: {reference_path}")

    out_path, _subs = run_pipeline(
        audio_path=audio_path,
        model=integration_model,
        cfg=base_cfg,
        tmp_path=tmp_path,
    )

    baseline_path = BASELINE_DIR / f"{fixture_key}.srt"
    baseline_path.parent.mkdir(parents=True, exist_ok=True)

    if update_baselines:
        baseline_path.write_text(out_path.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        if not baseline_path.exists():
            raise AssertionError(
                f"Baseline missing for {fixture_key}. "
                "Run pytest -m integration --update-baselines to generate it."
            )

        compare_srt_timing(out_path, baseline_path)

        # Compare text similarity (WER) against baseline output.
        baseline_text = _extract_srt_text(baseline_path)
        actual_text = _extract_srt_text(out_path)
        wer = _word_error_rate(baseline_text, actual_text)
        if wer > MAX_WER:
            raise AssertionError(
                f"WER too high vs baseline ({wer:.3f} > {MAX_WER:.3f}). "
                f"Baseline: {baseline_text.strip()} "
                f"Actual: {actual_text.strip()}"
            )

    reference_text = reference_path.read_text(encoding="utf-8")
    actual_text = _extract_srt_text(out_path)
    ref_wer = _word_error_rate(reference_text, actual_text)
    if ref_wer > MAX_WER:
        raise AssertionError(
            f"WER too high vs reference ({ref_wer:.3f} > {MAX_WER:.3f}). "
            f"Reference: {reference_text.strip()} "
            f"Actual: {actual_text.strip()}"
        )
