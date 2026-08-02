"""Apply the packaged srxy icon to a Qt GUI application."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtGui import QGuiApplication, QIcon

from srxy.resources.icons import app_icon_path, available_icon_sizes


def _xdg_data_dirs() -> list[Path]:
	dirs: list[Path] = []
	home = os.environ.get("XDG_DATA_HOME", "").strip()
	dirs.append(Path(home).expanduser() if home else Path.home() / ".local" / "share")
	raw = os.environ.get("XDG_DATA_DIRS", "").strip()
	parts = raw.split(":") if raw else ["/usr/local/share", "/usr/share"]
	for part in parts:
		text = part.strip()
		if text:
			dirs.append(Path(text))
	return dirs


def desktop_file_available(name: str) -> bool:
	"""True when ``{name}.desktop`` exists in an XDG applications dir."""
	filename = f"{name}.desktop"
	for root in _xdg_data_dirs():
		if (root / "applications" / filename).is_file():
			return True
	return False


def apply_desktop_file_name(app: QGuiApplication, name: str):
	"""Set the portal/Wayland app id only when a matching .desktop file exists.

	Avoids: Failed to register with host portal … App info not found for '…'
	when running via ``uv run`` / PyPI without a desktop entry installed.
	"""
	if desktop_file_available(name):
		app.setDesktopFileName(name)


def apply_app_icon(app: QGuiApplication):
	icon = QIcon()
	sizes = available_icon_sizes() or [256]
	for size in sizes:
		path = app_icon_path(size=size)
		icon.addFile(str(path))
	# Also add the master asset when present.
	try:
		icon.addFile(str(app_icon_path()))
	except FileNotFoundError:
		pass
	if icon.isNull():
		return
	app.setWindowIcon(icon)


__all__ = [
	"apply_app_icon",
	"apply_desktop_file_name",
	"desktop_file_available",
]
