from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pytest

from srxy.application.search_filters import SearchFilters, default_search_filters
from srxy.application.search_options import SearchOptions
from srxy.application.settings import (
	load_persisted_search_prefs,
	load_settings,
	save_persisted_search_prefs,
	save_settings,
	set_language_setting,
	settings_path,
)
from srxy.application.size_limits import SizeLimits


pytestmark = [pytest.mark.unit]


def test_given_persist_options_when_save_and_load_then_round_trips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	options = SearchOptions(include_hidden=True, ocr=True, search_names=True, search_contents=True)

	# when
	save_persisted_search_prefs(persist_options=True, persist_filters=False, options=options)
	prefs = load_persisted_search_prefs()

	# then
	assert prefs.persist_options is True
	assert prefs.persist_filters is False
	assert prefs.options == options
	assert prefs.filters is None
	assert "filters" not in load_settings()


def test_given_persist_filters_when_save_and_load_then_round_trips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	filters = default_search_filters()
	filters = SearchFilters(
		top_files="100",
		max_matches=filters.max_matches,
		size_limits=filters.size_limits,
		threshold="40",
		semantic_image_threshold=filters.semantic_image_threshold,
		transcribe_threshold=filters.transcribe_threshold,
	)

	# when
	save_persisted_search_prefs(persist_options=False, persist_filters=True, filters=filters)
	prefs = load_persisted_search_prefs()

	# then
	assert prefs.persist_filters is True
	assert prefs.filters == filters
	assert prefs.options is None
	assert "options" not in load_settings()


def test_given_corrupt_options_blob_when_load_then_ignores_and_clears_flag(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	save_settings({"persist_options": True, "options": "not-a-dict"})

	# when
	prefs = load_persisted_search_prefs()

	# then
	assert prefs.persist_options is False
	assert prefs.options is None


def test_given_corrupt_filters_when_load_then_ignores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	save_settings(
		{
			"persist_filters": True,
			"filters": {
				"top_files": "x",
				"max_matches": "50",
				"threshold": "35",
				"semantic_image_threshold": "18",
				"transcribe_threshold": "25",
				"size_limits": {"text_mib": "100", "ocr_mib": "50", "transcribe_mib": "500"},
			},
		}
	)

	# when
	prefs = load_persisted_search_prefs()

	# then
	assert prefs.persist_filters is False
	assert prefs.filters is None


def test_given_unpersist_when_save_then_drops_payload_keeps_language(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.delenv("SRXY_LANGUAGE", raising=False)
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	set_language_setting("es")
	save_persisted_search_prefs(
		persist_options=True,
		persist_filters=True,
		options=SearchOptions(include_archives=True),
		filters=default_search_filters(),
	)

	# when
	save_persisted_search_prefs(persist_options=False, persist_filters=False)

	# then
	data = load_settings()
	assert data["language"] == "es"
	assert data["persist_options"] is False
	assert data["persist_filters"] is False
	assert "options" not in data
	assert "filters" not in data


def test_given_srxy_home_when_settings_path_then_uses_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	home = tmp_path / "Applications" / "srxy"
	home.mkdir(parents=True)
	monkeypatch.delenv("SRXY_SETTINGS_PATH", raising=False)
	monkeypatch.setenv("SRXY_HOME", str(home))

	# when / then
	assert settings_path() == home / "settings.json"


def test_given_size_limits_asdict_when_rebuild_then_matches_default():
	# given / when
	filters = default_search_filters()
	raw = asdict(filters)
	size = SizeLimits(**raw.pop("size_limits"))
	rebuilt = SearchFilters(size_limits=size, **raw)

	# then
	assert rebuilt == filters
