"""Launch the PySide6 + QML GUI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from srxy.adapters.inbound.gui.app_icon import apply_app_icon, apply_desktop_file_name
from srxy.adapters.inbound.gui.controller import SearchController
from srxy.adapters.inbound.gui.desktop import QtDesktopAdapter
from srxy.bootstrap import build_app_services


def qml_dir() -> Path:
	return Path(__file__).resolve().parent / "qml"


def run_gui(args: argparse.Namespace, *, auto_start: bool = False) -> int:
	app = QGuiApplication(sys.argv)
	app.setApplicationName("srxy")
	apply_desktop_file_name(app, "srxy")
	apply_app_icon(app)
	from srxy.i18n import get_language
	from srxy.i18n.qt import install_qt_translator

	install_qt_translator(app, get_language())
	engine = QQmlApplicationEngine()
	services = build_app_services(desktop=QtDesktopAdapter())
	controller = SearchController(
		args,
		search_runner=services.search_runner,
		desktop=services.desktop,
	)
	app.aboutToQuit.connect(controller.shutdown)
	engine.rootContext().setContextProperty("controller", controller)
	qml_path = qml_dir() / "Main.qml"
	engine.load(QUrl.fromLocalFile(str(qml_path)))
	if not engine.rootObjects():
		print("error: failed to load GUI", file=sys.stderr)
		return 2
	if auto_start and (args.query or "").strip():
		controller.startSearch()
	code = app.exec()
	return controller.exit_code() if code == 0 else code


__all__ = ["run_gui"]
