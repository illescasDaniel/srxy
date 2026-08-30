"""PreviewHighlighter applies native QTextCharFormat colours to plain text."""

from __future__ import annotations

import os

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QColor, QTextDocument

from srxy.adapters.inbound.gui.preview import PREVIEW_PALETTES
from srxy.adapters.inbound.gui.preview_highlighter import PreviewHighlighter


pytestmark = [pytest.mark.unit, pytest.mark.gui, pytest.mark.xdist_group("gui")]


@pytest.fixture(scope="module")
def qapp() -> QCoreApplication:
	os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
	app = QCoreApplication.instance()
	if app is None:
		app = QCoreApplication([])
	assert isinstance(app, QCoreApplication)
	return app


def _formats_at(document: QTextDocument, block_number: int) -> list[tuple[int, int, str, str]]:
	block = document.findBlockByNumber(block_number)
	assert block.isValid()
	out: list[tuple[int, int, str, str]] = []
	for ran in block.layout().formats():
		fg = ran.format.foreground().color()
		bg = ran.format.background().color()
		out.append(
			(
				ran.start,
				ran.length,
				fg.name() if fg.isValid() and fg.alpha() > 0 else "",
				bg.name() if bg.isValid() and bg.alpha() > 0 else "",
			)
		)
	return out


def test_given_python_document_when_highlighting_then_one_block_per_line_and_keyword_colour(
	qapp: QCoreApplication,
):
	# given
	document = QTextDocument()
	document.setPlainText("def hello():\n\treturn 1\n")
	highlighter = PreviewHighlighter(document)
	highlighter.set_context(suffix=".py", theme="light")

	# when
	highlighter.rehighlight()

	# then
	assert document.blockCount() >= 2
	formats = _formats_at(document, 0)
	assert any(
		start == 0 and length == 3 and colour == PREVIEW_PALETTES["light"].keyword
		for start, length, colour, _bg in formats
	)


def test_given_find_overlays_when_highlighting_then_current_wins_over_find(qapp: QCoreApplication):
	# given
	document = QTextDocument()
	document.setPlainText("hello hello")
	highlighter = PreviewHighlighter(document)
	highlighter.set_context(suffix=".txt", theme="light")
	highlighter.set_overlays(finds={1: [(0, 5), (6, 11)]}, current={1: [(6, 11)]})

	# when
	highlighter.rehighlight()

	# then
	formats = _formats_at(document, 0)
	backgrounds = {(start, length): bg for start, length, _fg, bg in formats if bg}
	assert backgrounds.get((6, 5)) == PREVIEW_PALETTES["light"].find_current_background
	assert backgrounds.get((0, 5)) == PREVIEW_PALETTES["light"].find_background


def test_given_overlay_change_when_rehighlight_block_then_only_that_block_updates(
	qapp: QCoreApplication,
):
	# given
	document = QTextDocument()
	document.setPlainText("alpha\nbeta\ngamma\n")
	highlighter = PreviewHighlighter(document)
	highlighter.set_context(suffix=".txt", theme="light")
	highlighter.set_overlays(finds={2: [(0, 4)]})
	highlighter.rehighlight()
	assert any(bg == PREVIEW_PALETTES["light"].find_background for _s, _l, _fg, bg in _formats_at(document, 1))

	# when — move overlay to line 3 and refresh only the affected blocks
	previous = highlighter.overlay_line_numbers()
	highlighter.set_overlays(finds={3: [(0, 5)]})
	affected = previous | highlighter.overlay_line_numbers()
	for line in affected:
		block = document.findBlockByNumber(line - 1)
		if block.isValid():
			highlighter.rehighlightBlock(block)

	# then
	assert not any(bg for _s, _l, _fg, bg in _formats_at(document, 1) if bg)
	assert any(bg == PREVIEW_PALETTES["light"].find_background for _s, _l, _fg, bg in _formats_at(document, 2))


def test_given_overlays_when_querying_line_numbers_then_returns_union(qapp: QCoreApplication):
	# given
	document = QTextDocument()
	document.setPlainText("one\ntwo\nthree\n")
	highlighter = PreviewHighlighter(document)
	highlighter.set_overlays(finds={1: [(0, 3)]}, current={3: [(0, 5)]})

	# when / then
	assert highlighter.overlay_line_numbers() == {1, 3}
	assert QColor(PREVIEW_PALETTES["light"].gutter).isValid()
