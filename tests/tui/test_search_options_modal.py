from __future__ import annotations

import asyncio

import pytest
from tests.tui.helpers import assert_svg_snapshot
from textual.app import App, ComposeResult
from textual.widgets import Static

from srxy.tui.modals import SearchOptionsModal
from srxy.tui.search_options import SearchOptions


pytestmark = [pytest.mark.integration, pytest.mark.tui]


class _SearchOptionsModalHostApp(App[None]):
	def compose(self) -> ComposeResult:
		yield Static("host", id="host")


@pytest.mark.parametrize("theme", ["textual-light", "textual-dark"])
def test_given_search_options_modal_when_screenshot_then_matches_snapshot(theme: str):
	# given
	app = _SearchOptionsModalHostApp()
	app.theme = theme
	initial = SearchOptions(
		search_names=True,
		search_contents=True,
		semantic=True,
		include_archives=False,
	)

	async def run():
		async with app.run_test(size=(80, 30)) as pilot:
			app.push_screen(SearchOptionsModal(initial), wait_for_dismiss=False)
			await pilot.pause()
			modal = app.screen
			assert isinstance(modal, SearchOptionsModal)
			svg = app.export_screenshot(title="search-options-modal")
			assert_svg_snapshot(f"search_options_modal_{theme}", svg)

	asyncio.run(run())
