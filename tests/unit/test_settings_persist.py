from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

import pytest

from srxy.application.search_filters import SearchFilters, default_search_filters
from srxy.application.search_options import SearchOptions
from srxy.application.settings import (
	SCAN_SWITCH_KEYS,
	ScanSwitches,
	apply_scan_switches,
	load_persisted_search_prefs,
	load_settings,
	save_persisted_filters,
	save_persisted_search_prefs,
	save_settings,
	scan_switches_from_options,
	set_language_setting,
	settings_path,
)
from srxy.application.size_limits import SizeLimits


pytestmark = [pytest.mark.unit]


def test_given_persist_options_when_save_and_load_then_round_trips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	options = SearchOptions(search_docs_tags=False, ocr=True, search_names=True, search_contents=True)

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


def _ignore_filters() -> SearchFilters:
	return replace(default_search_filters(), ignore_patterns="*.log\n!keep.log\n/src/old/", respect_gitignore=True)


def _legacy_filters_blob(**extra: object) -> dict[str, object]:
	return {
		"top_files": "100",
		"max_matches": "50",
		"threshold": "40",
		"semantic_image_threshold": "18",
		"transcribe_threshold": "25",
		"size_limits": {"text_mib": "100", "ocr_mib": "50", "transcribe_mib": "500"},
		**extra,
	}


def test_given_remember_filters_with_ignore_when_save_and_load_then_list_and_checkbox_round_trip(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	filters = _ignore_filters()

	# when
	save_persisted_search_prefs(persist_options=False, persist_filters=True, filters=filters)
	prefs = load_persisted_search_prefs()

	# then
	assert prefs.persist_filters is True
	assert prefs.filters == filters
	assert prefs.filters is not None
	assert prefs.filters.ignore_patterns == "*.log\n!keep.log\n/src/old/"
	assert prefs.filters.respect_gitignore is True


def test_given_remember_filters_unticked_when_save_and_load_then_ignore_list_not_restored(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	filters = _ignore_filters()

	# when
	save_persisted_search_prefs(persist_options=False, persist_filters=False, filters=filters)
	prefs = load_persisted_search_prefs()

	# then
	assert prefs.persist_filters is False
	assert prefs.filters is None
	assert "filters" not in load_settings()


def test_given_old_settings_file_without_ignore_keys_when_load_then_empty_list_and_other_filters_intact(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	save_settings({"persist_filters": True, "filters": _legacy_filters_blob()})

	# when
	prefs = load_persisted_search_prefs()

	# then
	assert prefs.persist_filters is True
	assert prefs.filters is not None
	assert prefs.filters.ignore_patterns == ""
	assert prefs.filters.respect_gitignore is False
	assert prefs.filters.top_files == "100"
	assert prefs.filters.threshold == "40"


def test_given_non_bool_respect_gitignore_when_load_then_falls_back_to_factory_filters(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	save_settings({"persist_filters": True, "filters": _legacy_filters_blob(respect_gitignore="yes")})

	# when
	prefs = load_persisted_search_prefs()

	# then
	assert prefs.persist_filters is False
	assert prefs.filters is None


def test_given_invalid_persisted_ignore_pattern_when_load_then_falls_back_to_factory_filters(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	save_settings(
		{
			"persist_filters": True,
			"filters": _legacy_filters_blob(ignore_patterns="ok\n[oops", respect_gitignore=False),
		}
	)

	# when
	prefs = load_persisted_search_prefs()

	# then
	assert prefs.persist_filters is False
	assert prefs.filters is None


def test_given_persisted_list_over_size_cap_when_load_then_falls_back_to_factory_filters(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	save_settings({"persist_filters": True, "filters": _legacy_filters_blob(ignore_patterns="\n".join(["x"] * 1001))})

	# when
	prefs = load_persisted_search_prefs()

	# then
	assert prefs.persist_filters is False
	assert prefs.filters is None


def test_given_persisted_options_when_save_persisted_filters_then_options_untouched(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	options = SearchOptions(search_docs_tags=False, ocr=True, search_names=True, search_contents=True)
	save_persisted_search_prefs(persist_options=True, persist_filters=False, options=options)
	filters = _ignore_filters()

	# when
	save_persisted_filters(persist_filters=True, filters=filters)
	prefs = load_persisted_search_prefs()

	# then
	assert prefs.persist_options is True
	assert prefs.options == options
	assert prefs.persist_filters is True
	assert prefs.filters == filters


def test_given_persisted_filters_when_save_persisted_filters_unticked_then_drops_filters_keeps_options(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	options = SearchOptions(ocr=True)
	save_persisted_search_prefs(persist_options=True, persist_filters=True, options=options, filters=_ignore_filters())

	# when
	save_persisted_filters(persist_filters=False, filters=_ignore_filters())

	# then
	data = load_settings()
	assert data["persist_filters"] is False
	assert "filters" not in data
	assert data["persist_options"] is True
	assert data["options"] == {k: v for k, v in asdict(options).items() if k not in SCAN_SWITCH_KEYS}


def test_given_language_when_save_persisted_filters_then_language_kept(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.delenv("SRXY_LANGUAGE", raising=False)
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	set_language_setting("es")

	# when
	save_persisted_filters(persist_filters=True, filters=_ignore_filters())

	# then
	assert load_settings()["language"] == "es"


def test_given_no_prior_settings_when_save_persisted_filters_then_options_keys_not_created(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))

	# when
	save_persisted_filters(persist_filters=True, filters=_ignore_filters())

	# then
	data = load_settings()
	assert "options" not in data
	assert "persist_options" not in data


_NON_DEFAULT_SCAN = ScanSwitches(
	include_subdirectories=False,
	include_archives=True,
	include_hidden=True,
	include_noise=True,
	include_noise_files=True,
	match_skipped_names=True,
)


def _scan_options() -> SearchOptions:
	return apply_scan_switches(SearchOptions(ocr=True), _NON_DEFAULT_SCAN)


def test_given_scan_keys_when_listed_then_match_scan_switches_fields():
	# given / when
	from dataclasses import fields

	# then
	assert SCAN_SWITCH_KEYS == tuple(f.name for f in fields(ScanSwitches))
	assert ScanSwitches() == scan_switches_from_options(SearchOptions())


def test_given_scan_switches_when_apply_and_extract_then_round_trip():
	# given
	options = SearchOptions(ocr=True)

	# when
	applied = apply_scan_switches(options, _NON_DEFAULT_SCAN)

	# then
	assert applied.ocr is True
	assert scan_switches_from_options(applied) == _NON_DEFAULT_SCAN


def test_given_remember_filters_when_save_and_load_then_scan_round_trips(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))

	# when
	save_persisted_search_prefs(
		persist_options=True, persist_filters=True, options=_scan_options(), filters=default_search_filters()
	)
	prefs = load_persisted_search_prefs()

	# then
	assert load_settings()["scan"] == asdict(_NON_DEFAULT_SCAN)
	assert prefs.scan == _NON_DEFAULT_SCAN
	assert prefs.options is not None
	assert prefs.options.ocr is True
	assert scan_switches_from_options(prefs.options) == _NON_DEFAULT_SCAN


def test_given_persist_filters_off_when_save_then_scan_not_written_even_with_persist_options(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))

	# when
	save_persisted_search_prefs(persist_options=True, persist_filters=False, options=_scan_options())
	prefs = load_persisted_search_prefs()

	# then
	assert "scan" not in load_settings()
	assert prefs.scan is None
	assert prefs.options is not None
	assert prefs.options.ocr is True
	assert scan_switches_from_options(prefs.options) == ScanSwitches()


def test_given_save_when_options_blob_written_then_contains_no_scan_keys(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))

	# when
	save_persisted_search_prefs(
		persist_options=True, persist_filters=True, options=_scan_options(), filters=default_search_filters()
	)

	# then
	blob = load_settings()["options"]
	assert blob["ocr"] is True
	assert not set(SCAN_SWITCH_KEYS) & set(blob)


def test_given_legacy_options_blob_without_scan_when_load_then_scan_migrated(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	save_settings({"persist_options": True, "options": asdict(_scan_options())})

	# when
	prefs = load_persisted_search_prefs()

	# then
	assert prefs.scan == _NON_DEFAULT_SCAN
	assert prefs.persist_filters is False

	# when the next save happens with Remember filters on
	assert prefs.options is not None
	save_persisted_search_prefs(
		persist_options=True,
		persist_filters=True,
		options=apply_scan_switches(prefs.options, prefs.scan or ScanSwitches()),
		filters=default_search_filters(),
	)

	# then
	data = load_settings()
	assert data["scan"] == asdict(_NON_DEFAULT_SCAN)
	assert not set(SCAN_SWITCH_KEYS) & set(data["options"])


def test_given_scan_and_legacy_keys_when_load_then_scan_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	filters = default_search_filters()
	save_settings(
		{
			"persist_options": True,
			"persist_filters": True,
			"options": asdict(_scan_options()),
			"filters": asdict(filters),
			"scan": asdict(ScanSwitches()),
		}
	)

	# when
	prefs = load_persisted_search_prefs()

	# then
	assert prefs.scan == ScanSwitches()


@pytest.mark.parametrize("bad", ["x", [1], {"include_hidden": "yes"}, {"include_hidden": 1}])
def test_given_invalid_scan_when_load_then_ignored_and_other_prefs_kept(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad: object
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	save_settings(
		{
			"persist_options": True,
			"persist_filters": True,
			"options": {"ocr": True},
			"filters": asdict(default_search_filters()),
			"scan": bad,
		}
	)

	# when
	prefs = load_persisted_search_prefs()

	# then
	assert prefs.scan is None
	assert prefs.persist_filters is True
	assert prefs.filters == default_search_filters()
	assert prefs.options is not None
	assert prefs.options.ocr is True


def test_given_options_when_save_persisted_filters_then_scan_written_and_options_untouched(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	stored = SearchOptions(ocr=True)
	save_persisted_search_prefs(persist_options=True, persist_filters=False, options=stored)

	# when
	save_persisted_filters(persist_filters=True, filters=_ignore_filters(), options=_scan_options())

	# then
	data = load_settings()
	assert data["scan"] == asdict(_NON_DEFAULT_SCAN)
	assert data["persist_options"] is True
	assert data["options"] == {k: v for k, v in asdict(stored).items() if k not in SCAN_SWITCH_KEYS}


def test_given_scan_when_save_persisted_filters_unticked_then_scan_dropped(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	save_persisted_filters(persist_filters=True, filters=_ignore_filters(), options=_scan_options())

	# when
	save_persisted_filters(persist_filters=False, filters=_ignore_filters(), options=_scan_options())

	# then
	assert "scan" not in load_settings()


def test_given_nothing_persisted_when_load_then_scan_none_and_options_none(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))

	# when
	prefs = load_persisted_search_prefs()

	# then
	assert prefs.scan is None
	assert prefs.options is None


def test_given_persisted_ignore_pattern_with_escaped_slash_when_load_then_falls_back_to_factory_filters(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	save_settings(
		{
			"persist_filters": True,
			"filters": _legacy_filters_blob(ignore_patterns="foo\\/", respect_gitignore=False),
		}
	)

	# when
	prefs = load_persisted_search_prefs()

	# then
	assert prefs.persist_filters is False
	assert prefs.filters is None
