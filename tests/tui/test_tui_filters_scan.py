from __future__ import annotations

import asyncio
from typing import Any

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Checkbox, Static

from srxy.adapters.inbound.cli.cli import build_parser
from srxy.adapters.inbound.tui.app import SrxyApp
from srxy.adapters.inbound.tui.modals import SearchFiltersModal
from srxy.application.search_filters import default_search_filters
from srxy.application.settings import ScanSwitches, load_persisted_search_prefs


pytestmark = [pytest.mark.integration, pytest.mark.tui]

_SCAN_IDS = ("sf-subdirs", "sf-archives", "sf-hidden", "sf-noise", "sf-noise-files", "sf-match-skipped-names")


class _ModalHostApp(App[None]):
	def compose(self) -> ComposeResult:
		yield Static("host", id="host")


def test_given_filters_modal_when_opened_then_scan_section_is_first_and_switches_present():
	# given
	app = _ModalHostApp()

	async def run():
		async with app.run_test(size=(80, 30)) as pilot:
			app.push_screen(
				SearchFiltersModal(default_search_filters(), scan=ScanSwitches(include_archives=True)),
				wait_for_dismiss=False,
			)
			await pilot.pause()

			# then
			scroll = app.screen.query_one("#search-filters-scroll")
			first = scroll.children[0]
			assert "scan" in str(first.render()).lower() or "files" in str(first.render()).lower()
			for checkbox_id in _SCAN_IDS:
				assert app.screen.query_one(f"#{checkbox_id}", Checkbox)
			assert app.screen.query_one("#sf-archives", Checkbox).value is True
			assert app.screen.query_one("#sf-subdirs", Checkbox).value is True

	asyncio.run(run())


def test_given_scan_switch_toggled_when_apply_pressed_then_result_carries_switches():
	# given
	app = _ModalHostApp()
	results: list[Any] = []

	async def run():
		async with app.run_test(size=(80, 30)) as pilot:
			app.push_screen(
				SearchFiltersModal(default_search_filters()), wait_for_dismiss=False, callback=results.append
			)
			await pilot.pause()
			app.screen.query_one("#sf-hidden", Checkbox).value = True
			app.screen.query_one("#sf-subdirs", Checkbox).value = False
			await pilot.pause()

			# when
			await pilot.click("#search-filters-apply")
			await pilot.pause()

			# then
			assert results[0].scan == ScanSwitches(include_subdirectories=False, include_hidden=True)

	asyncio.run(run())


def test_given_scan_switch_toggled_when_cancel_pressed_then_result_none():
	# given
	app = _ModalHostApp()
	results: list[Any] = []

	async def run():
		async with app.run_test(size=(80, 30)) as pilot:
			app.push_screen(
				SearchFiltersModal(default_search_filters()), wait_for_dismiss=False, callback=results.append
			)
			await pilot.pause()
			app.screen.query_one("#sf-archives", Checkbox).value = True
			await pilot.pause()

			# when
			await pilot.click("#search-filters-cancel")
			await pilot.pause()

			# then
			assert results == [None]

	asyncio.run(run())


def test_given_file_names_off_when_filters_opened_then_skipped_names_disabled():
	# given
	app = _ModalHostApp()

	async def run():
		async with app.run_test(size=(80, 30)) as pilot:
			# when
			app.push_screen(SearchFiltersModal(default_search_filters(), search_names=False), wait_for_dismiss=False)
			await pilot.pause()

			# then
			assert app.screen.query_one("#sf-match-skipped-names", Checkbox).disabled is True

	asyncio.run(run())


def test_given_tui_when_filters_applied_with_scan_switch_then_options_updated_and_persisted(
	tmp_path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	app = SrxyApp(build_parser().parse_args(["hello", "."]), auto_start=False)

	async def run():
		async with app.run_test(size=(120, 40)) as pilot:
			await pilot.pause()
			app.action_open_search_filters()
			await pilot.pause()
			app.screen.query_one("#sf-archives", Checkbox).value = True
			app.screen.query_one("#sf-persist", Checkbox).value = True
			await pilot.pause()

			# when
			await pilot.click("#search-filters-apply")
			await pilot.pause()

			# then
			assert app.search_options.include_archives is True
			assert app._args.include_archives is True
			prefs = load_persisted_search_prefs()
			assert prefs.scan is not None
			assert prefs.scan.include_archives is True

	asyncio.run(run())


def test_given_persisted_scan_when_tui_starts_then_options_carry_switches(tmp_path, monkeypatch: pytest.MonkeyPatch):
	# given
	from srxy.application.search_options import SearchOptions
	from srxy.application.settings import save_persisted_filters

	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	save_persisted_filters(
		persist_filters=True,
		filters=default_search_filters(),
		options=SearchOptions(include_hidden=True, include_subdirectories=False),
	)

	# when
	app = SrxyApp(build_parser().parse_args(["hello", "."]), auto_start=False)

	# then
	assert app.search_options.include_hidden is True
	assert app.search_options.include_subdirectories is False
