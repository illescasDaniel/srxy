"""Launch the PySide6 + QML GUI."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow

from srxy.adapters.inbound.gui.app_icon import (
	apply_app_icon,
	apply_app_identity,
	apply_icon_to_windows,
	ensure_windows_app_user_model_id,
)
from srxy.adapters.inbound.gui.qt_theme import (
	apply_qt_quick_theme,
	prefer_native_file_dialogs,
	prefer_stable_wayland_rendering,
	shared_qml_import_path,
)
from srxy.adapters.inbound.gui.splash import SplashBridge
from srxy.application.startup_timing import exit_after_qml, mark
from srxy.resources.icons import app_icon_path


_TRUTHY = frozenset({"1", "true", "yes", "on"})


def qml_dir() -> Path:
	return Path(__file__).resolve().parent / "qml"


def splash_enabled() -> bool:
	"""Splash is on by default; ``SRXY_NO_SPLASH=1`` skips it (benchmarks/debug)."""
	return os.environ.get("SRXY_NO_SPLASH", "").strip().lower() not in _TRUTHY


def _flush_gui(app: QGuiApplication):
	"""Push pending paints so a just-loaded splash can appear before more work."""
	app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
	app.processEvents()


def _root_by_name(engine: QQmlApplicationEngine, name: str) -> list[object]:
	return [obj for obj in engine.rootObjects() if obj.objectName() == name]


def _close_splash(engine: QQmlApplicationEngine):
	for splash in _root_by_name(engine, "splashWindow"):
		close = getattr(splash, "close", None)
		if callable(close):
			close()
		splash.deleteLater()


def _reveal_main(engine: QQmlApplicationEngine):
	mains = _root_by_name(engine, "mainWindow")
	for main in mains:
		main.setProperty("visible", True)
	apply_icon_to_windows(mains)
	_close_splash(engine)


def _splash_status(app: QGuiApplication, bridge: SplashBridge | None, text: str):
	if bridge is None:
		return
	bridge.set_status(text)
	_flush_gui(app)


def run_gui(args: argparse.Namespace, *, auto_start: bool = False) -> int:
	ensure_windows_app_user_model_id()
	prefer_stable_wayland_rendering()
	prefer_native_file_dialogs()
	apply_app_identity("srxy")
	# Opaque windows are cheaper to composite; must be set before any Quick window.
	QQuickWindow.setDefaultAlphaBuffer(False)
	app = QGuiApplication(sys.argv)
	# Theme before splash so palette.window / Fluent match the eventual Main window.
	srxy_theme = apply_qt_quick_theme(app)
	mark("qt_ready")

	engine = QQmlApplicationEngine()
	engine.addImportPath(shared_qml_import_path())
	engine.rootContext().setContextProperty("srxyTheme", srxy_theme)

	bridge: SplashBridge | None = None
	if splash_enabled():
		bridge = SplashBridge()
		try:
			icon_url = QUrl.fromLocalFile(str(app_icon_path(size=128)))
		except FileNotFoundError:
			icon_url = QUrl()
		engine.rootContext().setContextProperty("splashBridge", bridge)
		engine.rootContext().setContextProperty("splashIconUrl", icon_url)
		engine.load(QUrl.fromLocalFile(str(qml_dir() / "Splash.qml")))
		if _root_by_name(engine, "splashWindow"):
			_flush_gui(app)
			mark("splash_shown")

	# Icon after first splash paint — not needed for the splash pixmap path.
	apply_app_icon(app)

	from srxy.adapters.inbound.gui.controller import SearchController
	from srxy.adapters.inbound.gui.desktop import QtDesktopAdapter
	from srxy.bootstrap import build_app_services
	from srxy.i18n import get_language
	from srxy.i18n.qt import install_qt_translator

	_splash_status(app, bridge, "Loading translations…")
	install_qt_translator(app, get_language())
	_splash_status(app, bridge, "Starting services…")
	services = build_app_services(desktop=QtDesktopAdapter())
	_splash_status(app, bridge, "Preparing search…")
	controller = SearchController(
		args,
		search_runner=services.search_runner,
		desktop=services.desktop,
	)
	mark("controller_ready")
	app.aboutToQuit.connect(controller.shutdown)
	engine.rootContext().setContextProperty("controller", controller)

	_splash_status(app, bridge, "Loading interface…")
	# Keep Main hidden until content is ready so we do not flash an empty shell
	# over (or under) the splash.
	qml_path = qml_dir() / "Main.qml"
	engine.load(QUrl.fromLocalFile(str(qml_path)))
	if not _root_by_name(engine, "mainWindow"):
		print("error: failed to load GUI", file=sys.stderr)
		_close_splash(engine)
		return 2
	_reveal_main(engine)
	_flush_gui(app)
	mark("qml_loaded")

	if exit_after_qml():
		# Benchmark path: tear down without entering the interactive event loop.
		for root in list(engine.rootObjects()):
			root.deleteLater()
		engine.deleteLater()
		_flush_gui(app)
		return 0
	if auto_start and (args.query or "").strip():
		controller.startSearch()
	code = app.exec()
	# Tear down the QML scene in a controlled order: destroy the root windows
	# first (cancelling any pending async object incubations), then the engine.
	# Deleting the engine while the window is still alive logs "There are still
	# ... items in the process of being created at engine destruction."
	for root in list(engine.rootObjects()):
		root.deleteLater()
	engine.deleteLater()
	_flush_gui(app)
	return controller.exit_code() if code == 0 else code


__all__ = ["qml_dir", "run_gui", "splash_enabled"]
