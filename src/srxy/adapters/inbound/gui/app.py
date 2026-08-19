"""Launch the PySide6 + QML GUI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from srxy.adapters.inbound.gui.app_icon import (
	apply_app_icon,
	apply_desktop_file_name,
	apply_icon_to_windows,
	ensure_windows_app_user_model_id,
)
from srxy.adapters.inbound.gui.controller import SearchController
from srxy.adapters.inbound.gui.desktop import QtDesktopAdapter
from srxy.adapters.inbound.gui.qt_theme import (
	apply_qt_quick_theme,
	prefer_native_file_dialogs,
	shared_qml_import_path,
)
from srxy.bootstrap import build_app_services


def qml_dir() -> Path:
	return Path(__file__).resolve().parent / "qml"


def run_gui(args: argparse.Namespace, *, auto_start: bool = False) -> int:
	ensure_windows_app_user_model_id()
	prefer_native_file_dialogs()
	app = QGuiApplication(sys.argv)
	app.setApplicationName("srxy")
	app.setOrganizationName("srxy")
	srxy_theme = apply_qt_quick_theme(app)
	apply_desktop_file_name(app, "srxy")
	apply_app_icon(app)
	from srxy.i18n import get_language
	from srxy.i18n.qt import install_qt_translator

	install_qt_translator(app, get_language())
	engine = QQmlApplicationEngine()
	engine.addImportPath(shared_qml_import_path())
	services = build_app_services(desktop=QtDesktopAdapter())
	controller = SearchController(
		args,
		search_runner=services.search_runner,
		desktop=services.desktop,
	)
	app.aboutToQuit.connect(controller.shutdown)
	engine.rootContext().setContextProperty("controller", controller)
	engine.rootContext().setContextProperty("srxyTheme", srxy_theme)
	qml_path = qml_dir() / "Main.qml"
	engine.load(QUrl.fromLocalFile(str(qml_path)))
	if not engine.rootObjects():
		print("error: failed to load GUI", file=sys.stderr)
		return 2
	apply_icon_to_windows(engine.rootObjects())
	if auto_start and (args.query or "").strip():
		controller.startSearch()
	code = app.exec()
	# Tear down the QML scene in a controlled order: destroy the root windows
	# first (cancelling any pending async object incubations), then the engine.
	# Deleting the engine while the window is still alive logs "There are still
	# ... items in the process of being created at engine destruction."
	for root in engine.rootObjects():
		root.deleteLater()
	engine.deleteLater()
	app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
	app.processEvents()
	return controller.exit_code() if code == 0 else code


__all__ = ["run_gui"]
