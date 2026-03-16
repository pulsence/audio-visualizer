"""Audio-reactive analysis for caption animations.

Provides amplitude analysis from audio files to drive reactive caption
animations (pulse, beat_pop, emphasis_glow).  Results are cached in the
WorkspaceContext analysis cache to avoid recomputation across re-renders.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AudioReactiveAnalysis:
    """Result of audio-reactive analysis for caption rendering.

    Attributes
    ----------
    smoothed_amplitude : list[float]
        Per-frame smoothed amplitude values in [0.0, 1.0].
    peak_markers : list[int]
        Frame indices where amplitude peaks occur.
    emphasis_markers : list[int]
        Frame indices where sustained emphasis is detected.
    bpm_estimate : float
        Estimated beats per minute from onset detection.
    frame_count : int
        Total number of frames in the analysis.
    fps : float
        Frame rate used during analysis.
    duration_ms : int
        Duration of the audio in milliseconds.
    """

    smoothed_amplitude: List[float] = field(default_factory=list)
    peak_markers: List[int] = field(default_factory=list)
    emphasis_markers: List[int] = field(default_factory=list)
    bpm_estimate: float = 0.0
    frame_count: int = 0
    fps: float = 30.0
    duration_ms: int = 0


def analyze_audio(
    audio_path: Path,
    fps: float = 30.0,
    duration_ms: int = 0,
) -> AudioReactiveAnalysis:
    """Analyze an audio file for reactive caption animation data.

    Uses librosa for amplitude envelope extraction, onset detection,
    and tempo estimation.  The analysis is designed to be run on a
    background thread.

    Parameters
    ----------
    audio_path : Path
        Path to the audio file to analyze.
    fps : float
        Target frame rate for per-frame amplitude data.
    duration_ms : int
        Duration to analyze in milliseconds.  0 means the full file.

    Returns
    -------
    AudioReactiveAnalysis
        Analysis results suitable for driving reactive animations.
    """
    import numpy as np

    try:
        import librosa
    except ImportError:
        logger.warning("librosa not available; returning empty analysis")
        return AudioReactiveAnalysis(fps=fps, duration_ms=duration_ms)

    # Load audio
    duration_sec = duration_ms / 1000.0 if duration_ms > 0 else None
    y, sr = librosa.load(str(audio_path), sr=22050, mono=True, duration=duration_sec)

    if len(y) == 0:
        return AudioReactiveAnalysis(fps=fps, duration_ms=duration_ms)

    actual_duration_ms = int((len(y) / sr) * 1000)
    if duration_ms <= 0:
        duration_ms = actual_duration_ms

    # Compute frame-level amplitude envelope
    hop_length = int(sr / fps)
    if hop_length < 1:
        hop_length = 1

    # RMS energy per frame
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]

    # Normalize to [0, 1]
    rms_max = float(np.max(rms)) if len(rms) > 0 else 1.0
    if rms_max > 0:
        amplitude = (rms / rms_max).tolist()
    else:
        amplitude = [0.0] * len(rms)

    # Smooth amplitude with a simple moving average
    window_size = max(1, int(fps * 0.05))  # 50ms window
    if window_size > 1 and len(amplitude) > window_size:
        kernel = np.ones(window_size) / window_size
        smoothed = np.convolve(amplitude, kernel, mode="same").tolist()
    else:
        smoothed = list(amplitude)

    frame_count = len(smoothed)

    # Detect peaks (frames with amplitude above 85th percentile and local maxima)
    peak_markers: List[int] = []
    if len(smoothed) > 2:
        threshold = float(np.percentile(smoothed, 85))
        for i in range(1, len(smoothed) - 1):
            if (
                smoothed[i] > threshold
                and smoothed[i] >= smoothed[i - 1]
                and smoothed[i] >= smoothed[i + 1]
            ):
                peak_markers.append(i)

    # Detect emphasis regions (sustained high amplitude)
    emphasis_markers: List[int] = []
    if len(smoothed) > 0:
        emphasis_threshold = float(np.percentile(smoothed, 75))
        sustained_frames = max(1, int(fps * 0.2))  # 200ms sustained
        count = 0
        for i, val in enumerate(smoothed):
            if val > emphasis_threshold:
                count += 1
                if count >= sustained_frames:
                    emphasis_markers.append(i)
            else:
                count = 0

    # BPM estimate via onset detection
    bpm_estimate = 0.0
    try:
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        if hasattr(tempo, '__len__'):
            bpm_estimate = float(tempo[0]) if len(tempo) > 0 else 0.0
        else:
            bpm_estimate = float(tempo)
    except Exception:
        logger.debug("BPM estimation failed, using 0.0")

    return AudioReactiveAnalysis(
        smoothed_amplitude=smoothed,
        peak_markers=peak_markers,
        emphasis_markers=emphasis_markers,
        bpm_estimate=bpm_estimate,
        frame_count=frame_count,
        fps=fps,
        duration_ms=duration_ms,
    )


def make_cache_key(audio_path: Path, fps: float, duration_ms: int) -> tuple:
    """Build a WorkspaceContext analysis cache key for audio-reactive data.

    Parameters
    ----------
    audio_path : Path
        Path to the audio file.
    fps : float
        Frame rate used for analysis.
    duration_ms : int
        Duration used for analysis.

    Returns
    -------
    tuple
        Cache key suitable for WorkspaceContext.store_analysis().
    """
    return (str(audio_path), "audio_reactive", f"{fps}_{duration_ms}")
