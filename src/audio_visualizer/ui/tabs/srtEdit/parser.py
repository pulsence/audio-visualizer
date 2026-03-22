"""Parser helpers for subtitle file I/O.

Provides functions to read and write subtitle files in SRT, ASS, and
VTT formats using pysubs2, and JSON bundle files via the srt.io reader.
Also includes a markdown-stripping helper for plain-text export paths.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import pysubs2

logger = logging.getLogger(__name__)

# Markdown-stripping patterns (order: bold before italic, same as highlighter)
_BOLD_STRIP_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_STRIP_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_HIGHLIGHT_STRIP_RE = re.compile(r"==(.+?)==")


def strip_markdown(text: str) -> str:
    """Remove **bold**, *italic*, and ==highlight== markdown markers.

    Returns the plain-text content with all delimiter characters removed.
    This is intended for SRT/VTT/TXT export where markdown markup should
    not appear in the output.

    >>> strip_markdown("**bold** and *italic* and ==highlight==")
    'bold and italic and highlight'
    """
    text = _BOLD_STRIP_RE.sub(r"\1", text)
    text = _ITALIC_STRIP_RE.sub(r"\1", text)
    text = _HIGHLIGHT_STRIP_RE.sub(r"\1", text)
    return text


def is_bundle_file(path: str) -> bool:
    """Return True if the path looks like a JSON bundle file.

    Recognizes ``.json`` and ``.bundle.json`` extensions.
    """
    p = Path(path)
    if p.suffix.lower() == ".json":
        return True
    # Handle .bundle.json (double suffix)
    if p.name.lower().endswith(".bundle.json"):
        return True
    return False


def parse_bundle_file(path: str) -> list:
    """Parse a JSON bundle file into a list of SubtitleEntry objects.

    Uses ``read_json_bundle()`` as the single bundle entry point and
    populates entries with word-level data and provenance fields.

    Args:
        path: Filesystem path to the .json bundle file.

    Returns:
        Ordered list of SubtitleEntry instances with words populated.
    """
    from audio_visualizer.srt.io import read_json_bundle
    from audio_visualizer.ui.tabs.srtEdit.document import SubtitleEntry

    bundle = read_json_bundle(path)
    entries: list[SubtitleEntry] = []
    for i, sub in enumerate(bundle.get("subtitles", []), start=1):
        entry = SubtitleEntry(
            index=i,
            start_ms=int(round(sub["start"] * 1000)),
            end_ms=int(round(sub["end"] * 1000)),
            text=sub.get("text", ""),
            speaker=sub.get("speaker_label"),
            dirty=False,
            id=sub.get("id"),
            words=list(sub.get("words", [])),
            original_text=sub.get("original_text"),
            source_media_path=sub.get("source_media_path"),
            model_name=sub.get("model_name"),
            alignment_status=sub.get("alignment_status"),
            alignment_confidence=sub.get("alignment_confidence"),
        )
        entries.append(entry)
    return entries


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


def write_srt_file(entries: list, path: str, *, strip_md: bool = False) -> None:
    """Write a list of SubtitleEntry objects to an .srt file.

    Args:
        entries: Ordered list of SubtitleEntry instances.
        path: Filesystem path for the output .srt file.
        strip_md: If True, remove markdown markers from the output text.
    """
    subs = pysubs2.SSAFile()
    subs.info["Title"] = ""
    for entry in entries:
        text = entry.text
        if strip_md:
            text = strip_markdown(text)
        event = pysubs2.SSAEvent(
            start=entry.start_ms,
            end=entry.end_ms,
            text=text.replace("\n", "\\N"),
        )
        subs.events.append(event)
    subs.save(path, format_="srt", encoding="utf-8")
    logger.info("Wrote %d entries to %s (strip_md=%s)", len(entries), path, strip_md)


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
