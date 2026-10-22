from __future__ import annotations

import asyncio
import dataclasses
from pathlib import Path
from typing import Any

import pytest
from tests.tui.helpers import assert_svg_snapshot, normalized_svg_text
from textual.app import App, ComposeResult
from textual.widgets import Button, Checkbox, Label, Static, TextArea

from srxy.adapters.inbound.cli.cli import build_parser
from srxy.adapters.inbound.tui.app import SrxyApp
from srxy.adapters.inbound.tui.modals import SearchFiltersModal
from srxy.application.search_filters import SearchFilters, default_search_filters
from srxy.application.settings import load_persisted_search_prefs, save_persisted_filters


pytestmark = [pytest.mark.integration, pytest.mark.tui]


class _ModalHostApp(App[None]):
	def compose(self) -> ComposeResult:
		yield Static("host", id="host")


def _label_text(app: App[Any], selector: str) -> str:
	return str(app.screen.query_one(selector, Label).render()).strip()


def _apply_disabled(app: App[Any]) -> bool:
	return app.screen.query_one("#search-filters-apply", Button).disabled


def _filters_with(**changes: Any) -> SearchFilters:
	return dataclasses.replace(default_search_filters(), **changes)


@pytest.fixture
def settings_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
	path = tmp_path / "settings.json"
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(path))
	return path


def test_given_invalid_pattern_when_modal_viewed_then_error_shown_and_apply_disabled():
	# given
	app = _ModalHostApp()

	async def run():
		async with app.run_test(size=(80, 40)) as pilot:
			app.push_screen(SearchFiltersModal(default_search_filters()), wait_for_dismiss=False)
			await pilot.pause()
			assert _label_text(app, "#sf-ignore-error") == ""

			# when
			app.screen.query_one("#sf-ignore", TextArea).text = "[oops"
			await pilot.pause()

			# then
			assert _label_text(app, "#sf-ignore-error") != ""
			assert _apply_disabled(app) is True

	asyncio.run(run())


def test_given_invalid_pattern_when_replaced_by_valid_text_then_apply_enabled_and_error_cleared():
	# given
	app = _ModalHostApp()

	async def run():
		async with app.run_test(size=(80, 40)) as pilot:
			app.push_screen(SearchFiltersModal(default_search_filters()), wait_for_dismiss=False)
			await pilot.pause()
			area = app.screen.query_one("#sf-ignore", TextArea)
			area.text = "[oops"
			await pilot.pause()
			assert _apply_disabled(app) is True

			# when
			area.text = "node_modules/\n*.log"
			await pilot.pause()

			# then
			assert _label_text(app, "#sf-ignore-error") == ""
			assert _apply_disabled(app) is False

	asyncio.run(run())


@pytest.mark.parametrize(
	"text",
	["\n".join(f"p{i}" for i in range(1001)), "a" * 1025],
	ids=["too_many_lines", "line_too_long"],
)
def test_given_list_over_size_caps_when_modal_viewed_then_error_shown_and_apply_disabled(text: str):
	# given
	app = _ModalHostApp()

	async def run():
		async with app.run_test(size=(80, 40)) as pilot:
			app.push_screen(SearchFiltersModal(default_search_filters()), wait_for_dismiss=False)
			await pilot.pause()

			# when
			app.screen.query_one("#sf-ignore", TextArea).text = text
			await pilot.pause()

			# then
			assert _label_text(app, "#sf-ignore-error") != ""
			assert _apply_disabled(app) is True

	asyncio.run(run())


def test_given_initial_filters_with_ignore_when_modal_opened_then_widgets_prefilled():
	# given
	app = _ModalHostApp()
	initial = _filters_with(ignore_patterns="*.log\n/build/", respect_gitignore=True)

	async def run():
		async with app.run_test(size=(80, 40)) as pilot:
			# when
			app.push_screen(SearchFiltersModal(initial), wait_for_dismiss=False)
			await pilot.pause()

			# then
			assert app.screen.query_one("#sf-ignore", TextArea).text == "*.log\n/build/"
			assert app.screen.query_one("#sf-respect-gitignore", Checkbox).value is True

	asyncio.run(run())


def test_given_ignore_text_and_checkboxes_when_apply_pressed_then_result_carries_filters_and_persist():
	# given
	app = _ModalHostApp()
	results: list[Any] = []

	async def run():
		async with app.run_test(size=(80, 40)) as pilot:
			app.push_screen(
				SearchFiltersModal(default_search_filters()), wait_for_dismiss=False, callback=results.append
			)
			await pilot.pause()
			app.screen.query_one("#sf-ignore", TextArea).text = "node_modules/\n*.log\n/build/"
			app.screen.query_one("#sf-respect-gitignore", Checkbox).value = True
			app.screen.query_one("#sf-persist", Checkbox).value = True
			await pilot.pause()

			# when
			await pilot.click("#search-filters-apply")
			await pilot.pause()

			# then
			assert len(results) == 1
			result = results[0]
			assert result.filters.ignore_patterns == "node_modules/\n*.log\n/build/"
			assert result.filters.respect_gitignore is True
			assert result.persist is True

	asyncio.run(run())


def test_given_remember_unticked_when_apply_pressed_then_result_persist_false():
	# given
	app = _ModalHostApp()
	results: list[Any] = []

	async def run():
		async with app.run_test(size=(80, 40)) as pilot:
			app.push_screen(
				SearchFiltersModal(default_search_filters()), wait_for_dismiss=False, callback=results.append
			)
			await pilot.pause()
			app.screen.query_one("#sf-ignore", TextArea).text = "*.log"
			app.screen.query_one("#sf-persist", Checkbox).value = False
			await pilot.pause()

			# when
			await pilot.click("#search-filters-apply")
			await pilot.pause()

			# then
			assert results[0].persist is False
			assert results[0].filters.ignore_patterns == "*.log"
			assert results[0].filters.respect_gitignore is False

	asyncio.run(run())


def test_given_invalid_pattern_when_cancel_pressed_then_modal_dismissed_with_none():
	# given
	app = _ModalHostApp()
	results: list[Any] = []

	async def run():
		async with app.run_test(size=(80, 40)) as pilot:
			app.push_screen(
				SearchFiltersModal(default_search_filters()), wait_for_dismiss=False, callback=results.append
			)
			await pilot.pause()
			app.screen.query_one("#sf-ignore", TextArea).text = "[oops"
			await pilot.pause()

			# when
			await pilot.click("#search-filters-cancel")
			await pilot.pause()

			# then
			assert results == [None]

	asyncio.run(run())


def _open_filters_and_apply(app: SrxyApp, *, text: str, respect_gitignore: bool, persist: bool):
	async def run():
		async with app.run_test(size=(100, 40)) as pilot:
			await pilot.pause()
			await pilot.click("#search-filters-button")
			await pilot.pause()
			assert isinstance(app.screen, SearchFiltersModal)
			app.screen.query_one("#sf-ignore", TextArea).text = text
			app.screen.query_one("#sf-respect-gitignore", Checkbox).value = respect_gitignore
			app.screen.query_one("#sf-persist", Checkbox).value = persist
			await pilot.pause()
			await pilot.click("#search-filters-apply")
			await pilot.pause()

	asyncio.run(run())


def test_given_remember_filters_ticked_when_app_restarted_then_list_and_checkbox_restored(settings_file: Path):
	# given
	args = build_parser().parse_args(["hello", "."])
	first = SrxyApp(args, auto_start=False)

	# when
	_open_filters_and_apply(first, text="*.log\n/build/", respect_gitignore=True, persist=True)
	second = SrxyApp(build_parser().parse_args(["hello", "."]), auto_start=False)

	# then
	assert first.search_filters.ignore_patterns == "*.log\n/build/"
	assert second.search_filters.ignore_patterns == "*.log\n/build/"
	assert second.search_filters.respect_gitignore is True
	assert load_persisted_search_prefs().persist_filters is True


def test_given_remember_filters_unticked_when_app_restarted_then_list_empty_but_applied_in_session(settings_file: Path):
	# given
	args = build_parser().parse_args(["hello", "."])
	first = SrxyApp(args, auto_start=False)

	# when
	_open_filters_and_apply(first, text="*.log", respect_gitignore=True, persist=False)
	second = SrxyApp(build_parser().parse_args(["hello", "."]), auto_start=False)

	# then
	assert first.search_filters.ignore_patterns == "*.log"
	assert first.search_filters.respect_gitignore is True
	assert second.search_filters.ignore_patterns == ""
	assert second.search_filters.respect_gitignore is False


def test_given_persisted_filters_with_ignore_when_app_started_then_filters_modal_prefilled(settings_file: Path):
	# given
	save_persisted_filters(
		persist_filters=True,
		filters=_filters_with(ignore_patterns="*.tmp", respect_gitignore=True),
	)
	app = SrxyApp(build_parser().parse_args(["hello", "."]), auto_start=False)

	async def run():
		async with app.run_test(size=(100, 40)) as pilot:
			await pilot.pause()

			# when
			await pilot.click("#search-filters-button")
			await pilot.pause()

			# then
			assert app.screen.query_one("#sf-ignore", TextArea).text == "*.tmp"
			assert app.screen.query_one("#sf-respect-gitignore", Checkbox).value is True
			assert app.screen.query_one("#sf-persist", Checkbox).value is True

	asyncio.run(run())


def test_given_three_patterns_and_respect_gitignore_when_summary_renders_then_reads_ignoring_3_patterns():
	# given
	app = SrxyApp(build_parser().parse_args(["hello", "."]), auto_start=False)
	filters = _filters_with(ignore_patterns="node_modules/\n*.log\n/build/", respect_gitignore=True)

	async def run():
		async with app.run_test(size=(120, 40)) as pilot:
			await pilot.pause()

			# when
			app.search_filters = filters
			app._refresh_filters_summary()
			await pilot.pause()

			# then
			summary = str(app.query_one("#filters-summary", Static).render())
			assert "ignoring 3 patterns (+.gitignore)" in summary

	asyncio.run(run())


def test_given_no_patterns_when_summary_renders_then_no_ignoring_text():
	# given
	app = SrxyApp(build_parser().parse_args(["hello", "."]), auto_start=False)

	async def run():
		async with app.run_test(size=(120, 40)) as pilot:
			# when
			await pilot.pause()

			# then
			summary = str(app.query_one("#filters-summary", Static).render())
			assert "ignoring" not in summary

	asyncio.run(run())


@pytest.mark.parametrize("theme", ["textual-light", "textual-dark"])
def test_given_ignore_patterns_and_checkbox_when_modal_opened_then_matches_snapshot(theme: str):
	# given
	app = _ModalHostApp()
	app.theme = theme
	initial = _filters_with(ignore_patterns="node_modules/\n*.log\n/build/", respect_gitignore=True)

	async def run():
		async with app.run_test(size=(80, 50)) as pilot:
			app.push_screen(SearchFiltersModal(initial), wait_for_dismiss=False)
			await pilot.pause()
			app.screen.query_one("#sf-persist", Checkbox).value = True
			await pilot.pause()
			assert isinstance(app.screen, SearchFiltersModal)
			svg = app.export_screenshot(title="search-filters-modal-ignore")
			assert_svg_snapshot(f"search_filters_modal_ignore_{theme}", svg)

	asyncio.run(run())


@pytest.mark.parametrize("theme", ["textual-light", "textual-dark"])
def test_given_invalid_pattern_when_modal_opened_then_matches_snapshot(theme: str):
	# given
	app = _ModalHostApp()
	app.theme = theme

	async def run():
		async with app.run_test(size=(80, 50)) as pilot:
			app.push_screen(SearchFiltersModal(default_search_filters()), wait_for_dismiss=False)
			await pilot.pause()
			app.screen.query_one("#sf-ignore", TextArea).text = "[oops"
			await pilot.pause()
			svg = app.export_screenshot(title="search-filters-modal-ignore-error")
			assert "oops" in normalized_svg_text(svg)
			assert_svg_snapshot(f"search_filters_modal_ignore_error_{theme}", svg)

	asyncio.run(run())


@pytest.mark.parametrize("theme", ["textual-light", "textual-dark"])
def test_given_ignore_filters_when_summary_bar_rendered_then_matches_snapshot(theme: str):
	# given
	app = SrxyApp(build_parser().parse_args(["hello", "."]), auto_start=False)
	app.theme = theme
	filters = _filters_with(ignore_patterns="node_modules/\n*.log\n/build/", respect_gitignore=True)

	async def run():
		async with app.run_test(size=(120, 40)) as pilot:
			await pilot.pause()
			app.search_filters = filters
			app._refresh_filters_summary()
			await pilot.pause()
			svg = app.export_screenshot(title="srxy-tui-filters-summary-ignore")
			assert "ignoring 3 patterns" in normalized_svg_text(svg)
			assert_svg_snapshot(f"srxy_app_filters_summary_ignore_{theme}", svg)

	asyncio.run(run())
