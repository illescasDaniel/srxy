"""Persisted user settings (language, search options/filters, etc.)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import TYPE_CHECKING, Any

from srxy.application.install_paths import srxy_home


if TYPE_CHECKING:
	from srxy.application.search_filters import SearchFilters
	from srxy.application.search_options import SearchOptions


SUPPORTED_LANGUAGES = ("en", "es")
DEFAULT_LANGUAGE = "en"


@dataclass(frozen=True, slots=True)
class PersistedSearchPrefs:
	persist_options: bool = False
	persist_filters: bool = False
	options: SearchOptions | None = None
	filters: SearchFilters | None = None


def settings_path() -> Path:
	override = os.environ.get("SRXY_SETTINGS_PATH", "").strip()
	if override:
		return Path(override).expanduser()
	home = srxy_home()
	if home is not None:
		return home / "settings.json"
	xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
	base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
	return base / "srxy" / "settings.json"


def load_settings() -> dict[str, Any]:
	path = settings_path()
	if not path.is_file():
		return {}
	try:
		data = json.loads(path.read_text(encoding="utf-8"))
	except (OSError, json.JSONDecodeError, TypeError, ValueError):
		return {}
	return data if isinstance(data, dict) else {}


def save_settings(data: dict[str, Any]) -> bool:
	path = settings_path()
	try:
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
	except OSError:
		# Best-effort persistence (e.g. read-only sandbox / missing home config).
		return False
	return True


def get_language_setting() -> str | None:
	"""Explicit language from settings or env, else None (use system default)."""
	env = os.environ.get("SRXY_LANGUAGE", "").strip().lower()
	if env:
		return env.split("-", 1)[0][:2]
	raw = load_settings().get("language")
	if isinstance(raw, str) and raw.strip():
		return raw.strip().lower().split("-", 1)[0][:2]
	return None


def set_language_setting(language: str):
	code = language.strip().lower().split("-", 1)[0][:2]
	if code not in SUPPORTED_LANGUAGES:
		code = DEFAULT_LANGUAGE
	data = load_settings()
	data["language"] = code
	save_settings(data)
	os.environ["SRXY_LANGUAGE"] = code


def reset_settings() -> bool:
	"""Delete persisted settings.json and clear the language env override.

	Returns True if a settings file was removed. Does not write a new file;
	callers should re-resolve language from the system locale afterward.
	"""
	path = settings_path()
	removed = False
	if path.is_file():
		try:
			path.unlink()
			removed = True
		except OSError:
			pass
	os.environ.pop("SRXY_LANGUAGE", None)
	return removed


def settings_file_present() -> bool:
	return settings_path().is_file()


def _options_from_raw(raw: Any) -> SearchOptions | None:
	from srxy.application.search_options import SearchOptions

	if not isinstance(raw, dict):
		return None
	names = frozenset(f.name for f in fields(SearchOptions))
	kwargs: dict[str, Any] = {}
	for name in names:
		if name not in raw:
			continue
		kwargs[name] = bool(raw[name])
	try:
		return SearchOptions(**kwargs)
	except TypeError:
		return None


def _filters_from_raw(raw: Any) -> SearchFilters | None:
	from srxy.application.search_filters import SearchFilters, validate_search_filters
	from srxy.application.size_limits import SizeLimits

	if not isinstance(raw, dict):
		return None
	size_raw = raw.get("size_limits")
	if not isinstance(size_raw, dict):
		return None
	size_names = frozenset(f.name for f in fields(SizeLimits))
	filter_names = frozenset(f.name for f in fields(SearchFilters)) - {"size_limits"}
	try:
		size = SizeLimits(**{name: str(size_raw.get(name, "")) for name in size_names})
		draft = SearchFilters(
			size_limits=size,
			**{name: str(raw.get(name, "")) for name in filter_names},
		)
		validate_search_filters(draft)
	except (TypeError, ValueError, KeyError):
		return None
	return draft


def load_persisted_search_prefs() -> PersistedSearchPrefs:
	data = load_settings()
	persist_options = bool(data.get("persist_options"))
	persist_filters = bool(data.get("persist_filters"))
	options = _options_from_raw(data.get("options")) if persist_options else None
	filters = _filters_from_raw(data.get("filters")) if persist_filters else None
	if persist_options and options is None:
		persist_options = False
	if persist_filters and filters is None:
		persist_filters = False
	return PersistedSearchPrefs(
		persist_options=persist_options,
		persist_filters=persist_filters,
		options=options,
		filters=filters,
	)


def save_persisted_search_prefs(
	*,
	persist_options: bool,
	persist_filters: bool,
	options: SearchOptions | None = None,
	filters: SearchFilters | None = None,
) -> bool:
	"""Merge search prefs into settings.json without clobbering language."""
	data = load_settings()
	data["persist_options"] = bool(persist_options)
	data["persist_filters"] = bool(persist_filters)
	if persist_options and options is not None:
		data["options"] = asdict(options)
	else:
		data.pop("options", None)
	if persist_filters and filters is not None:
		data["filters"] = asdict(filters)
	else:
		data.pop("filters", None)
	return save_settings(data)


__all__ = [
	"DEFAULT_LANGUAGE",
	"SUPPORTED_LANGUAGES",
	"PersistedSearchPrefs",
	"get_language_setting",
	"load_persisted_search_prefs",
	"load_settings",
	"reset_settings",
	"save_persisted_search_prefs",
	"save_settings",
	"set_language_setting",
	"settings_file_present",
	"settings_path",
]
