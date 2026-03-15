#!/usr/bin/env python3
"""Tests for script_reader module."""
from __future__ import annotations

from pathlib import Path

from docx import Document

from local_srt.script_reader import MAX_PROMPT_CHARS, read_docx


def test_read_docx_paragraphs_and_list_items():
    fixture = Path(__file__).parent / "fixtures" / "script_reader" / "sample.docx"
    text = read_docx(fixture)
    expected = (
        "This is the first paragraph. "
        "This is the second paragraph. "
        "First bullet. "
        "Second bullet. "
        "Final line."
    )
    assert text == expected


def test_read_docx_truncation(tmp_path):
    doc = Document()
    long_text = "word " * 300
    doc.add_paragraph(long_text)
    path = tmp_path / "long.docx"
    doc.save(path)

    text = read_docx(path)
    assert len(text) <= MAX_PROMPT_CHARS
    assert text == long_text.strip()[:MAX_PROMPT_CHARS].rstrip()
