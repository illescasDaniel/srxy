"""Smoke-load Main.qml so invalid property assignments and binding loops fail the gate."""

from __future__ import annotations

import os

import pytest
from PySide6.QtCore import QCoreApplication, QObject, QtMsgType, QUrl, qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from srxy.adapters.inbound.cli.cli import build_parser
from srxy.adapters.inbound.gui.app import qml_dir
from srxy.adapters.inbound.gui.controller import SearchController


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
		if "Binding loop detected" in message:
			warnings.append(message)

	previous = qInstallMessageHandler(_handler)
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	engine = QQmlApplicationEngine()
	engine.rootContext().setContextProperty("controller", controller)
	qml_path = qml_dir() / "Main.qml"

	# when
	engine.load(QUrl.fromLocalFile(str(qml_path)))
	roots = engine.rootObjects()
	assert roots, f"failed to load {qml_path}"
	window = roots[0]
	assert window.objectName() == "mainWindow"
	assert window.findChild(QObject, "searchButton") is not None
	assert window.findChild(QObject, "browseButton") is not None

	for name in (
		"optionsDialog",
		"filtersDialog",
		"helpDialog",
		"downloadConfirmDialog",
		"downloadProgressDialog",
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

	# then
	qInstallMessageHandler(previous)
	assert not warnings, "Qt binding loops:\n" + "\n".join(warnings)
	for root in list(roots):
		root.deleteLater()
	engine.deleteLater()
	qapp.processEvents()
