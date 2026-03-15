#!/usr/bin/env python3
"""Data models for Local SRT.

This module contains all data classes used throughout the application:
- FormattingConfig: Subtitle formatting defaults
- TranscriptionConfig: Model transcription tuning defaults
- SilenceConfig: Silence detection defaults
- ResolvedConfig: Nested configuration container
- SubtitleBlock: Represents a subtitle cue with timing and text
- WordItem: Represents a single transcribed word with timing
"""
from __future__ import annotations

from dataclasses import dataclass, field
import enum
from typing import List, Optional


# ============================================================
# Configuration
# ============================================================

@dataclass
class FormattingConfig:
    """Subtitle formatting and timing constraints."""

    # caption formatting
    max_chars: int = 42
    max_lines: int = 2

    # readability / timing heuristics
    target_cps: float = 17.0
    min_dur: float = 1.0
    max_dur: float = 6.0

    # punctuation splitting
    allow_commas: bool = True
    allow_medium: bool = True
    prefer_punct_splits: bool = False

    # timing polish
    min_gap: float = 0.08
    pad: float = 0.00


@dataclass
class TranscriptionConfig:
    """Model transcription tuning parameters."""

    vad_filter: bool = True
    condition_on_previous_text: bool = True
    no_speech_threshold: float = 0.6
    log_prob_threshold: float = -1.0
    compression_ratio_threshold: float = 2.4
    initial_prompt: str = ""


@dataclass
class SilenceConfig:
    """Silence detection parameters."""

    silence_min_dur: float = 0.2
    silence_threshold_db: float = -35.0


@dataclass
class ResolvedConfig:
    """Resolved configuration for subtitle generation."""

    formatting: FormattingConfig = field(default_factory=FormattingConfig)
    transcription: TranscriptionConfig = field(default_factory=TranscriptionConfig)
    silence: SilenceConfig = field(default_factory=SilenceConfig)


class PipelineMode(enum.Enum):
    GENERAL = "general"
    SHORTS = "shorts"
    TRANSCRIPT = "transcript"


# ============================================================
# Subtitle Data Structures
# ============================================================

@dataclass
class SubtitleBlock:
    """Represents a single subtitle cue with timing and text.

    Attributes:
        start: Start time in seconds
        end: End time in seconds
        lines: List of text lines to display
        speaker: Optional speaker label to prefix in outputs
    """
    start: float
    end: float
    lines: List[str]
    speaker: Optional[str] = None


@dataclass
class WordItem:
    """Represents a single transcribed word with timing.

    Attributes:
        start: Start time in seconds
        end: End time in seconds
        text: The word text
    """
    start: float
    end: float
    text: str
