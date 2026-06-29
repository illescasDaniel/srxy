from __future__ import annotations

import asyncio

import pytest
from tests.tui.helpers import assert_svg_snapshot
from textual.app import App, ComposeResult
from textual.widgets import Button, Input

from srxy.cli import build_parser
from srxy.tui.app import SrxyApp
from srxy.tui.query_builder import QueryBuilder


pytestmark = [pytest.mark.integration, pytest.mark.tui]


class _QueryBuilderApp(App[None]):
	def __init__(self, *, initial_query: str = ""):
		super().__init__()
		self._initial_query = initial_query

	def compose(self) -> ComposeResult:
		yield QueryBuilder(id="query-builder", initial_query=self._initial_query)

	def builder(self) -> QueryBuilder:
		return self.query_one("#query-builder", QueryBuilder)


@pytest.mark.parametrize("theme", ["textual-light", "textual-dark"])
def test_given_builder_with_or_terms_when_screenshot_then_matches_snapshot(theme: str):
	# given
	app = _QueryBuilderApp(initial_query="revenue|amphibian|person|thank you")
	app.theme = theme

	async def run():
		async with app.run_test(size=(100, 14)) as pilot:
			await pilot.pause()
			svg = app.export_screenshot(title="query-builder-or-terms")
			assert_svg_snapshot(f"query_builder_or_terms_{theme}", svg)

	asyncio.run(run())


@pytest.mark.parametrize("theme", ["textual-light", "textual-dark"])
def test_given_advanced_mode_when_screenshot_then_matches_snapshot(theme: str):
	# given
	app = _QueryBuilderApp(initial_query="(red|blue)&color")
	app.theme = theme

	async def run():
		async with app.run_test(size=(100, 12)) as pilot:
			await pilot.pause()
			await pilot.click("#mode-toggle-button")
			await pilot.pause()
			svg = app.export_screenshot(title="query-builder-advanced")
			assert_svg_snapshot(f"query_builder_advanced_{theme}", svg)

	asyncio.run(run())


@pytest.mark.parametrize("theme", ["textual-light", "textual-dark"])
def test_given_invalid_advanced_query_when_screenshot_then_matches_snapshot(theme: str):
	# given
	app = _QueryBuilderApp()
	app.theme = theme

	async def run():
		async with app.run_test(size=(100, 12)) as pilot:
			await pilot.pause()
			builder = app.builder()
			await pilot.click("#mode-toggle-button")
			await pilot.pause()
			builder.query_one("#query-raw-input", Input).value = "(foo"
			await pilot.pause()
			svg = app.export_screenshot(title="query-builder-invalid")
			assert_svg_snapshot(f"query_builder_invalid_{theme}", svg)

	asyncio.run(run())


@pytest.mark.parametrize("theme", ["textual-light", "textual-dark"])
def test_given_full_tui_when_screenshot_then_shows_advanced_toggle(theme: str):
	# given
	args = build_parser().parse_args(["revenue|amphibian", "."])
	app = SrxyApp(args, auto_start=False)
	app.theme = theme

	async def run():
		async with app.run_test(size=(100, 30)) as pilot:
			await pilot.pause()
			svg = app.export_screenshot(title="srxy-tui-advanced-toggle")
			assert_svg_snapshot(f"srxy_app_advanced_toggle_{theme}", svg)

	asyncio.run(run())


def test_given_grouped_query_in_advanced_when_switching_to_builder_then_matches_snapshot():
	# given
	app = _QueryBuilderApp(initial_query="(red|blue)&color")
	app.theme = "textual-light"

	async def run():
		async with app.run_test(size=(100, 14)) as pilot:
			await pilot.pause()
			builder = app.builder()
			await pilot.click("#mode-toggle-button")
			await pilot.pause(delay=0.2)
			await pilot.click(builder.query_one("#mode-toggle-button", Button))
			await pilot.pause(delay=0.2)
			svg = app.export_screenshot(title="query-builder-round-trip")
			assert_svg_snapshot("query_builder_round_trip_light", svg)

	asyncio.run(run())
