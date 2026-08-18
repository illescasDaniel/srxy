"""Launch the PySide6 install / uninstall wizard."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from srxy.adapters.inbound.gui.app_icon import (
	apply_desktop_file_name,
	apply_icon_to_windows,
	apply_installer_icon,
	ensure_windows_app_user_model_id,
)
from srxy.adapters.inbound.gui.qt_theme import apply_qt_quick_theme, shared_qml_import_path
from srxy.adapters.inbound.installer.controller import InstallerController


def qml_dir() -> Path:
	return Path(__file__).resolve().parent / "qml"


def run_installer() -> int:
	ensure_windows_app_user_model_id("srxy.Installer")
	app = QGuiApplication(sys.argv)
	app.setApplicationName("srxy-installer")
	app.setOrganizationName("srxy")
	srxy_theme = apply_qt_quick_theme(app)
	apply_desktop_file_name(app, "srxy-installer")
	apply_installer_icon(app)
	from srxy.i18n import get_language, resolve_language, set_language
	from srxy.i18n.qt import install_qt_translator

	set_language(resolve_language())
	install_qt_translator(app, get_language())
	engine = QQmlApplicationEngine()
	engine.addImportPath(shared_qml_import_path())
	controller = InstallerController()
	engine.rootContext().setContextProperty("controller", controller)
	engine.rootContext().setContextProperty("srxyTheme", srxy_theme)
	qml_path = qml_dir() / "Main.qml"
	engine.load(QUrl.fromLocalFile(str(qml_path)))
	if not engine.rootObjects():
		print("error: failed to load installer UI", file=sys.stderr)
		return 2
	apply_icon_to_windows(engine.rootObjects())
	return app.exec()


__all__ = ["run_installer"]
