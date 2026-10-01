"""Controller-level unit tests for recent-searches / restore-last-session."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QCoreApplication

from srxy.adapters.inbound.cli.cli import build_parser
from srxy.adapters.inbound.gui.controller import SearchController
from srxy.application.search_session import SearchFinishedEvent
from srxy.application.settings import RecentSearchEntry, load_recent_searches, save_recent_search


pytestmark = [pytest.mark.unit, pytest.mark.gui, pytest.mark.xdist_group("gui")]


@pytest.fixture(scope="module")
def qapp() -> QCoreApplication:
	os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
	from PySide6.QtGui import QGuiApplication

	app = QCoreApplication.instance()
	if app is None:
		app = QGuiApplication([])
	assert isinstance(app, QCoreApplication)
	return app


def test_given_successful_search_when_finished_then_recorded_in_recent_history(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	args = build_parser().parse_args(["invoice", str(tmp_path), "--cli"])
	controller = SearchController(args)

	# when
	controller.handle_search_event_for_tests(SearchFinishedEvent(results=[], skipped_files=[], cancelled=False))

	# then
	recent = load_recent_searches()
	assert len(recent) == 1
	assert recent[0].path == str(tmp_path)
	assert recent[0].query_mode == "simple"
	assert recent[0].simple_query == "invoice"
	assert json.loads(controller.recentSearchesJson)[0]["display"] == "invoice"
	assert controller.hasRecentSearches is True
	controller.shutdown(thread_wait_ms=100)


def test_given_cancelled_search_when_finished_then_not_recorded(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	args = build_parser().parse_args(["invoice", str(tmp_path), "--cli"])
	controller = SearchController(args)

	# when
	controller.handle_search_event_for_tests(SearchFinishedEvent(results=[], skipped_files=[], cancelled=True))

	# then
	assert load_recent_searches() == []
	assert controller.hasRecentSearches is False
	controller.shutdown(thread_wait_ms=100)


def test_given_no_filters_snapshot_when_recording_recent_then_only_path_query_mode_saved(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given (scope lock 2026-09-07: no filter/options snapshot in v1)
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	args = build_parser().parse_args(["invoice", str(tmp_path), "--cli"])
	controller = SearchController(args)

	# when
	controller.handle_search_event_for_tests(SearchFinishedEvent(results=[], skipped_files=[], cancelled=False))

	# then
	from srxy.application.settings import load_settings

	raw_entry = load_settings()["recent_searches"][0]
	assert set(raw_entry) == {
		"path",
		"query_mode",
		"simple_query",
		"advanced_query",
		"term_rows_json",
		"display",
		"timestamp",
	}
	controller.shutdown(thread_wait_ms=100)


def test_given_prior_recent_search_when_controller_starts_then_launch_banner_shows_summary(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	save_recent_search(
		RecentSearchEntry(
			path=str(tmp_path),
			query_mode="advanced",
			advanced_query="revenue | amphibian",
			display="revenue | amphibian",
		)
	)

	# when
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)

	# then
	assert controller.launchBannerVisible is True
	assert "revenue | amphibian" in controller.launchBannerMessage
	assert str(tmp_path) in controller.launchBannerMessage
	controller.shutdown(thread_wait_ms=100)


def test_given_no_recent_search_when_controller_starts_then_no_launch_banner(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))

	# when
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)

	# then
	assert controller.launchBannerVisible is False
	assert controller.launchBannerMessage == ""
	controller.shutdown(thread_wait_ms=100)


def test_given_launch_banner_when_restore_then_fills_form_without_starting_search(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	target = tmp_path / "restored"
	target.mkdir()
	save_recent_search(
		RecentSearchEntry(path=str(target), query_mode="simple", simple_query="invoice", display="invoice")
	)
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	assert controller.launchBannerVisible is True

	# when
	controller.restoreLaunchBanner(False)

	# then — form filled, never auto-started
	assert controller.path == str(target)
	assert controller.queryMode == "simple"
	assert controller.simpleQuery == "invoice"
	assert controller.searching is False
	assert controller.hasSearched is False
	assert controller.launchBannerVisible is False
	controller.shutdown(thread_wait_ms=100)


def test_given_launch_banner_when_dismiss_then_fields_left_default_and_banner_hidden(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	save_recent_search(
		RecentSearchEntry(path=str(tmp_path / "other"), query_mode="simple", simple_query="invoice", display="invoice")
	)
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	original_path = controller.path
	original_query = controller.simpleQuery

	# when
	controller.dismissLaunchBanner()

	# then
	assert controller.launchBannerVisible is False
	assert controller.path == original_path
	assert controller.simpleQuery == original_query
	controller.shutdown(thread_wait_ms=100)


def test_given_starting_any_search_when_launch_banner_open_then_it_closes(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	(tmp_path / "note.txt").write_text("alpha\n", encoding="utf-8")
	save_recent_search(RecentSearchEntry(path=str(tmp_path), query_mode="simple", simple_query="x", display="x"))
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	assert controller.launchBannerVisible is True

	# when
	controller.startSearch()

	# then
	assert controller.launchBannerVisible is False
	controller.shutdown(thread_wait_ms=2000)


def test_given_multiple_recent_entries_when_restore_recent_search_then_fills_that_entry(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	save_recent_search(
		RecentSearchEntry(path=str(tmp_path / "a"), query_mode="simple", simple_query="alpha", display="alpha")
	)
	save_recent_search(
		RecentSearchEntry(path=str(tmp_path / "b"), query_mode="simple", simple_query="beta", display="beta")
	)
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	entries = json.loads(controller.recentSearchesJson)
	assert entries[0]["display"] == "beta"
	assert entries[1]["display"] == "alpha"

	# when — restore the older ("alpha") entry, not the most recent
	controller.restoreRecentSearch(1, False)

	# then
	assert controller.simpleQuery == "alpha"
	assert controller.path == str(tmp_path / "a")
	assert controller.searching is False
	controller.shutdown(thread_wait_ms=100)


def test_given_popover_restore_and_search_when_invoked_then_runs_exactly_one_search(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	(tmp_path / "note.txt").write_text("alpha\n", encoding="utf-8")
	save_recent_search(
		RecentSearchEntry(path=str(tmp_path), query_mode="simple", simple_query="alpha", display="alpha")
	)
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	controller.startSearch = MagicMock()  # type: ignore[method-assign]

	# when
	controller.restoreRecentSearch(0, True)

	# then
	controller.startSearch.assert_called_once()
	assert controller.path == str(tmp_path)
	assert controller.simpleQuery == "alpha"
	controller.shutdown(thread_wait_ms=100)


def test_given_invalid_recent_index_when_restore_then_noop(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	original_path = controller.path

	# when
	controller.restoreRecentSearch(5, False)

	# then
	assert controller.path == original_path
	controller.shutdown(thread_wait_ms=100)


def test_given_recent_history_when_clear_all_then_list_and_banner_cleared(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	save_recent_search(RecentSearchEntry(path=str(tmp_path), query_mode="simple", simple_query="x", display="x"))
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	assert controller.hasRecentSearches is True

	# when
	controller.clearRecentSearches()

	# then
	assert controller.hasRecentSearches is False
	assert controller.launchBannerVisible is False
	assert json.loads(controller.recentSearchesJson) == []
	assert load_recent_searches() == []
	controller.shutdown(thread_wait_ms=100)


def test_given_recent_history_when_reset_preferences_then_history_cleared(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SKIP_UPDATE_CHECK", "1")
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	save_recent_search(RecentSearchEntry(path=str(tmp_path), query_mode="simple", simple_query="x", display="x"))
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	assert controller.hasRecentSearches is True

	# when
	controller.resetPreferences()

	# then — Reset preferences clears history too, not just persist options/filters defaults.
	assert controller.hasRecentSearches is False
	assert load_recent_searches() == []
	controller.shutdown(thread_wait_ms=100)
	from srxy.i18n import set_language

	set_language("en")


def test_given_cap_of_20_when_20_entries_when_21st_saved_then_oldest_dropped(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)

	# when
	for i in range(25):
		controller._path = str(tmp_path / f"case-{i}")  # noqa: SLF001 — direct state seed avoids per-iter filesystem/UI churn
		controller._simple_query = f"query-{i}"  # noqa: SLF001
		controller.handle_search_event_for_tests(SearchFinishedEvent(results=[], skipped_files=[], cancelled=False))

	# then
	recent = load_recent_searches()
	assert len(recent) == 20
	assert recent[0].simple_query == "query-24"
	assert all(entry.simple_query != "query-0" for entry in recent)
	controller.shutdown(thread_wait_ms=100)
