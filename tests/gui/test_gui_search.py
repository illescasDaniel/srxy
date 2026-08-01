from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication
from pytestqt.qtbot import QtBot

from srxy.adapters.inbound.cli.cli import build_parser
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


def test_given_fixture_file_when_controller_searches_then_finds_result(
	qapp: QCoreApplication,
	qtbot: QtBot,
	tmp_path: Path,
):
	(tmp_path / "hello.txt").write_text("hello world from srxy\n", encoding="utf-8")
	args = build_parser().parse_args(["hello", str(tmp_path), "--cli"])
	controller = SearchController(args)

	controller.startSearch()
	qtbot.waitUntil(lambda: not controller.searching, timeout=60000)

	assert controller.resultsModel.rowCount() >= 1
	assert controller.exit_code() == 0


def test_given_uppercase_readme_when_controller_searches_names_then_finds_file(
	qapp: QCoreApplication,
	qtbot: QtBot,
	tmp_path: Path,
):
	# given — filename case must not block a names-only hit
	(tmp_path / "README.md").write_text("docs without matching body text\n", encoding="utf-8")
	(tmp_path / "notes.txt").write_text("unrelated\n", encoding="utf-8")
	args = build_parser().parse_args(["README", str(tmp_path), "--names-only", "--cli"])
	controller = SearchController(args)

	# when
	controller.startSearch()
	qtbot.waitUntil(lambda: not controller.searching, timeout=60000)

	# then
	assert controller.exit_code() == 0
	paths = [
		controller.resultsModel.data(controller.resultsModel.index(row, 0), controller.resultsModel.PathRole)
		for row in range(controller.resultsModel.rowCount())
	]
	assert any(isinstance(path, str) and path.endswith("README.md") for path in paths)
