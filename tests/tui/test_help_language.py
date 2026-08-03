from __future__ import annotations

import asyncio

import pytest
from tests.tui.helpers import assert_svg_snapshot
from textual.app import App, ComposeResult

from srxy.adapters.inbound.tui.modals import HelpModal
from srxy.i18n import set_language


pytestmark = [pytest.mark.integration, pytest.mark.tui]


class _HelpApp(App[None]):
	def compose(self) -> ComposeResult:
		yield from ()

	def on_mount(self):
		self.push_screen(HelpModal())


@pytest.mark.parametrize("theme", ["textual-light", "textual-dark"])
def test_given_help_modal_when_screenshot_then_shows_language_control(theme: str):
	# given
	set_language("en")
	app = _HelpApp()
	app.theme = theme

	async def run():
		async with app.run_test(size=(80, 36)) as pilot:
			await pilot.pause()
			svg = app.export_screenshot(title="help-language")
			assert_svg_snapshot(f"help_modal_language_{theme}", svg)

	asyncio.run(run())
