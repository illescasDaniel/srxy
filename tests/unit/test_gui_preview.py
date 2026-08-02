from __future__ import annotations

from pathlib import Path

import pytest

from srxy.adapters.inbound.gui.preview import (
	PREVIEW_MAX_BYTES,
	PREVIEW_MAX_LINES,
	format_preview_for_file,
	format_preview_html,
	format_preview_message,
	prepare_preview_text,
)


pytestmark = pytest.mark.unit


def test_given_python_snippet_when_formatting_preview_then_includes_line_numbers_and_keywords():
	# given
	path = Path("sample.py")
	text = "def hello():\n\treturn 1\n"

	# when
	html = format_preview_html(path, text)

	# then
	assert ">  1</span>" in html or ">1</span>" in html or "  1" in html
	assert "def" in html
	assert "color:#0550ae" in html
	assert "hello" in html


def test_given_plain_text_when_formatting_preview_then_escapes_and_numbers_lines():
	# given
	path = Path("notes.txt")
	text = "a <b> tag\nsecond"

	# when
	html = format_preview_html(path, text)

	# then
	assert "&lt;b&gt;" in html
	assert "second" in html
	assert html.count("<br/>") == 2


def test_given_status_message_when_formatting_then_escapes_without_line_gutter():
	# given / when
	html = format_preview_message("(No file preview available)")

	# then
	assert "(No file preview available)" in html
	assert "<br/>" not in html


def test_given_large_text_when_formatting_preview_then_caps_html_size_and_shows_footer():
	# given
	line = "x" * 80 + "\n"
	text = line * (PREVIEW_MAX_LINES + 500)
	footer = "Preview truncated (size/line limit reached)."

	# when
	html = format_preview_for_file("big.txt", text, truncated_footer=footer)

	# then
	assert len(html.encode("utf-8")) < PREVIEW_MAX_BYTES * 4
	assert footer in html
	assert html.count("<br/>") <= PREVIEW_MAX_LINES + 1


def test_given_large_payload_when_preparing_text_then_truncates_by_bytes_and_lines():
	# given
	text = ("line\n" * PREVIEW_MAX_LINES) + "extra\n"

	# when
	prepared, truncated = prepare_preview_text(text)

	# then
	assert truncated is True
	assert prepared.count("\n") + 1 <= PREVIEW_MAX_LINES
