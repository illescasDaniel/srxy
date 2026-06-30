from __future__ import annotations

import asyncio

import pytest
from tests.tui.helpers import assert_svg_snapshot
from textual.app import App, ComposeResult
from textual.widgets import Static

from srxy.cli import build_parser
from srxy.tui.app import SrxyApp
from srxy.tui.modals import SearchFiltersModal, SearchOptionsModal
from srxy.tui.search_filters import SearchFilters, format_search_filters_summary
from srxy.tui.size_limits import SizeLimits


pytestmark = [pytest.mark.integration, pytest.mark.tui]


class _ModalHostApp(App[None]):
	def compose(self) -> ComposeResult:
		yield Static("host", id="host")


@pytest.mark.parametrize("theme", ["textual-light", "textual-dark"])
def test_given_search_filters_modal_when_screenshot_then_matches_snapshot(theme: str):
	# given
	app = _ModalHostApp()
	app.theme = theme
	initial = SearchFilters(
		top_files="",
		max_matches="50",
		size_limits=SizeLimits(text_mib="100", ocr_mib="50", transcribe_mib="500"),
	)

	async def run():
		async with app.run_test(size=(80, 28)) as pilot:
			app.push_screen(SearchFiltersModal(initial), wait_for_dismiss=False)
			await pilot.pause()
			assert isinstance(app.screen, SearchFiltersModal)
			svg = app.export_screenshot(title="search-filters-modal")
			assert_svg_snapshot(f"search_filters_modal_{theme}", svg)

	asyncio.run(run())


@pytest.mark.parametrize("theme", ["textual-light", "textual-dark"])
def test_given_tui_when_filters_dialog_opened_then_matches_snapshot(theme: str):
	# given
	args = build_parser().parse_args(["hello", "."])
	app = SrxyApp(args, auto_start=False)
	app.theme = theme

	async def run():
		async with app.run_test(size=(100, 30)) as pilot:
			await pilot.pause()
			await pilot.click("#search-filters-button")
			await pilot.pause()
			assert isinstance(app.screen, SearchFiltersModal)
			svg = app.export_screenshot(title="srxy-tui-filters-open")
			assert_svg_snapshot(f"srxy_app_filters_open_{theme}", svg)

	asyncio.run(run())


@pytest.mark.parametrize("theme", ["textual-light", "textual-dark"])
def test_given_tui_when_advanced_dialog_opened_then_matches_snapshot(theme: str):
	# given
	args = build_parser().parse_args(["hello", ".", "--semantic", "--include-archives"])
	app = SrxyApp(args, auto_start=False)
	app.theme = theme

	async def run():
		async with app.run_test(size=(100, 30)) as pilot:
			await pilot.pause()
			await pilot.click("#search-options-button")
			await pilot.pause()
			assert isinstance(app.screen, SearchOptionsModal)
			svg = app.export_screenshot(title="srxy-tui-advanced-open")
			assert_svg_snapshot(f"srxy_app_advanced_open_{theme}", svg)

	asyncio.run(run())


def test_given_default_filters_when_formatting_summary_then_shows_defaults():
	# given
	filters = SearchFilters(
		top_files="",
		max_matches="50",
		size_limits=SizeLimits(text_mib="100", ocr_mib="50", transcribe_mib="500"),
	)

	# when
	summary = format_search_filters_summary(filters)

	# then
	assert "All files" in summary
	assert "50/file" in summary
	assert "100 MiB" in summary
