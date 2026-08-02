"""Launch the PySide6 install / uninstall wizard."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from srxy.adapters.inbound.gui.app_icon import apply_app_icon, apply_desktop_file_name
from srxy.adapters.inbound.installer.controller import InstallerController


def qml_dir() -> Path:
	return Path(__file__).resolve().parent / "qml"


def _follow_system_color_scheme(app: QGuiApplication):
	"""Prefer the desktop light/dark scheme so Quick Controls match the OS."""
	hints = app.styleHints()
	set_scheme = getattr(hints, "setColorScheme", None)
	if set_scheme is None:
		return
	color_scheme = getattr(Qt, "ColorScheme", None)
	if color_scheme is None:
		return
	unknown = getattr(color_scheme, "Unknown", None)
	if unknown is not None:
		set_scheme(unknown)


def run_installer() -> int:
	app = QGuiApplication(sys.argv)
	app.setApplicationName("srxy-installer")
	apply_desktop_file_name(app, "srxy-installer")
	_follow_system_color_scheme(app)
	apply_app_icon(app)
	engine = QQmlApplicationEngine()
	controller = InstallerController()
	engine.rootContext().setContextProperty("controller", controller)
	qml_path = qml_dir() / "Main.qml"
	engine.load(QUrl.fromLocalFile(str(qml_path)))
	if not engine.rootObjects():
		print("error: failed to load installer UI", file=sys.stderr)
		return 2
	return app.exec()


__all__ = ["run_installer"]
