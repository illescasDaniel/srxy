"""Apply the packaged srxy icon to a Qt GUI application."""

from __future__ import annotations

import ctypes
import os
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

from PySide6.QtGui import QGuiApplication, QIcon

from srxy.resources.icons import (
	app_icon_path,
	available_icon_sizes,
	available_installer_icon_sizes,
	available_macos_icon_sizes,
	icon_dir,
	installer_icon_path,
	macos_app_icon_path,
)


WINDOWS_APP_USER_MODEL_ID = "srxy.Srxy"


def ensure_windows_app_user_model_id(app_id: str = WINDOWS_APP_USER_MODEL_ID):
	"""Pin a stable AppUserModelID so the taskbar uses our window icon, not pythonw.exe."""
	if sys.platform != "win32":
		return
	try:
		ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
	except (AttributeError, OSError):
		return


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


def _load_icon(*, path_for_size: Callable[..., Path], sizes: list[int]) -> QIcon:
	icon = QIcon()
	for size in sizes or [256]:
		icon.addFile(str(path_for_size(size=size)))
	try:
		icon.addFile(str(path_for_size()))
	except FileNotFoundError:
		pass
	return icon


def _apply_icon(
	app: QGuiApplication,
	*,
	path_for_size: Callable[..., Path],
	sizes: list[int],
):
	icon = _load_icon(path_for_size=path_for_size, sizes=sizes)
	if icon.isNull():
		return
	app.setWindowIcon(icon)


def apply_icon_to_windows(windows: Iterable[object], icon: QIcon | None = None):
	"""Copy the app icon onto QML/QQuick root windows (needed on Windows taskbar)."""
	if icon is None or icon.isNull():
		app = QGuiApplication.instance()
		if app is None:
			return
		icon = app.windowIcon()
	if icon is None or icon.isNull():
		return
	for window in windows:
		set_icon = getattr(window, "setIcon", None)
		if callable(set_icon):
			set_icon(icon)


def apply_app_icon(app: QGuiApplication):
	# On macOS, setWindowIcon overrides the Dock tile while running. Use the
	# squircle-masked artwork so the running Dock icon matches the pinned one.
	if sys.platform == "darwin" and available_macos_icon_sizes():
		_apply_icon(
			app,
			path_for_size=macos_app_icon_path,
			sizes=available_macos_icon_sizes(),
		)
		return
	# Windows prefers a multi-size .ico for the taskbar / Alt-Tab chrome.
	if sys.platform == "win32":
		ico = icon_dir() / "srxy.ico"
		if ico.is_file():
			icon = QIcon(str(ico))
			if not icon.isNull():
				app.setWindowIcon(icon)
				return
	_apply_icon(app, path_for_size=app_icon_path, sizes=available_icon_sizes())


def apply_installer_icon(app: QGuiApplication):
	if sys.platform == "win32":
		ico = icon_dir() / "srxy-installer.ico"
		if ico.is_file():
			icon = QIcon(str(ico))
			if not icon.isNull():
				app.setWindowIcon(icon)
				return
	_apply_icon(
		app,
		path_for_size=installer_icon_path,
		sizes=available_installer_icon_sizes(),
	)


__all__ = [
	"WINDOWS_APP_USER_MODEL_ID",
	"apply_app_icon",
	"apply_desktop_file_name",
	"apply_icon_to_windows",
	"apply_installer_icon",
	"desktop_file_available",
	"ensure_windows_app_user_model_id",
]
