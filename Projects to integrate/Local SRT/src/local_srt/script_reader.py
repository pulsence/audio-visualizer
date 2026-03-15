#!/usr/bin/env python3
"""Script reader utilities for Local SRT."""
from __future__ import annotations

from pathlib import Path
from typing import List

from docx import Document

from .text_processing import normalize_spaces


MAX_PROMPT_CHARS = 900


def read_docx(path: Path) -> str:
    """Read a .docx file and return a prompt string.

    Non-empty paragraphs are joined with a single space. List items
    (paragraphs whose style name starts with "List") are treated as
    individual sentence units.
    """
    doc = Document(str(path))
    units: List[str] = []
    for para in doc.paragraphs:
        text = normalize_spaces(para.text)
        if not text:
            continue
        style_name = getattr(getattr(para, "style", None), "name", "") or ""
        if style_name.startswith("List"):
            if text[-1] not in ".?!;":
                text = f"{text}."
            units.append(text)
        else:
            units.append(text)

    combined = normalize_spaces(" ".join(units))
    if len(combined) > MAX_PROMPT_CHARS:
        combined = combined[:MAX_PROMPT_CHARS].rstrip()
    return combined
