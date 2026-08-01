from __future__ import annotations

import asyncio

import pytest
from tests.tui.helpers import assert_svg_snapshot
from textual.app import App, ComposeResult
from textual.widgets import Checkbox, Static

from srxy.adapters.inbound.tui.modals import SearchOptionsModal
from srxy.application.search_options import SearchOptions


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


def test_given_content_how_ticked_when_toggling_file_contents_off_then_on_then_ticks_remain():
	# given
	app = _SearchOptionsModalHostApp()
	initial = SearchOptions(
		search_names=True,
		search_contents=True,
		search_docs_tags=True,
		ocr=True,
		transcribe=True,
	)

	async def run():
		async with app.run_test(size=(80, 40)) as pilot:
			app.push_screen(SearchOptionsModal(initial), wait_for_dismiss=False)
			await pilot.pause()
			modal = app.screen
			assert isinstance(modal, SearchOptionsModal)
			docs = modal.query_one("#so-docs-tags", Checkbox)
			ocr = modal.query_one("#so-ocr", Checkbox)
			content = modal.query_one("#so-content", Checkbox)
			assert docs.value is True
			assert ocr.value is True

			# when
			content.value = False
			await pilot.pause()

			# then
			assert docs.disabled is True
			assert ocr.disabled is True
			assert docs.value is True
			assert ocr.value is True

			# when
			content.value = True
			await pilot.pause()

			# then
			assert docs.disabled is False
			assert ocr.disabled is False
			assert docs.value is True
			assert ocr.value is True

	asyncio.run(run())
