from __future__ import annotations

import json
from importlib import resources

import pytest


pytestmark = pytest.mark.unit

# Keys intentionally identical across EN/ES (proper nouns, URLs, technical tokens).
_IDENTICAL_ALLOWLIST = frozenset(
	{
		"app.name",
		"about.pypi",
		"about.github",
		"common.no",
		"gui.col.hash",
		"gui.error",
		"gui.mode.simple",
		"menu.language.en",
		"menu.language.es",
		"filters.summary.top",
		"installer.options.tesseract_sub",
		"installer.options.ffmpeg_sub",
		"privacy.party.uv",
		"privacy.party.pypi",
		"privacy.party.qt",
		"privacy.party.tesseract",
		"privacy.party.tessdata",
		"privacy.party.ffmpeg",
		"privacy.party.ffmpeg_build",
		"privacy.party.pytorch",
		"privacy.party.nvidia",
		"privacy.party.nvidia_eula",
		"privacy.party.hf",
		"privacy.party.model_text",
		"privacy.party.model_clip",
		"privacy.party.model_fw",
		"privacy.party.model_whisper",
		"summary.how.semantic_image",
		"tui.match.visual",
	}
)


def _load_catalog(language: str) -> dict[str, str]:
	raw = resources.files("srxy.i18n").joinpath(f"{language}.json").read_text(encoding="utf-8")
	data = json.loads(raw)
	assert isinstance(data, dict)
	return {str(key): str(value) for key, value in data.items()}


def test_given_en_and_es_catalogs_when_comparing_keys_then_sets_match():
	en = _load_catalog("en")
	es = _load_catalog("es")
	assert set(en) == set(es)


def test_given_en_and_es_catalogs_when_values_identical_then_allowlisted_or_translated():
	en = _load_catalog("en")
	es = _load_catalog("es")
	for key in en:
		if en[key] == es[key] and key not in _IDENTICAL_ALLOWLIST:
			pytest.fail(f"identical EN/ES value for {key!r} — translate es or add to allowlist")
