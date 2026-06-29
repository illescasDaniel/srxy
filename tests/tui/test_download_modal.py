from __future__ import annotations

import asyncio

import pytest
from tests.tui.helpers import assert_svg_snapshot
from textual.app import App, ComposeResult
from textual.widgets import Static

from srxy.tui.modals import DownloadProgressModal


pytestmark = [pytest.mark.integration, pytest.mark.tui]


class _DownloadModalHostApp(App[None]):
	def compose(self) -> ComposeResult:
		yield Static("host", id="host")


@pytest.mark.parametrize("theme", ["textual-light", "textual-dark"])
def test_given_download_progress_modal_when_screenshot_then_matches_snapshot(theme: str):
	# given
	app = _DownloadModalHostApp()
	app.theme = theme

	async def run():
		async with app.run_test(size=(80, 12)) as pilot:
			app.push_screen(DownloadProgressModal("Downloading semantic text model…"), wait_for_dismiss=False)
			await pilot.pause()
			modal = app.screen
			assert isinstance(modal, DownloadProgressModal)
			modal.update_progress(42, 100, "Downloading model files")
			await pilot.pause()
			svg = app.export_screenshot(title="download-progress-modal")
			assert_svg_snapshot(f"download_progress_modal_{theme}", svg)

	asyncio.run(run())
