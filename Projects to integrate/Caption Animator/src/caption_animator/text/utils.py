"""
Text utilities for ASS format handling.

This module provides utilities for working with ASS text, including tag stripping,
newline conversion, and whitespace normalization.
"""

import re


def strip_ass_tags(text: str) -> str:
    """
    Remove ASS override tags from text.

    This removes all override blocks like {\\...} to get the visible text only.

    Args:
        text: Text containing ASS tags

    Returns:
        Text with all override tags removed

    Example:
        >>> strip_ass_tags("{\\fad(120,120)}Hello world")
        'Hello world'
    """
    return re.sub(r"\{[^}]*\}", "", text)


def ass_newlines_to_real(text: str) -> str:
    """
    Convert ASS newline escape sequences to real newlines.

    ASS format uses:
    - \\N for hard line breaks
    - \\n for soft line breaks

    Both are converted to Python's \\n character for manipulation.

    Args:
        text: Text with ASS newline sequences

    Returns:
        Text with real newline characters

    Example:
        >>> ass_newlines_to_real("Line 1\\\\NLine 2")
        'Line 1\\nLine 2'
    """
    return text.replace(r"\N", "\n").replace(r"\n", "\n")


def real_newlines_to_ass(text: str) -> str:
    """
    Convert real newlines to ASS escape sequences.

    Python's \\n characters are converted to \\N (hard line breaks) for ASS format.

    Args:
        text: Text with real newline characters

    Returns:
        Text with ASS \\N escape sequences

    Example:
        >>> real_newlines_to_ass("Line 1\\nLine 2")
        'Line 1\\\\NLine 2'
    """
    return text.replace("\n", r"\N")


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace in text.

    - Converts all line endings to \\n
    - Collapses multiple spaces/tabs to single space
    - Preserves explicit newlines
    - Strips leading/trailing whitespace

    Args:
        text: Text to normalize

    Returns:
        Normalized text

    Example:
        >>> normalize_whitespace("Hello    world\\r\\nNew line")
        'Hello world\\nNew line'
    """
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Collapse multiple spaces/tabs (but keep newlines)
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()
