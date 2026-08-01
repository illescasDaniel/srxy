from __future__ import annotations

from pathlib import Path

import pytest

from srxy.adapters.inbound.gui.preview import format_preview_html, format_preview_message


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
