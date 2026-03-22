"""Tests for caption/core/markdownToAss.py — markdown-to-ASS conversion."""

import pytest

from audio_visualizer.caption.core.markdownToAss import (
    extract_highlight_words,
    markdown_to_ass,
    strip_ass_overrides,
    strip_highlight_markers,
    tokenize_with_ass_tags,
)


class TestMarkdownToAss:
    """Tests for the markdown_to_ass() conversion function."""

    def test_empty_string(self):
        assert markdown_to_ass("") == ""

    def test_plain_text_unchanged(self):
        assert markdown_to_ass("Hello world") == "Hello world"

    def test_bold(self):
        result = markdown_to_ass("Hello **world**")
        assert r"{\b1}" in result
        assert r"{\b0}" in result
        assert "world" in result
        assert "**" not in result

    def test_italic(self):
        result = markdown_to_ass("Hello *world*")
        assert r"{\i1}" in result
        assert r"{\i0}" in result
        assert "world" in result

    def test_bold_and_italic(self):
        result = markdown_to_ass("**bold** and *italic*")
        assert r"{\b1}" in result
        assert r"{\b0}" in result
        assert r"{\i1}" in result
        assert r"{\i0}" in result

    def test_highlight_preserved(self):
        result = markdown_to_ass("==important==")
        assert "==important==" in result
        assert r"{\b1}" not in result

    def test_highlight_with_bold(self):
        result = markdown_to_ass("**bold** and ==highlight==")
        assert r"{\b1}" in result
        assert "==highlight==" in result

    def test_nested_bold_italic(self):
        result = markdown_to_ass("**bold *and italic***")
        assert r"{\b1}" in result

    def test_multiple_bold(self):
        result = markdown_to_ass("**one** and **two**")
        assert result.count(r"{\b1}") == 2
        assert result.count(r"{\b0}") == 2

    def test_multiple_highlights(self):
        result = markdown_to_ass("==one== and ==two==")
        assert "==one==" in result
        assert "==two==" in result


class TestStripHighlightMarkers:
    def test_strip_single(self):
        assert strip_highlight_markers("==word==") == "word"

    def test_strip_in_sentence(self):
        result = strip_highlight_markers("Hello ==world== today")
        assert result == "Hello world today"

    def test_no_markers(self):
        assert strip_highlight_markers("plain text") == "plain text"

    def test_multiple_markers(self):
        result = strip_highlight_markers("==one== ==two==")
        assert result == "one two"


class TestExtractHighlightWords:
    def test_single(self):
        assert extract_highlight_words("==word==") == ["word"]

    def test_multiple(self):
        result = extract_highlight_words("Hello ==world== and ==again==")
        assert result == ["world", "again"]

    def test_none(self):
        assert extract_highlight_words("plain text") == []


class TestStripAssOverrides:
    def test_strip_simple(self):
        result = strip_ass_overrides(r"{\b1}bold{\b0} text")
        assert result == "bold text"

    def test_strip_complex(self):
        result = strip_ass_overrides(r"{\k50}Hello {\k30}world")
        assert result == "Hello world"

    def test_no_overrides(self):
        assert strip_ass_overrides("plain text") == "plain text"


class TestTokenizeWithAssTags:
    def test_plain_text(self):
        result = tokenize_with_ass_tags("Hello world")
        assert result == [("Hello world", False)]

    def test_with_tags(self):
        result = tokenize_with_ass_tags(r"{\b1}bold{\b0} text")
        assert len(result) == 4
        assert result[0] == (r"{\b1}", True)
        assert result[1] == ("bold", False)
        assert result[2] == (r"{\b0}", True)
        assert result[3] == (" text", False)

    def test_empty(self):
        result = tokenize_with_ass_tags("")
        assert result == []
