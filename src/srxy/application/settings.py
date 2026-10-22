"""Persisted user settings (language, search options/filters, etc.)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from srxy.application.install_paths import srxy_home


if TYPE_CHECKING:
	from srxy.application.search_filters import SearchFilters
	from srxy.application.search_options import SearchOptions


SUPPORTED_LANGUAGES = ("en", "es")
DEFAULT_LANGUAGE = "en"
QUERY_MODES = ("simple", "multi", "advanced")
RECENT_SEARCHES_CAP = 20


SCAN_SWITCH_KEYS = (
	"include_subdirectories",
	"include_archives",
	"include_hidden",
	"include_noise",
	"include_noise_files",
	"match_skipped_names",
)


@dataclass(frozen=True, slots=True)
class ScanSwitches:
	"""The "Which files to scan" switches (defaults equal ``SearchOptions`` defaults)."""

	include_subdirectories: bool = True
	include_archives: bool = False
	include_hidden: bool = False
	include_noise: bool = False
	include_noise_files: bool = False
	match_skipped_names: bool = False


def scan_switches_from_options(options: SearchOptions) -> ScanSwitches:
	return ScanSwitches(**{name: bool(getattr(options, name)) for name in SCAN_SWITCH_KEYS})


def apply_scan_switches(options: SearchOptions, scan: ScanSwitches) -> SearchOptions:
	return replace(options, **{name: getattr(scan, name) for name in SCAN_SWITCH_KEYS})


@dataclass(frozen=True, slots=True)
class PersistedSearchPrefs:
	"""Loaded search prefs.

	``options`` already has the six scan switches overlaid from ``scan`` (or at their
	defaults when ``scan`` is None); callers may still ``apply_scan_switches(options,
	prefs.scan)`` when ``prefs.scan`` is not None, e.g. onto other options when
	``options`` is None because "Persist options" is off.
	"""

	persist_options: bool = False
	persist_filters: bool = False
	options: SearchOptions | None = None
	filters: SearchFilters | None = None
	scan: ScanSwitches | None = None


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
	filter_names = frozenset(f.name for f in fields(SearchFilters)) - {"size_limits", "respect_gitignore"}
	respect_gitignore = raw.get("respect_gitignore", False)
	if not isinstance(respect_gitignore, bool):
		return None
	try:
		size = SizeLimits(**{name: str(size_raw.get(name, "")) for name in size_names})
		draft = SearchFilters(
			size_limits=size,
			respect_gitignore=respect_gitignore,
			**{name: str(raw.get(name, "")) for name in filter_names},
		)
		validate_search_filters(draft)
	except (TypeError, ValueError, KeyError):
		return None
	return draft


def _scan_from_raw(raw: Any) -> ScanSwitches | None:
	"""Parse a ``scan`` dict; any non-dict or non-bool value invalidates it."""
	if not isinstance(raw, dict):
		return None
	kwargs: dict[str, bool] = {}
	for name in SCAN_SWITCH_KEYS:
		if name not in raw:
			continue
		if not isinstance(raw[name], bool):
			return None
		kwargs[name] = raw[name]
	return ScanSwitches(**kwargs)


def _legacy_scan_from_options_blob(raw: Any) -> ScanSwitches | None:
	"""1.7 files kept the scan switches inside the persisted ``options`` blob."""
	if not isinstance(raw, dict) or not any(name in raw for name in SCAN_SWITCH_KEYS):
		return None
	return ScanSwitches(**{name: bool(raw[name]) for name in SCAN_SWITCH_KEYS if name in raw})


def _options_blob_without_scan(options: SearchOptions) -> dict[str, Any]:
	return {k: v for k, v in asdict(options).items() if k not in SCAN_SWITCH_KEYS}


def load_persisted_search_prefs() -> PersistedSearchPrefs:
	data = load_settings()
	persist_options = bool(data.get("persist_options"))
	persist_filters = bool(data.get("persist_filters"))
	raw_options = data.get("options")
	options = None
	if persist_options and isinstance(raw_options, dict):
		options = _options_from_raw({k: v for k, v in raw_options.items() if k not in SCAN_SWITCH_KEYS})
	filters = _filters_from_raw(data.get("filters")) if persist_filters else None
	if persist_options and options is None:
		persist_options = False
	if persist_filters and filters is None:
		persist_filters = False
	scan: ScanSwitches | None = None
	if "scan" in data:
		if persist_filters:
			scan = _scan_from_raw(data["scan"])
	elif persist_options:
		scan = _legacy_scan_from_options_blob(raw_options)
	if options is not None and scan is not None:
		options = apply_scan_switches(options, scan)
	return PersistedSearchPrefs(
		persist_options=persist_options,
		persist_filters=persist_filters,
		options=options,
		filters=filters,
		scan=scan,
	)


def save_persisted_search_prefs(
	*,
	persist_options: bool,
	persist_filters: bool,
	options: SearchOptions | None = None,
	filters: SearchFilters | None = None,
) -> bool:
	"""Merge search prefs into settings.json without clobbering language.

	The scan switches are stored under ``scan`` (only with ``persist_filters``) and never
	inside the ``options`` blob.
	"""
	data = load_settings()
	data["persist_options"] = bool(persist_options)
	data["persist_filters"] = bool(persist_filters)
	if persist_options and options is not None:
		data["options"] = _options_blob_without_scan(options)
	else:
		data.pop("options", None)
	if persist_filters and filters is not None:
		data["filters"] = asdict(filters)
	else:
		data.pop("filters", None)
	if persist_filters and options is not None:
		data["scan"] = asdict(scan_switches_from_options(options))
	else:
		data.pop("scan", None)
	return save_settings(data)


def save_persisted_filters(
	*, persist_filters: bool, filters: SearchFilters | None, options: SearchOptions | None = None
) -> bool:
	"""Update persist_filters / filters / scan, leaving persist_options and options untouched.

	``scan`` is written from ``options`` when given and ``persist_filters`` is on; it is
	dropped when ``persist_filters`` is off, and left as is when ``options`` is omitted.
	"""
	data = load_settings()
	data["persist_filters"] = bool(persist_filters)
	if persist_filters and filters is not None:
		data["filters"] = asdict(filters)
	else:
		data.pop("filters", None)
	if not persist_filters:
		data.pop("scan", None)
	elif options is not None:
		data["scan"] = asdict(scan_switches_from_options(options))
	return save_settings(data)


@dataclass(frozen=True, slots=True)
class RecentSearchEntry:
	"""One successful GUI search: path, query text, and query mode only.

	No filter/options snapshot in v1 (Trello scope lock 2026-09-07) — restoring
	a recent entry never touches Search options / Filters.
	"""

	path: str
	query_mode: str
	simple_query: str = ""
	advanced_query: str = ""
	term_rows_json: str = "[]"
	display: str = ""
	timestamp: str = ""


def _recent_entry_from_raw(raw: Any) -> RecentSearchEntry | None:
	if not isinstance(raw, dict):
		return None
	path = raw.get("path")
	mode = raw.get("query_mode")
	if not isinstance(path, str) or not path.strip():
		return None
	if mode not in QUERY_MODES:
		return None
	return RecentSearchEntry(
		path=path,
		query_mode=mode,
		simple_query=str(raw.get("simple_query", "")),
		advanced_query=str(raw.get("advanced_query", "")),
		term_rows_json=str(raw.get("term_rows_json", "[]")),
		display=str(raw.get("display", "")),
		timestamp=str(raw.get("timestamp", "")),
	)


def load_recent_searches() -> list[RecentSearchEntry]:
	"""Recent successful searches, newest first. ``[0]`` is the last session."""
	raw = load_settings().get("recent_searches")
	if not isinstance(raw, list):
		return []
	entries: list[RecentSearchEntry] = []
	for item in raw:
		entry = _recent_entry_from_raw(item)
		if entry is not None:
			entries.append(entry)
	return entries


def save_recent_search(entry: RecentSearchEntry, *, cap: int = RECENT_SEARCHES_CAP) -> bool:
	"""Prepend a successful search to the recent list (settings.json), oldest dropped past ``cap``.

	An exact duplicate (same path/mode/query text) already in the list is
	removed first so re-running the same search moves it to the front instead
	of padding the list with copies.
	"""
	data = load_settings()
	existing = load_recent_searches()
	stamped = replace(entry, timestamp=entry.timestamp or datetime.now(UTC).isoformat(timespec="seconds"))

	def _key(item: RecentSearchEntry) -> tuple[str, str, str, str, str]:
		return (item.path, item.query_mode, item.simple_query, item.advanced_query, item.term_rows_json)

	deduped = [item for item in existing if _key(item) != _key(stamped)]
	deduped.insert(0, stamped)
	data["recent_searches"] = [asdict(item) for item in deduped[:cap]]
	return save_settings(data)


def clear_recent_searches() -> bool:
	"""Drop the recent-searches list (and last-session banner) from settings.json."""
	data = load_settings()
	if "recent_searches" not in data:
		return True
	data.pop("recent_searches", None)
	return save_settings(data)


__all__ = [
	"DEFAULT_LANGUAGE",
	"QUERY_MODES",
	"RECENT_SEARCHES_CAP",
	"SUPPORTED_LANGUAGES",
	"SCAN_SWITCH_KEYS",
	"PersistedSearchPrefs",
	"RecentSearchEntry",
	"ScanSwitches",
	"apply_scan_switches",
	"clear_recent_searches",
	"get_language_setting",
	"load_persisted_search_prefs",
	"load_recent_searches",
	"load_settings",
	"reset_settings",
	"save_persisted_filters",
	"save_persisted_search_prefs",
	"save_recent_search",
	"save_settings",
	"scan_switches_from_options",
	"set_language_setting",
	"settings_file_present",
	"settings_path",
]
