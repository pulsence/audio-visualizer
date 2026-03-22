"""Markdown-to-ASS conversion helpers.

Converts a limited set of markdown inline styling into ASS override tags
that libass can render.  Supported conversions:

- ``**bold**``  ->  ``{\\b1}bold{\\b0}``
- ``*italic*``  ->  ``{\\i1}italic{\\i0}``
- ``==highlight==``  ->  preserved as ``==highlight==`` markers for
  animation targeting (not turned into static ASS styling).

Nested markers are handled correctly: ``**bold *and italic***`` produces
the expected override nesting.  The ``==highlight==`` markers are left
intact so that word-aware animations can detect emphasis targets and
apply stronger treatment (e.g. bigger scale, brighter color).
"""
from __future__ import annotations

import re
from typing import List, Tuple


# Regex for highlight markers — deliberately matched first so bold/italic
# conversion does not interfere with the ``==`` delimiters.
_HIGHLIGHT_RE = re.compile(r"==(.*?)==")

# Bold: **text** — match non-greedily, avoiding already-converted regions.
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")

# Italic: *text* — single asterisk that is not part of a bold pair.
_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")


def markdown_to_ass(text: str) -> str:
    r"""Convert markdown inline styling to ASS override tags.

    ``==highlight==`` markers are **preserved** — they are not converted
    to ASS tags here.  Downstream animation code can inspect them for
    emphasis targeting, then strip them before final output.

    Args:
        text: Source text possibly containing ``**bold**``, ``*italic*``,
              and ``==highlight==`` markers.

    Returns:
        Text with bold/italic converted to ASS overrides and highlight
        markers left intact.

    Examples:
        >>> markdown_to_ass("Hello **world**")
        'Hello {\\b1}world{\\b0}'
        >>> markdown_to_ass("*italic* text")
        '{\\i1}italic{\\i0} text'
        >>> markdown_to_ass("==important==")
        '==important=='
    """
    if not text:
        return text

    # Step 1: Protect highlight markers from bold/italic conversion by
    # temporarily replacing them with placeholders.
    highlights: List[str] = []

    def _stash_highlight(m: re.Match) -> str:
        idx = len(highlights)
        highlights.append(m.group(0))  # preserve ==...== intact
        return f"\x00HL{idx}\x00"

    text = _HIGHLIGHT_RE.sub(_stash_highlight, text)

    # Step 2: Convert **bold** to ASS overrides.
    # Use lambda to avoid regex interpreting \b as backreference.
    text = _BOLD_RE.sub(lambda m: "{\\b1}" + m.group(1) + "{\\b0}", text)

    # Step 3: Convert *italic* to ASS overrides.
    text = _ITALIC_RE.sub(lambda m: "{\\i1}" + m.group(1) + "{\\i0}", text)

    # Step 4: Restore highlight markers.
    for idx, original in enumerate(highlights):
        text = text.replace(f"\x00HL{idx}\x00", original)

    return text


def strip_highlight_markers(text: str) -> str:
    """Remove ``==`` highlight delimiters, keeping inner text.

    This should be called after animation targeting has already
    identified the highlighted words.

    Args:
        text: Text possibly containing ``==word==`` markers.

    Returns:
        Text with markers removed but content preserved.
    """
    return _HIGHLIGHT_RE.sub(r"\1", text)


def extract_highlight_words(text: str) -> List[str]:
    """Return a list of words/phrases wrapped in ``==...==`` markers.

    Args:
        text: Source text with possible highlight markers.

    Returns:
        List of highlighted strings (without delimiters).
    """
    return _HIGHLIGHT_RE.findall(text)


def strip_ass_overrides(text: str) -> str:
    r"""Remove all ASS override blocks ``{...}`` from *text*.

    This is useful for tokenizing text into words without being
    confused by override tags like ``{\b1}`` or ``{\k50}``.

    Args:
        text: Text with ASS override blocks.

    Returns:
        Plain text with all ``{...}`` blocks removed.
    """
    return re.sub(r"\{[^}]*\}", "", text)


def tokenize_with_ass_tags(
    text: str,
) -> List[Tuple[str, bool]]:
    r"""Split *text* into segments, distinguishing ASS tags from content.

    Returns a list of ``(segment, is_tag)`` tuples where ``is_tag`` is
    ``True`` for ``{...}`` override blocks and ``False`` for content
    between them.

    Args:
        text: Text interspersed with ASS override blocks.

    Returns:
        List of (segment_text, is_tag) tuples.
    """
    result: List[Tuple[str, bool]] = []
    pos = 0
    for m in re.finditer(r"\{[^}]*\}", text):
        if m.start() > pos:
            result.append((text[pos:m.start()], False))
        result.append((m.group(), True))
        pos = m.end()
    if pos < len(text):
        result.append((text[pos:], False))
    return result
