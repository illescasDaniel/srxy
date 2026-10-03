"""Click-driven QML flows for the launch banner and recent-searches popover."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.gui.helpers import ensure_qapp, load_main

from srxy.adapters.inbound.cli.cli import build_parser
from srxy.adapters.inbound.gui.controller import SearchController
from srxy.application.settings import RecentSearchEntry, save_recent_search


pytestmark = [pytest.mark.integration, pytest.mark.gui]


@pytest.fixture(scope="module")
def qapp():
	return ensure_qapp()


def _open_popover(harness):
	harness.click("recentSearchesButton")
	harness.wait_until(
		lambda: (
			bool(harness.prop("recentSearchesPopup", "visible")) or bool(harness.prop("recentSearchesPopup", "opened"))
		),
		timeout_ms=5_000,
		message="recentSearchesPopup did not open",
	)


def test_given_recent_search_when_gui_launches_then_banner_restore_fills_form_without_searching(
	qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	monkeypatch.setenv("SRXY_SKIP_UPDATE_CHECK", "1")
	restored_dir = tmp_path / "restored"
	restored_dir.mkdir()
	save_recent_search(
		RecentSearchEntry(path=str(restored_dir), query_mode="simple", simple_query="invoice", display="invoice")
	)
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	harness = load_main(controller, qapp)
	for _ in range(20):
		qapp.processEvents()

	# then — banner shown at launch
	assert bool(harness.prop("launchBanner", "visible")) is True

	# when
	harness.click("launchBannerRestoreButton")

	# then — form filled, search never auto-started
	assert str(harness.prop("pathField", "text")) == str(restored_dir)
	assert str(harness.prop("simpleQueryField", "text")) == "invoice"
	assert bool(controller.searching) is False
	assert bool(controller.hasSearched) is False
	assert bool(harness.prop("launchBanner", "visible")) is False

	harness.shutdown()


def test_given_recent_search_when_dismiss_clicked_then_banner_hidden_and_fields_untouched(
	qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	monkeypatch.setenv("SRXY_SKIP_UPDATE_CHECK", "1")
	save_recent_search(
		RecentSearchEntry(path=str(tmp_path / "other"), query_mode="simple", simple_query="invoice", display="invoice")
	)
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	harness = load_main(controller, qapp)
	for _ in range(20):
		qapp.processEvents()
	original_path = str(harness.prop("pathField", "text"))
	original_query = str(harness.prop("simpleQueryField", "text"))

	# when
	harness.click("launchBannerDismissButton")

	# then
	assert bool(harness.prop("launchBanner", "visible")) is False
	assert str(harness.prop("pathField", "text")) == original_path
	assert str(harness.prop("simpleQueryField", "text")) == original_query

	harness.shutdown()


def test_given_no_recent_search_when_gui_launches_then_no_banner(qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	monkeypatch.setenv("SRXY_SKIP_UPDATE_CHECK", "1")
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	harness = load_main(controller, qapp)
	for _ in range(20):
		qapp.processEvents()

	# then
	assert bool(harness.prop("launchBanner", "visible")) is False

	harness.shutdown()


def test_given_recent_searches_when_popover_opened_then_shows_entries_and_restore_fills_form(
	qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	monkeypatch.setenv("SRXY_SKIP_UPDATE_CHECK", "1")
	older = tmp_path / "older"
	older.mkdir()
	save_recent_search(RecentSearchEntry(path=str(older), query_mode="simple", simple_query="alpha", display="alpha"))
	newer = tmp_path / "newer"
	newer.mkdir()
	save_recent_search(RecentSearchEntry(path=str(newer), query_mode="simple", simple_query="beta", display="beta"))
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	harness = load_main(controller, qapp)
	for _ in range(20):
		qapp.processEvents()
	# Launch banner would otherwise sit on top of the popover's anchor point.
	harness.click("launchBannerDismissButton")

	# when
	_open_popover(harness)

	# then — newest first: restoring index 1 ("older"/alpha) fills that entry
	harness.click("recentRestoreButton_1")

	assert str(harness.prop("pathField", "text")) == str(older)
	assert str(harness.prop("simpleQueryField", "text")) == "alpha"
	assert bool(controller.searching) is False

	harness.shutdown()


def test_given_recent_search_when_restore_and_search_clicked_then_runs_exactly_one_search(
	qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	monkeypatch.setenv("SRXY_SKIP_UPDATE_CHECK", "1")
	needle_dir = tmp_path / "needle_dir"
	needle_dir.mkdir()
	(needle_dir / "note.txt").write_text("srxy-recent-flow-needle\n", encoding="utf-8")
	save_recent_search(
		RecentSearchEntry(
			path=str(needle_dir),
			query_mode="simple",
			simple_query="srxy-recent-flow-needle",
			display="srxy-recent-flow-needle",
		)
	)
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	harness = load_main(controller, qapp)
	for _ in range(20):
		qapp.processEvents()
	harness.click("launchBannerDismissButton")

	# when
	_open_popover(harness)
	harness.click("recentRestoreSearchButton_0")

	# then — popover closes, search runs once and finishes with the expected hit
	harness.wait_until(
		lambda: bool(controller.hasSearched) or bool(controller.searching),
		timeout_ms=10_000,
		message="restore & search never started",
	)
	harness.wait_search_finished()
	assert controller.resultsModel.rowCount() == 1
	assert bool(harness.prop("recentSearchesPopup", "opened")) is False

	harness.shutdown()


def test_given_recent_searches_when_clear_all_clicked_then_list_emptied(
	qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	monkeypatch.setenv("SRXY_SKIP_UPDATE_CHECK", "1")
	save_recent_search(RecentSearchEntry(path=str(tmp_path), query_mode="simple", simple_query="x", display="x"))
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	harness = load_main(controller, qapp)
	for _ in range(20):
		qapp.processEvents()
	harness.click("launchBannerDismissButton")
	_open_popover(harness)
	assert bool(harness.prop("recentSearchesEmptyLabel", "visible")) is False

	# when
	harness.click("recentClearAllButton")

	# then
	assert bool(controller.hasRecentSearches) is False
	assert bool(controller.launchBannerVisible) is False

	# and reopening the popover shows the empty placeholder
	_open_popover(harness)
	assert bool(harness.prop("recentSearchesEmptyLabel", "visible")) is True

	harness.shutdown()
