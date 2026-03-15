"""Parser helpers for subtitle file I/O.

Provides functions to read and write subtitle files in SRT, ASS, and
VTT formats using pysubs2.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pysubs2

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def parse_srt_file(path: str) -> list:
    """Parse an .srt file into a list of SubtitleEntry objects.

    Args:
        path: Filesystem path to the .srt file.

    Returns:
        Ordered list of SubtitleEntry instances.
    """
    from audio_visualizer.ui.tabs.srtEdit.document import SubtitleEntry

    subs = pysubs2.load(path, encoding="utf-8")
    entries: list[SubtitleEntry] = []
    for i, event in enumerate(subs, start=1):
        text = event.plaintext.strip()
        if not text:
            continue
        entries.append(
            SubtitleEntry(
                index=i,
                start_ms=event.start,
                end_ms=event.end,
                text=text,
                speaker=None,
                dirty=False,
            )
        )
    # Re-index after filtering empty entries
    for i, entry in enumerate(entries, start=1):
        entry.index = i
    return entries


def write_srt_file(entries: list, path: str) -> None:
    """Write a list of SubtitleEntry objects to an .srt file.

    Args:
        entries: Ordered list of SubtitleEntry instances.
        path: Filesystem path for the output .srt file.
    """
    subs = pysubs2.SSAFile()
    subs.info["Title"] = ""
    for entry in entries:
        event = pysubs2.SSAEvent(
            start=entry.start_ms,
            end=entry.end_ms,
            text=entry.text.replace("\n", "\\N"),
        )
        subs.events.append(event)
    subs.save(path, format_="srt", encoding="utf-8")
    logger.info("Wrote %d entries to %s", len(entries), path)


def parse_ass_file(path: str) -> list:
    """Parse an .ass file into a list of SubtitleEntry objects.

    Args:
        path: Filesystem path to the .ass file.

    Returns:
        Ordered list of SubtitleEntry instances.
    """
    from audio_visualizer.ui.tabs.srtEdit.document import SubtitleEntry

    subs = pysubs2.load(path, encoding="utf-8")
    entries: list[SubtitleEntry] = []
    for i, event in enumerate(subs, start=1):
        if event.is_comment:
            continue
        text = event.plaintext.strip()
        if not text:
            continue
        entries.append(
            SubtitleEntry(
                index=i,
                start_ms=event.start,
                end_ms=event.end,
                text=text,
                speaker=event.name if event.name else None,
                dirty=False,
            )
        )
    for i, entry in enumerate(entries, start=1):
        entry.index = i
    return entries


def parse_vtt_file(path: str) -> list:
    """Parse a .vtt (WebVTT) file into a list of SubtitleEntry objects.

    Args:
        path: Filesystem path to the .vtt file.

    Returns:
        Ordered list of SubtitleEntry instances.
    """
    from audio_visualizer.ui.tabs.srtEdit.document import SubtitleEntry

    subs = pysubs2.load(path, encoding="utf-8")
    entries: list[SubtitleEntry] = []
    for i, event in enumerate(subs, start=1):
        text = event.plaintext.strip()
        if not text:
            continue
        entries.append(
            SubtitleEntry(
                index=i,
                start_ms=event.start,
                end_ms=event.end,
                text=text,
                speaker=None,
                dirty=False,
            )
        )
    for i, entry in enumerate(entries, start=1):
        entry.index = i
    return entries
