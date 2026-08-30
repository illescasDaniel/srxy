"""Shared helpers for offscreen QML GUI flow tests (Pilot-style)."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPointF, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlProperty
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QTest

from srxy.adapters.inbound.gui.app import qml_dir
from srxy.adapters.inbound.gui.controller import SearchController
from srxy.adapters.inbound.gui.qt_theme import apply_qt_quick_theme, shared_qml_import_path


@dataclass
class GuiHarness:
	"""Loaded Main.qml window plus engine/controller for click-driven tests."""

	controller: SearchController
	engine: QQmlApplicationEngine
	window: QObject
	qapp: QCoreApplication

	def find(self, object_name: str) -> QObject:
		item = self.window.findChild(QObject, object_name)
		assert item is not None, f"missing objectName={object_name!r}"
		return item

	def prop(self, object_name: str, property_name: str) -> Any:
		return QQmlProperty(self.find(object_name), property_name).read()

	def set_prop(self, object_name: str, property_name: str, value: Any):
		ok = QQmlProperty(self.find(object_name), property_name).write(value)
		assert ok, f"failed to write {object_name}.{property_name}"
		self.qapp.processEvents()

	def set_text(self, object_name: str, text: str):
		"""Set a TextField's text (exercises QML onTextChanged → controller)."""
		self.set_prop(object_name, "text", text)

	def click(self, object_name: str):
		"""Synthesize a left click at the centre of a QQuickItem."""
		item = self.find(object_name)
		assert isinstance(item, QQuickItem), f"{object_name!r} is not a QQuickItem"
		quick_window = item.window()
		assert isinstance(quick_window, QQuickWindow), f"{object_name!r} has no QQuickWindow"
		width = float(item.width())
		height = float(item.height())
		assert width > 0 and height > 0, f"{object_name!r} has zero size (visible?)"
		centre = item.mapToScene(QPointF(width / 2.0, height / 2.0)).toPoint()
		QTest.mouseClick(
			quick_window,
			Qt.MouseButton.LeftButton,
			Qt.KeyboardModifier.NoModifier,
			centre,
		)
		self.qapp.processEvents()

	def set_checked(self, object_name: str, checked: bool):
		"""Click a CheckBox until its checked state matches."""
		current = bool(self.prop(object_name, "checked"))
		if current != checked:
			self.click(object_name)
			assert bool(self.prop(object_name, "checked")) is checked, (
				f"{object_name!r} checked stuck at {self.prop(object_name, 'checked')!r}"
			)

	def wait_until(self, predicate: Callable[[], bool], *, timeout_ms: int = 60_000, message: str = ""):
		deadline = time.monotonic() + (timeout_ms / 1000.0)
		while time.monotonic() < deadline:
			if predicate():
				return
			self.qapp.processEvents()
			time.sleep(0.01)
		detail = f": {message}" if message else ""
		raise AssertionError(f"wait_until timed out after {timeout_ms}ms{detail}")

	def wait_search_finished(self, *, timeout_ms: int = 60_000):
		self.wait_until(
			lambda: not bool(self.controller.searching),
			timeout_ms=timeout_ms,
			message="controller.searching stayed true",
		)

	def open_dialog_via(self, button_name: str, dialog_name: str):
		self.click(button_name)
		self.wait_until(
			lambda: bool(self.prop(dialog_name, "visible")) or bool(self.prop(dialog_name, "opened")),
			timeout_ms=5_000,
			message=f"{dialog_name} did not open via {button_name}",
		)

	def apply_dialog_ok(self, ok_name: str, dialog_name: str):
		self.click(ok_name)
		self.wait_until(
			lambda: not (bool(self.prop(dialog_name, "visible")) or bool(self.prop(dialog_name, "opened"))),
			timeout_ms=5_000,
			message=f"{dialog_name} stayed open after {ok_name}",
		)

	def shutdown(self):
		self.controller.shutdown(thread_wait_ms=500)
		self.window.deleteLater()
		self.engine.deleteLater()
		self.qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
		self.qapp.processEvents()


def ensure_qapp() -> QCoreApplication:
	"""Return a process-wide QGuiApplication suitable for offscreen QML tests."""
	import os

	os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
	app = QCoreApplication.instance()
	if app is None:
		app = QGuiApplication([])
		apply_qt_quick_theme(app)
	assert isinstance(app, QCoreApplication)
	return app


def load_main(controller: SearchController, qapp: QCoreApplication | None = None) -> GuiHarness:
	"""Load Main.qml with controller + theme context properties (visible for layout/clicks)."""
	app = qapp if qapp is not None else ensure_qapp()
	engine = QQmlApplicationEngine()
	engine.addImportPath(shared_qml_import_path())
	theme = apply_qt_quick_theme(app)
	engine.rootContext().setContextProperty("controller", controller)
	engine.rootContext().setContextProperty("srxyTheme", theme)
	engine.load(QUrl.fromLocalFile(str(qml_dir() / "Main.qml")))
	roots = engine.rootObjects()
	assert roots, "failed to load Main.qml"
	window = roots[0]
	assert isinstance(window, QObject)
	# Production run_gui reveals Main after splash; tests need it visible for hit-testing.
	window.setProperty("visible", True)
	app.processEvents()
	return GuiHarness(controller=controller, engine=engine, window=window, qapp=app)
