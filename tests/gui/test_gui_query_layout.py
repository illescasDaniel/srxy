"""QML layout smoke for What/How query chrome (mode in How, Search accessory)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest
from PySide6.QtCore import Q_ARG, QCoreApplication, QMetaObject, QObject, Qt, QtMsgType, QUrl, qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlProperty

from srxy.adapters.inbound.cli.cli import build_parser
from srxy.adapters.inbound.gui.app import qml_dir
from srxy.adapters.inbound.gui.controller import SearchController
from srxy.adapters.inbound.gui.qt_theme import apply_qt_quick_theme, shared_qml_import_path


pytestmark = [pytest.mark.integration, pytest.mark.gui]


@pytest.fixture(scope="module")
def qapp() -> QCoreApplication:
	os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
	app = QCoreApplication.instance()
	if app is None:
		app = QGuiApplication([])
		apply_qt_quick_theme(app)
	assert isinstance(app, QCoreApplication)
	return app


def _load_main(controller: SearchController) -> tuple[QQmlApplicationEngine, QObject]:
	engine = QQmlApplicationEngine()
	engine.addImportPath(shared_qml_import_path())
	theme = apply_qt_quick_theme(QCoreApplication.instance())  # type: ignore[arg-type]
	engine.rootContext().setContextProperty("controller", controller)
	engine.rootContext().setContextProperty("srxyTheme", theme)
	engine.load(QUrl.fromLocalFile(str(qml_dir() / "Main.qml")))
	roots = engine.rootObjects()
	assert roots, "failed to load Main.qml"
	window = roots[0]
	assert isinstance(window, QObject)
	return engine, window


def _shutdown(controller: SearchController, engine: QQmlApplicationEngine, window: QObject, qapp: QCoreApplication):
	controller.shutdown(thread_wait_ms=500)
	window.deleteLater()
	engine.deleteLater()
	qapp.processEvents()


def test_given_main_qml_when_loaded_then_mode_box_lives_in_how_and_search_button_exists(
	qapp: QCoreApplication,
):
	# given
	msgs: list[str] = []

	def _handler(_mode: QtMsgType, _context: object, message: str):
		if any(token in message for token in ("Binding loop", "ReferenceError", "TypeError")):
			msgs.append(message)

	previous = qInstallMessageHandler(_handler)
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)

	# when
	engine, window = _load_main(controller)
	for _ in range(20):
		qapp.processEvents()

	mode_box = window.findChild(QObject, "queryModeBox")
	search_button = window.findChild(QObject, "searchButton")
	simple_field = window.findChild(QObject, "simpleQueryField")
	options_button = window.findChild(QObject, "optionsButton")
	filters_button = window.findChild(QObject, "filtersButton")

	# then
	qInstallMessageHandler(previous)
	assert mode_box is not None
	assert search_button is not None
	assert simple_field is not None
	assert options_button is not None
	assert filters_button is not None
	# Mode selector is a sibling section of Options/Filters under How's column.
	options_parent = options_button.parent()
	assert options_parent is not None
	how_column = options_parent.parent()
	assert how_column is not None
	assert mode_box.parent() is how_column
	field_h = float(simple_field.property("implicitHeight") or 0)
	btn_h = float(search_button.property("height") or 0)
	btn_implicit_h = float(search_button.property("implicitHeight") or 0)
	assert field_h > 0
	assert btn_h > 0
	# Windows Fluent stretches the Search button to the field height; macOS/Linux
	# keep the native button size (taller than the field) and centre it instead.
	if sys.platform == "win32":
		assert abs(btn_h - field_h) <= 2.0
	else:
		assert abs(btn_h - btn_implicit_h) <= 2.0
		assert btn_h + 0.5 >= field_h
	assert not msgs, "QML errors:\n" + "\n".join(msgs)
	_shutdown(controller, engine, window, qapp)


def test_given_multi_terms_when_removing_term_then_no_root_reference_error(qapp: QCoreApplication):
	# given
	msgs: list[str] = []

	def _handler(_mode: QtMsgType, _context: object, message: str):
		if "ReferenceError" in message or "root is not defined" in message:
			msgs.append(message)

	previous = qInstallMessageHandler(_handler)
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	engine, window = _load_main(controller)

	# when
	QMetaObject.invokeMethod(
		window,
		"applyDemoMultiTerms",
		Qt.ConnectionType.DirectConnection,
		Q_ARG(str, '["alpha", "beta", "gamma"]'),
	)
	for _ in range(15):
		qapp.processEvents()
	# Shrink back to one term via the same helper.
	QMetaObject.invokeMethod(
		window,
		"applyDemoMultiTerms",
		Qt.ConnectionType.DirectConnection,
		Q_ARG(str, '["only"]'),
	)
	for _ in range(15):
		qapp.processEvents()

	# then
	qInstallMessageHandler(previous)
	assert not msgs, "QML ReferenceErrors:\n" + "\n".join(msgs)
	assert controller.queryMode in {"simple", "multi", "advanced"}
	_shutdown(controller, engine, window, qapp)


def test_given_cancelled_search_when_finished_then_search_button_stays_accented(qapp: QCoreApplication, tmp_path: Path):
	# given — Search accent tracks controller.stale; cancel must not drop it
	(tmp_path / "note.txt").write_text("alpha\n", encoding="utf-8")
	args = build_parser().parse_args(["zzzz-no-match-token", str(tmp_path), "--cli"])
	controller = SearchController(args)
	engine, window = _load_main(controller)
	for _ in range(20):
		qapp.processEvents()
	search_button = window.findChild(QObject, "searchButton")
	assert search_button is not None
	assert QQmlProperty(search_button, "accent").read() is True

	# when
	controller.startSearch()
	controller.cancelSearch()
	deadline = time.monotonic() + 30
	while controller.searching and time.monotonic() < deadline:
		qapp.processEvents()
		time.sleep(0.01)
	qapp.processEvents()

	# then
	assert not controller.searching
	assert controller.stale is True
	assert QQmlProperty(search_button, "accent").read() is True
	assert QQmlProperty(search_button, "highlighted").read() is True
	_shutdown(controller, engine, window, qapp)
