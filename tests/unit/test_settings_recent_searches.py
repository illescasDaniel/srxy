"""Unit tests for the recent-searches / last-session settings.json helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from srxy.application.settings import (
	RECENT_SEARCHES_CAP,
	RecentSearchEntry,
	clear_recent_searches,
	load_recent_searches,
	load_settings,
	reset_settings,
	save_recent_search,
	save_settings,
	set_language_setting,
)


pytestmark = [pytest.mark.unit]


def _entry(path: str, *, mode: str = "simple", simple: str = "invoice", **kwargs: object) -> RecentSearchEntry:
	return RecentSearchEntry(path=path, query_mode=mode, simple_query=simple, display=simple, **kwargs)


def test_given_no_settings_file_when_load_recent_then_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))

	# when / then
	assert load_recent_searches() == []


def test_given_saved_entry_when_load_then_round_trips_path_query_mode_only(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	docs_dir = str(tmp_path / "Documents")
	entry = RecentSearchEntry(
		path=docs_dir,
		query_mode="advanced",
		advanced_query="revenue | amphibian",
		display="revenue | amphibian",
	)

	# when
	ok = save_recent_search(entry)
	loaded = load_recent_searches()

	# then
	assert ok is True
	assert len(loaded) == 1
	assert loaded[0].path == docs_dir
	assert loaded[0].query_mode == "advanced"
	assert loaded[0].advanced_query == "revenue | amphibian"
	assert loaded[0].timestamp  # stamped automatically
	# No filter/options snapshot in v1.
	assert "filters" not in load_settings()
	assert "options" not in load_settings()


def test_given_language_setting_when_save_recent_then_does_not_clobber_language(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.delenv("SRXY_LANGUAGE", raising=False)
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	set_language_setting("es")

	# when
	save_recent_search(_entry(str(tmp_path / "a")))

	# then
	assert load_settings()["language"] == "es"


def test_given_more_than_cap_entries_when_save_then_oldest_dropped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))

	# when
	for i in range(RECENT_SEARCHES_CAP + 5):
		save_recent_search(_entry(str(tmp_path / f"path-{i}"), simple=f"query-{i}"))
	loaded = load_recent_searches()

	# then
	assert len(loaded) == RECENT_SEARCHES_CAP
	# Newest first; the earliest entries (path-0..path-4) were dropped.
	assert loaded[0].path == str(tmp_path / f"path-{RECENT_SEARCHES_CAP + 4}")
	paths = {e.path for e in loaded}
	assert str(tmp_path / "path-0") not in paths
	assert str(tmp_path / "path-4") not in paths


def test_given_repeat_of_same_search_when_save_then_moved_to_front_not_duplicated(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	path_a = str(tmp_path / "a")
	path_b = str(tmp_path / "b")
	save_recent_search(_entry(path_a, simple="alpha"))
	save_recent_search(_entry(path_b, simple="beta"))

	# when
	save_recent_search(_entry(path_a, simple="alpha"))
	loaded = load_recent_searches()

	# then
	assert [e.path for e in loaded] == [path_a, path_b]


def test_given_recent_searches_when_clear_then_list_removed_but_settings_kept(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.delenv("SRXY_LANGUAGE", raising=False)
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	set_language_setting("es")
	save_recent_search(_entry(str(tmp_path / "a")))

	# when
	ok = clear_recent_searches()

	# then
	assert ok is True
	assert load_recent_searches() == []
	assert load_settings()["language"] == "es"


def test_given_no_recent_searches_when_clear_then_noop_true(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))

	# when / then
	assert clear_recent_searches() is True


def test_given_malformed_recent_entries_when_load_then_ignores_invalid_rows(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	save_settings(
		{
			"recent_searches": [
				{"path": "/valid", "query_mode": "simple", "simple_query": "ok"},
				{"path": "", "query_mode": "simple"},
				{"path": "/bad-mode", "query_mode": "unknown"},
				"not-a-dict",
				{"query_mode": "simple"},
			]
		}
	)

	# when
	loaded = load_recent_searches()

	# then
	assert len(loaded) == 1
	assert loaded[0].path == "/valid"


def test_given_recent_searches_when_reset_settings_then_history_gone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	save_recent_search(_entry(str(tmp_path / "a")))
	assert load_recent_searches()

	# when
	reset_settings()

	# then
	assert load_recent_searches() == []
