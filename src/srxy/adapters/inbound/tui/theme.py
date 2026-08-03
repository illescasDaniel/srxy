from __future__ import annotations

import os
import shutil
import subprocess


def _colorfgbg_is_light() -> bool | None:
	raw = os.environ.get("COLORFGBG", "").strip()
	if not raw:
		return None
	parts = raw.split(";")
	if len(parts) < 2:
		return None
	try:
		background = int(parts[-1])
	except ValueError:
		return None
	return background >= 8


def _gnome_prefers_light() -> bool | None:
	gsettings = shutil.which("gsettings")
	if gsettings is None:
		return None
	try:
		result = subprocess.run(  # noqa: S603
			[gsettings, "get", "org.gnome.desktop.interface", "color-scheme"],
			check=False,
			capture_output=True,
			text=True,
		)
	except OSError:
		return None
	if result.returncode != 0:
		return None
	value = result.stdout.strip().strip("'")
	if value == "prefer-dark":
		return False
	if value in {"default", "prefer-light"}:
		return True
	return None


def detect_app_theme() -> str:
	if (light := _colorfgbg_is_light()) is not None:
		return "textual-light" if light else "textual-dark"
	if (light := _gnome_prefers_light()) is not None:
		return "textual-light" if light else "textual-dark"
	return "textual-dark"
