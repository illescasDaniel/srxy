"""QML layout smoke for What/How query chrome (mode in How, Search accessory)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest
from PySide6.QtCore import Q_ARG, QCoreApplication, QMetaObject, QPointF, Qt, QtMsgType, qInstallMessageHandler
from PySide6.QtQml import QQmlProperty
from PySide6.QtQuick import QQuickItem
from tests.gui.helpers import ensure_qapp, load_main

from srxy.adapters.inbound.cli.cli import build_parser
from srxy.adapters.inbound.gui.controller import SearchController


pytestmark = [pytest.mark.integration, pytest.mark.gui]


@pytest.fixture(scope="module")
def qapp() -> QCoreApplication:
	return ensure_qapp()


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
	harness = load_main(controller, qapp)
	for _ in range(20):
		qapp.processEvents()

	mode_box = harness.find("queryModeBox")
	search_button = harness.find("searchButton")
	simple_field = harness.find("simpleQueryField")
	options_button = harness.find("optionsButton")
	harness.find("filtersButton")

	# then
	qInstallMessageHandler(previous)
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
	harness.shutdown()


def test_given_multi_terms_when_removing_term_then_no_root_reference_error(qapp: QCoreApplication):
	# given
	msgs: list[str] = []

	def _handler(_mode: QtMsgType, _context: object, message: str):
		if "ReferenceError" in message or "root is not defined" in message:
			msgs.append(message)

	previous = qInstallMessageHandler(_handler)
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	harness = load_main(controller, qapp)

	# when
	QMetaObject.invokeMethod(
		harness.window,
		"applyDemoMultiTerms",
		Qt.ConnectionType.DirectConnection,
		Q_ARG(str, '["alpha", "beta", "gamma"]'),
	)
	for _ in range(15):
		qapp.processEvents()
	# Shrink back to one term via the same helper.
	QMetaObject.invokeMethod(
		harness.window,
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
	harness.shutdown()


def test_given_multi_term_growth_when_terms_added_then_search_button_stays_top_pinned(
	qapp: QCoreApplication,
):
	# given — start multi-term mode with a single term (initial/top position).
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	harness = load_main(controller, qapp)
	for _ in range(20):
		qapp.processEvents()

	search_button = harness.find("searchButton")
	assert isinstance(search_button, QQuickItem)

	def _search_button_scene_y() -> float:
		return search_button.mapToScene(QPointF(0.0, 0.0)).y()

	QMetaObject.invokeMethod(
		harness.window,
		"applyDemoMultiTerms",
		Qt.ConnectionType.DirectConnection,
		Q_ARG("QVariant", json.dumps(["one"])),
	)
	for _ in range(15):
		qapp.processEvents()
	initial_y = _search_button_scene_y()
	initial_height = float(harness.prop("multiTermColumn", "height") or 0)

	# when — grow the term list well beyond a single row.
	QMetaObject.invokeMethod(
		harness.window,
		"applyDemoMultiTerms",
		Qt.ConnectionType.DirectConnection,
		Q_ARG("QVariant", json.dumps(["one", "two", "three", "four", "five", "six"])),
	)
	for _ in range(15):
		qapp.processEvents()
	grown_height = float(harness.prop("multiTermColumn", "height") or 0)
	grown_y = _search_button_scene_y()

	# then — the term list actually grew taller, yet Search stayed at its
	# initial (top) y instead of re-centring within the taller row.
	assert grown_height > initial_height + 10.0, (
		f"expected term list to grow: initial={initial_height} grown={grown_height}"
	)
	assert abs(grown_y - initial_y) < 1.0, f"searchButton moved: initial_y={initial_y} grown_y={grown_y}"

	# and — shrinking back to one term restores the exact same y (idempotent).
	QMetaObject.invokeMethod(
		harness.window,
		"applyDemoMultiTerms",
		Qt.ConnectionType.DirectConnection,
		Q_ARG("QVariant", json.dumps(["one"])),
	)
	for _ in range(15):
		qapp.processEvents()
	shrunk_y = _search_button_scene_y()
	assert abs(shrunk_y - initial_y) < 1.0, f"searchButton did not restore y: initial_y={initial_y} shrunk_y={shrunk_y}"

	harness.shutdown()


def test_given_cancelled_search_when_finished_then_search_button_stays_accented(
	qapp: QCoreApplication,
	tmp_path: Path,
):
	# given — Search accent tracks controller.stale; cancel must not drop it
	(tmp_path / "note.txt").write_text("alpha\n", encoding="utf-8")
	args = build_parser().parse_args(["zzzz-no-match-token", str(tmp_path), "--cli"])
	controller = SearchController(args)
	harness = load_main(controller, qapp)
	for _ in range(20):
		qapp.processEvents()
	search_button = harness.find("searchButton")
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
	harness.shutdown()
