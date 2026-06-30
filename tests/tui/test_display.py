from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from tests.tui.helpers import assert_labels_visible, export_app_screenshot
from textual.widgets import DataTable

from srxy.cli import build_parser
from srxy.models import FileSearchResult, LineMatch
from srxy.tui.app import SrxyApp


pytestmark = [pytest.mark.integration, pytest.mark.tui]

_CONTROL_LABELS = (
	"Search",
	"Names",
	"Content",
	"Semantic",
	"Image semantic",
	"OCR",
	"Transcribe",
	"Hidden",
	"Noise",
)
_STATUS_LABELS = ("Match", "Path", "Matched", "Ready", "Quit")


def _build_app(*, theme: str) -> SrxyApp:
	args = build_parser().parse_args([])
	app = SrxyApp(args, auto_start=False)
	app.theme = theme
	return app


@pytest.mark.parametrize("theme", ["textual-light", "textual-dark"])
def test_given_tui_when_screenshot_exported_then_control_labels_are_visible(theme: str):
	# given
	app = _build_app(theme=theme)

	async def run():
		svg = await export_app_screenshot(app)
		assert_labels_visible(svg, _CONTROL_LABELS)

	# when / then
	asyncio.run(run())


@pytest.mark.parametrize("theme", ["textual-light", "textual-dark"])
def test_given_tui_when_screenshot_exported_then_status_and_footer_labels_are_visible(theme: str):
	# given
	app = _build_app(theme=theme)

	async def run():
		svg = await export_app_screenshot(app)
		assert_labels_visible(svg, _STATUS_LABELS)

	# when / then
	asyncio.run(run())


_FILTER_LABELS = ("Top files", "Per file", "Size limits", "Query", "Path", "Advanced")


@pytest.mark.parametrize("theme", ["textual-light", "textual-dark"])
def test_given_tui_when_screenshot_exported_then_field_labels_are_always_visible(theme: str):
	# given
	app = _build_app(theme=theme)

	async def run():
		async with app.run_test(size=(100, 30)) as pilot:
			await pilot.pause()
			svg = app.export_screenshot(title="srxy-tui")
			assert_labels_visible(svg, _FILTER_LABELS)
			assert app.query_one("#filter-max-matches").value == "50"

	# when / then
	asyncio.run(run())


def test_given_option_chips_when_composed_then_neighbors_have_horizontal_gap():
	# given
	app = _build_app(theme="textual-light")

	async def run():
		async with app.run_test(size=(100, 30)) as pilot:
			await pilot.pause()
			names = app.query_one("#opt-names")
			content = app.query_one("#opt-content")
			gap = content.region.x - names.region.x - names.region.width
			assert gap >= 1

	# when / then
	asyncio.run(run())


def test_given_tui_when_composed_then_search_row_has_padding_and_controls_are_slightly_taller():
	# given
	app = _build_app(theme="textual-light")

	async def run():
		async with app.run_test(size=(100, 30)) as pilot:
			await pilot.pause()
			search_bar = app.query_one("#search-bar")
			search_button = app.query_one("#search-button")
			query_input = app.query_one("#query-term-0")
			names_chip = app.query_one("#opt-names")
			assert search_bar.outer_size.height >= 2
			assert search_button.outer_size.height == 1
			assert query_input.outer_size.height == 1
			assert names_chip.outer_size.height >= 1
			svg = app.export_screenshot(title="srxy-tui")
			assert_labels_visible(svg, ("Search", "Names"))

	# when / then
	asyncio.run(run())


@pytest.mark.parametrize("theme", ["textual-light", "textual-dark"])
def test_given_result_selected_when_preview_rendered_then_match_table_headers_are_visible(theme: str, tmp_path: Path):
	# given
	file_path = tmp_path / "notes.txt"
	file_path.write_text("hello world", encoding="utf-8")
	result = FileSearchResult(
		path=file_path,
		score=0.85,
		breakdown={"content": 0.85},
		lines=[LineMatch(line_number=1, text="hello world", score=0.85)],
	)
	args = build_parser().parse_args(["hello", str(tmp_path), "--content-only"])
	app = SrxyApp(args, auto_start=True)
	app.theme = theme

	async def run():
		with (
			patch("srxy.tui.app.run_tui_preflight", new=AsyncMock(return_value=None)),
			patch("srxy.tui.app.execute_search", return_value=([result], [])),
		):
			async with app.run_test(size=(100, 30)) as pilot:
				for _ in range(30):
					await pilot.pause(delay=0.05)
					if app.query_one("#results-table", DataTable).row_count == 1:
						break
				svg = app.export_screenshot(title="srxy-tui")
				assert_labels_visible(svg, ("Location", "Text"))

	# when / then
	asyncio.run(run())
