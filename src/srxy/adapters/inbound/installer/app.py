"""Launch the PySide6 install / uninstall wizard."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from srxy.adapters.inbound.gui.app_icon import (
	apply_app_identity,
	apply_icon_to_windows,
	apply_installer_icon,
	ensure_windows_app_user_model_id,
)
from srxy.adapters.inbound.gui.qt_theme import (
	apply_qt_quick_theme,
	prefer_native_file_dialogs,
	shared_qml_import_path,
)
from srxy.adapters.inbound.installer.controller import InstallerController


def qml_dir() -> Path:
	return Path(__file__).resolve().parent / "qml"


def run_installer() -> int:
	ensure_windows_app_user_model_id("srxy.Installer")
	prefer_native_file_dialogs()
	apply_app_identity("srxy-installer")
	app = QGuiApplication(sys.argv)
	srxy_theme = apply_qt_quick_theme(app)
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
	code = app.exec()
	# Destroy the root windows before the engine so pending async incubations
	# are cancelled first, avoiding "items in the process of being created at
	# engine destruction." at shutdown.
	for root in engine.rootObjects():
		root.deleteLater()
	engine.deleteLater()
	app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
	app.processEvents()
	return code


__all__ = ["run_installer"]
