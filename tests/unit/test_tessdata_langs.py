from __future__ import annotations

from srxy.adapters.inbound.installer.tessdata_langs import (
	default_tessdata_langs,
	locale_to_tessdata,
	normalize_tessdata_langs,
	selectable_tessdata_languages,
	tessdata_artifact,
)


def test_given_locale_tags_when_defaulting_langs_then_includes_eng_osd_and_mapped():
	assert default_tessdata_langs("es", "en-US", "fr") == ("eng", "osd", "spa", "fra")


def test_given_unknown_locale_when_mapping_then_returns_none():
	assert locale_to_tessdata("zz") is None


def test_given_extra_lang_when_normalizing_then_keeps_required_first():
	assert normalize_tessdata_langs(["spa", "eng"]) == ("eng", "osd", "spa")


def test_given_registry_when_listing_selectable_then_includes_spa_and_excludes_scripts():
	codes = {lang.code for lang in selectable_tessdata_languages()}
	assert "eng" in codes
	assert "osd" in codes
	assert "spa" in codes
	assert not any("/" in code for code in codes)


def test_given_spa_when_building_artifact_then_pins_sha256():
	item = tessdata_artifact("spa")
	assert item.url.endswith("/spa.traineddata")
	assert len(item.sha256) == 64
