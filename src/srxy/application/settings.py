"""Persisted user settings (language, etc.)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from srxy.application.install_paths import srxy_home


SUPPORTED_LANGUAGES = ("en", "es")
DEFAULT_LANGUAGE = "en"


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


def save_settings(data: dict[str, Any]):
	path = settings_path()
	try:
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
	except OSError:
		# Best-effort persistence (e.g. read-only sandbox / missing home config).
		return


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


__all__ = [
	"DEFAULT_LANGUAGE",
	"SUPPORTED_LANGUAGES",
	"get_language_setting",
	"load_settings",
	"save_settings",
	"set_language_setting",
	"settings_path",
]
