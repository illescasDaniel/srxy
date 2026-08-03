from __future__ import annotations

import asyncio

import pytest
from tests.tui.helpers import assert_svg_snapshot, normalized_svg_text
from textual.app import App, ComposeResult
from textual.widgets import Static

from srxy.adapters.inbound.tui.modals import ErrorModal
from srxy.application.matching.semantic import semantic_deps_unavailable_message


pytestmark = [pytest.mark.integration, pytest.mark.tui]


class _ErrorModalHostApp(App[None]):
	def compose(self) -> ComposeResult:
		yield Static("host", id="host")


@pytest.mark.parametrize("theme", ["textual-light", "textual-dark"])
def test_given_semantic_deps_error_when_screenshot_then_matches_snapshot(theme: str):
	# given
	app = _ErrorModalHostApp()
	app.theme = theme
	message = semantic_deps_unavailable_message()

	async def run():
		async with app.run_test(size=(80, 16)) as pilot:
			# when
			app.push_screen(ErrorModal(message), wait_for_dismiss=False)
			await pilot.pause()
			assert isinstance(app.screen, ErrorModal)
			svg = app.export_screenshot(title="error-modal-semantic-deps")

			# then
			visible = normalized_svg_text(svg)
			assert "srxy[semantic]" in visible
			assert "GPU" in visible
			assert_svg_snapshot(f"error_modal_semantic_deps_{theme}", svg)

	asyncio.run(run())
