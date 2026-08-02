"""Lightweight string catalogs for English and Spanish."""

from __future__ import annotations

import json
import locale
import os
from functools import lru_cache
from importlib import resources
from typing import Any

from srxy.application.settings import (
	DEFAULT_LANGUAGE,
	SUPPORTED_LANGUAGES,
	get_language_setting,
)


_active_language: str | None = None


def system_language() -> str:
	raw = ""
	try:
		lang = locale.getlocale()[0]
		if lang:
			raw = lang
	except (TypeError, ValueError):
		raw = ""
	if not raw:
		raw = os.environ.get("LANG", "") or os.environ.get("LC_ALL", "") or ""
	code = raw.lower().replace("_", "-").split("-", 1)[0][:2]
	if code in SUPPORTED_LANGUAGES:
		return code
	return DEFAULT_LANGUAGE


def resolve_language(explicit: str | None = None) -> str:
	if explicit:
		code = explicit.strip().lower().split("-", 1)[0][:2]
		return code if code in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
	setting = get_language_setting()
	if setting:
		return setting if setting in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
	return system_language()


def get_language() -> str:
	global _active_language
	if _active_language is None:
		_active_language = resolve_language()
	return _active_language


def set_language(language: str):
	global _active_language
	code = resolve_language(language)
	_active_language = code
	_catalog.cache_clear()


@lru_cache(maxsize=8)
def _catalog(language: str) -> dict[str, str]:
	name = f"{language}.json"
	try:
		raw = resources.files("srxy.i18n").joinpath(name).read_text(encoding="utf-8")
		data = json.loads(raw)
	except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError, ValueError):
		data = {}
	if not isinstance(data, dict):
		return {}
	return {str(key): str(value) for key, value in data.items()}


def tr(key: str, **kwargs: Any) -> str:
	"""Translate ``key`` using the active catalog; fall back to English, then key."""
	lang = get_language()
	text = _catalog(lang).get(key)
	if text is None and lang != DEFAULT_LANGUAGE:
		text = _catalog(DEFAULT_LANGUAGE).get(key)
	if text is None:
		text = key
	if kwargs:
		try:
			return text.format(**kwargs)
		except (KeyError, ValueError, IndexError):
			return text
	return text


__all__ = [
	"get_language",
	"resolve_language",
	"set_language",
	"system_language",
	"tr",
]
