from __future__ import annotations

import pytest

from srxy.adapters.inbound.gui import preview as preview_module
from srxy.adapters.inbound.gui.preview import (
	PREVIEW_MAX_BYTES,
	PREVIEW_MAX_LINES,
	PREVIEW_PALETTES,
	prepare_preview_text,
	preview_font_family,
	preview_gutter_text,
	segments_for_line,
)


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
	("platform", "expected"),
	[
		("win32", "Consolas"),
		("darwin", "Menlo"),
		("linux", "monospace"),
	],
)
def test_given_platform_when_preview_font_family_then_matches_qml(
	monkeypatch: pytest.MonkeyPatch, platform: str, expected: str
):
	# given
	monkeypatch.setattr(preview_module.sys, "platform", platform)

	# when / then
	assert preview_font_family() == expected


def test_given_python_line_when_segmenting_then_marks_keywords_and_comments():
	# given
	line = "def hello():  # note"

	# when
	segments = segments_for_line(line, ".py")

	# then
	kinds = {line[start:end]: kind for start, end, kind in segments if kind}
	assert kinds.get("def") == "keyword"
	assert any(kind == "comment" for _s, _e, kind in segments)


def test_given_plain_text_when_segmenting_then_returns_single_plain_span():
	# given
	line = "a <b> tag"

	# when
	segments = segments_for_line(line, ".txt")

	# then
	assert segments == [(0, len(line), None)]


def test_given_markdown_heading_when_segmenting_then_marks_heading():
	# given / when
	segments = segments_for_line("# Title", ".md")

	# then
	assert segments == [(0, 7, "heading")]


def test_given_json_line_when_segmenting_then_marks_strings_and_literals():
	# given
	line = '{"ok": true, "n": null}'

	# when
	segments = segments_for_line(line, ".json")

	# then
	kinds = [kind for _s, _e, kind in segments if kind]
	assert "string" in kinds
	assert "keyword" in kinds


def test_given_large_payload_when_preparing_text_then_truncates_by_bytes_and_lines():
	# given
	text = ("line\n" * PREVIEW_MAX_LINES) + "extra\n"

	# when
	prepared, truncated = prepare_preview_text(text)

	# then
	assert truncated is True
	assert prepared.count("\n") + 1 <= PREVIEW_MAX_LINES
	assert len(prepared.encode("utf-8")) <= PREVIEW_MAX_BYTES


def test_given_line_count_when_building_gutter_then_right_aligns_numbers():
	# given / when
	gutter = preview_gutter_text(12)

	# then
	assert gutter.splitlines()[0].endswith("1")
	assert gutter.splitlines()[-1].endswith("12")
	assert len(gutter.splitlines()) == 12


def test_given_zero_lines_when_building_gutter_then_empty():
	# given / when / then
	assert preview_gutter_text(0) == ""


def test_given_long_python_file_when_preparing_then_still_returns_capped_plain_text():
	# given — exceeds the old 500-line plain fallback
	text = "def hello():\n\treturn 1\n" * 300

	# when
	prepared, truncated = prepare_preview_text(text)

	# then
	assert "def hello" in prepared
	assert "\n" in prepared
	assert "<" not in prepared  # no HTML markup in the document
	assert truncated is False or prepared.count("\n") + 1 <= PREVIEW_MAX_LINES


def test_given_themes_when_reading_palettes_then_keyword_colors_differ():
	# given / when / then
	assert PREVIEW_PALETTES["light"].keyword == "#0550ae"
	assert PREVIEW_PALETTES["dark"].keyword == "#ff7b72"
	assert PREVIEW_PALETTES["light"].gutter != PREVIEW_PALETTES["dark"].gutter
