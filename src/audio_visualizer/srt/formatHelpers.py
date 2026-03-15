#!/usr/bin/env python3
"""Formatting utilities for Local SRT."""
from __future__ import annotations


def format_duration(seconds: float) -> str:
    """Format a duration in seconds as HH:MM:SS or MM:SS.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string (e.g., "1:23:45" or "23:45")
    """
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:d}:{s:02d}"
