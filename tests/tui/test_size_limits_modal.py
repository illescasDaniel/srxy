from __future__ import annotations

import asyncio

import pytest
from tests.tui.helpers import assert_svg_snapshot
from textual.app import App, ComposeResult
from textual.widgets import Static

from srxy.tui.modals import SizeLimitsModal
from srxy.tui.size_limits import SizeLimits


pytestmark = [pytest.mark.integration, pytest.mark.tui]


class _SizeLimitsModalHostApp(App[None]):
	def compose(self) -> ComposeResult:
		yield Static("host", id="host")


@pytest.mark.parametrize("theme", ["textual-light", "textual-dark"])
def test_given_size_limits_modal_when_screenshot_then_matches_snapshot(theme: str):
	# given
	app = _SizeLimitsModalHostApp()
	app.theme = theme
	initial = SizeLimits(text_mib="100", ocr_mib="50", transcribe_mib="500")

	async def run():
		async with app.run_test(size=(80, 18)) as pilot:
			app.push_screen(SizeLimitsModal(initial), wait_for_dismiss=False)
			await pilot.pause()
			modal = app.screen
			assert isinstance(modal, SizeLimitsModal)
			svg = app.export_screenshot(title="size-limits-modal")
			assert_svg_snapshot(f"size_limits_modal_{theme}", svg)

	asyncio.run(run())
