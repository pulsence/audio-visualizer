#!/usr/bin/env python3
"""Speaker diarization utilities for Local SRT."""
from __future__ import annotations

from typing import Any, List, Tuple


def is_diarization_available() -> bool:
    """Return True if pyannote.audio is installed."""
    try:
        import pyannote.audio  # noqa: F401

        return True
    except Exception:
        return False


def load_diarization_pipeline(hf_token: str) -> Any:
    """Load the pyannote speaker diarization pipeline."""
    from pyannote.audio import Pipeline

    if not hf_token:
        raise ValueError("HF token is required to load the diarization pipeline.")
    return Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=hf_token)


def run_diarization(pipeline: Any, audio_path: str) -> List[Tuple[float, float, str]]:
    """Run diarization and return (start, end, speaker_label) tuples."""
    diarization = pipeline(audio_path)
    results: List[Tuple[float, float, str]] = []
    for segment, _, label in diarization.itertracks(yield_label=True):
        results.append((float(segment.start), float(segment.end), str(label)))
    results.sort(key=lambda x: (x[0], x[1]))
    return results


def _assign_segment_speaker(segment: Any, speaker: str | None) -> Any:
    if hasattr(segment, "_replace") and hasattr(segment, "_fields"):
        if "speaker" in getattr(segment, "_fields", ()):
            return segment._replace(speaker=speaker)
    try:
        setattr(segment, "speaker", speaker)
    except Exception:
        pass
    return segment


def assign_speakers(
    segments: List[Any],
    diarization: List[Tuple[float, float, str]],
) -> List[Any]:
    """Assign speakers to segments based on maximum overlap."""
    updated: List[Any] = []
    for seg in segments:
        s_start = float(getattr(seg, "start", 0.0))
        s_end = float(getattr(seg, "end", 0.0))
        best_label = None
        best_overlap = 0.0

        for d_start, d_end, label in diarization:
            overlap = max(0.0, min(s_end, d_end) - max(s_start, d_start))
            if overlap > best_overlap:
                best_overlap = overlap
                best_label = label

        updated.append(_assign_segment_speaker(seg, best_label))

    return updated
