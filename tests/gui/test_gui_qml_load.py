"""Smoke-load Main.qml so invalid property assignments and binding loops fail the gate."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject, QtMsgType, QUrl, qInstallMessageHandler
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlProperty

from srxy.adapters.inbound.cli.cli import build_parser
from srxy.adapters.inbound.gui.app import qml_dir
from srxy.adapters.inbound.gui.controller import SearchController
from srxy.adapters.inbound.gui.qt_theme import apply_qt_quick_theme, shared_qml_import_path
from srxy.application.search_session import SearchFinishedEvent
from srxy.domain.models import FileSearchResult


pytestmark = [pytest.mark.integration, pytest.mark.gui]


@pytest.fixture(scope="module")
def qapp() -> QCoreApplication:
	os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
	app = QCoreApplication.instance()
	if app is None:
		app = QGuiApplication([])
	assert isinstance(app, QCoreApplication)
	return app


def test_given_gui_qml_when_engine_loads_and_opens_dialogs_then_no_binding_loops(qapp: QCoreApplication):
	# given
	warnings: list[str] = []

	def _handler(_mode: QtMsgType, _context: object, message: str):
		if (
			"Binding loop detected" in message
			or "in the process of being created" in message
			or "DelegateModel" in message
			or "index out range" in message
			# Native styles (macOS Aqua) reject custom contentItems/backgrounds.
			# The Search button must use text+icon instead of a custom Row.
			or "does not support customization of this control" in message
		):
			warnings.append(message)

	previous = qInstallMessageHandler(_handler)
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	srxy_theme = apply_qt_quick_theme(qapp)
	engine = QQmlApplicationEngine()
	engine.addImportPath(shared_qml_import_path())
	engine.rootContext().setContextProperty("controller", controller)
	engine.rootContext().setContextProperty("srxyTheme", srxy_theme)
	qml_path = qml_dir() / "Main.qml"

	# when
	engine.load(QUrl.fromLocalFile(str(qml_path)))
	roots = engine.rootObjects()
	assert roots, f"failed to load {qml_path}"
	window = roots[0]
	window.setProperty("visible", True)
	assert window.objectName() == "mainWindow"
	assert window.findChild(QObject, "searchButton") is not None
	assert window.findChild(QObject, "browseButton") is not None
	assert window.findChild(QObject, "queryModeBox") is not None
	assert window.findChild(QObject, "simpleQueryField") is not None
	assert window.findChild(QObject, "optionsButton") is not None
	assert window.findChild(QObject, "filtersButton") is not None

	for name in (
		"optionsDialog",
		"filtersDialog",
		"helpDialog",
		"downloadConfirmDialog",
		"downloadProgressDialog",
		"searchWarningsDialog",
		"errorDialog",
	):
		dialog = window.findChild(QObject, name)
		assert dialog is not None, name
		open_fn = getattr(dialog, "open", None)
		close_fn = getattr(dialog, "close", None)
		assert callable(open_fn) and callable(close_fn), name
		open_fn()
		qapp.processEvents()
		close_fn()
		qapp.processEvents()

	# then — destroy the window before the engine (matching run_gui) so any
	# pending async delegate incubations are cancelled first. Teardown must not
	# emit "items in the process of being created at engine destruction."
	controller.shutdown(thread_wait_ms=500)
	for root in list(roots):
		root.deleteLater()
	engine.deleteLater()
	qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
	qapp.processEvents()
	qInstallMessageHandler(previous)
	assert not warnings, "Qt warnings:\n" + "\n".join(warnings)


def _color_name(value: object) -> str:
	assert isinstance(value, QColor)
	return value.name()


def test_given_dialog_ok_buttons_when_loaded_then_render_accent_fill_and_foreground(qapp: QCoreApplication):
	# given
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	srxy_theme = apply_qt_quick_theme(qapp)
	engine = QQmlApplicationEngine()
	engine.addImportPath(shared_qml_import_path())
	engine.rootContext().setContextProperty("controller", controller)
	engine.rootContext().setContextProperty("srxyTheme", srxy_theme)
	qml_path = qml_dir() / "Main.qml"

	# when
	engine.load(QUrl.fromLocalFile(str(qml_path)))
	roots = engine.rootObjects()
	assert roots, f"failed to load {qml_path}"
	window = roots[0]
	window.setProperty("visible", True)

	# then — DialogButtonBox must drive the accent (highlighted) state of the
	# OK buttons. ``foreground`` and ``palette.buttonText`` must match onAccent
	# (macOS/Fusion IconLabels draw the label from palette.buttonText).
	expected = srxy_theme.onAccent.name()
	for dialog_name, button_name in (
		("optionsDialog", "optionsOkButton"),
		("filtersDialog", "filtersOkButton"),
	):
		dialog = window.findChild(QObject, dialog_name)
		assert dialog is not None, dialog_name
		open_fn = getattr(dialog, "open", None)
		assert callable(open_fn), dialog_name
		open_fn()
		qapp.processEvents()
		button = window.findChild(QObject, button_name)
		assert button is not None, button_name
		assert QQmlProperty(button, "highlighted").read() is True, button_name
		assert _color_name(QQmlProperty(button, "foreground").read()) == expected, button_name
		assert _color_name(QQmlProperty(button, "palette.buttonText").read()) == expected, button_name
		dialog.close()
		qapp.processEvents()

	controller.shutdown(thread_wait_ms=500)
	for root in list(roots):
		root.deleteLater()
	engine.deleteLater()
	qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
	qapp.processEvents()


def test_given_results_when_running_a_new_search_then_no_delegate_model_warning(
	qapp: QCoreApplication,
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	"""A new search must not log ``DelegateModel::cancel: index out range``.

	Regression guard: `ResultsModel.clear()`/`replace_results()` used to do a
	full ``beginResetModel()``, invalidating rows while the ListView's async
	``currentIndex`` binding and in-flight delegate incubations were stale. The
	model now mutates rows explicitly, so no stale cancel index is requested.
	"""
	# given
	warnings: list[str] = []

	def _handler(_mode: QtMsgType, _context: object, message: str):
		if "DelegateModel" in message or "index out range" in message:
			warnings.append(message)

	previous = qInstallMessageHandler(_handler)
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	monkeypatch.setattr(controller, "_start_search_worker", lambda _args: None)
	srxy_theme = apply_qt_quick_theme(qapp)
	engine = QQmlApplicationEngine()
	engine.addImportPath(shared_qml_import_path())
	engine.rootContext().setContextProperty("controller", controller)
	engine.rootContext().setContextProperty("srxyTheme", srxy_theme)
	engine.load(QUrl.fromLocalFile(str(qml_dir() / "Main.qml")))
	roots = engine.rootObjects()
	assert roots, "failed to load Main.qml"
	roots[0].setProperty("visible", True)

	results = [
		FileSearchResult(path=tmp_path / f"file{i}.txt", score=0.9 - i * 0.01, breakdown={"content": 0.9}, lines=[])
		for i in range(8)
	]

	# when — first search populates the model and selects row 0; the second
	# search clears the selection and the model while delegates are in flight.
	for _ in range(2):
		controller.handle_search_event_for_tests(SearchFinishedEvent(results=results, skipped_files=[]))
		qapp.processEvents()
		controller._begin_search(args)  # pyright: ignore[reportPrivateUsage]
		qapp.processEvents()

	controller.shutdown(thread_wait_ms=500)
	for root in list(roots):
		root.deleteLater()
	engine.deleteLater()
	qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
	qapp.processEvents()
	qInstallMessageHandler(previous)

	# then
	assert not warnings, "Qt warnings:\n" + "\n".join(warnings)


def test_given_splash_qml_when_engine_loads_then_shows_branding_and_status(qapp: QCoreApplication):
	# given
	warnings: list[str] = []

	def _handler(_mode: QtMsgType, _context: object, message: str):
		if "Binding loop detected" in message or "ReferenceError" in message:
			warnings.append(message)

	previous = qInstallMessageHandler(_handler)
	from PySide6.QtQml import QQmlProperty

	from srxy.adapters.inbound.gui.splash import SplashBridge
	from srxy.application.branding import AUTHOR
	from srxy.resources.icons import app_icon_path

	srxy_theme = apply_qt_quick_theme(qapp)
	bridge = SplashBridge()
	engine = QQmlApplicationEngine()
	engine.addImportPath(shared_qml_import_path())
	engine.rootContext().setContextProperty("srxyTheme", srxy_theme)
	engine.rootContext().setContextProperty("splashBridge", bridge)
	engine.rootContext().setContextProperty(
		"splashIconUrl",
		QUrl.fromLocalFile(str(app_icon_path(size=128))),
	)

	# when
	engine.load(QUrl.fromLocalFile(str(qml_dir() / "Splash.qml")))
	roots = engine.rootObjects()
	assert roots, "failed to load Splash.qml"
	window = roots[0]
	assert window.objectName() == "splashWindow"
	app_name = window.findChild(QObject, "splashAppName")
	author = window.findChild(QObject, "splashAuthor")
	ver = window.findChild(QObject, "splashVersion")
	status = window.findChild(QObject, "splashStatus")
	assert app_name is not None
	assert author is not None
	assert ver is not None
	assert status is not None
	assert QQmlProperty(app_name, "text").read() == "srxy"
	assert AUTHOR in str(QQmlProperty(author, "text").read())
	assert str(QQmlProperty(ver, "text").read()).startswith("v")
	assert "Loading" in str(QQmlProperty(status, "text").read())

	bridge.set_status("Preparing search…")
	qapp.processEvents()
	assert QQmlProperty(status, "text").read() == "Preparing search…"

	# then
	for root in list(roots):
		root.deleteLater()
	engine.deleteLater()
	qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
	qapp.processEvents()
	qInstallMessageHandler(previous)
	assert not warnings, "Qt warnings:\n" + "\n".join(warnings)
