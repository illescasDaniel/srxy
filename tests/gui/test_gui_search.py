from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication

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
	tmp_path: Path,
):
	# given
	import time

	(tmp_path / "hello.txt").write_text("hello world from srxy\n", encoding="utf-8")
	args = build_parser().parse_args(["hello", str(tmp_path), "--cli"])
	controller = SearchController(args)

	# when
	controller.startSearch()
	deadline = time.monotonic() + 60
	while controller.searching and time.monotonic() < deadline:
		qapp.processEvents()
		time.sleep(0.01)

	# then
	assert not controller.searching
	assert controller.resultsModel.rowCount() >= 1
	assert controller.exit_code() == 0
	controller.shutdown(thread_wait_ms=500)


def test_given_uppercase_readme_when_controller_searches_names_then_finds_file(
	qapp: QCoreApplication,
	tmp_path: Path,
):
	# given — filename case must not block a names-only hit
	import time

	(tmp_path / "README.md").write_text("docs without matching body text\n", encoding="utf-8")
	(tmp_path / "notes.txt").write_text("unrelated\n", encoding="utf-8")
	args = build_parser().parse_args(["README", str(tmp_path), "--names-only", "--cli"])
	controller = SearchController(args)

	# when
	controller.startSearch()
	deadline = time.monotonic() + 60
	while controller.searching and time.monotonic() < deadline:
		qapp.processEvents()
		time.sleep(0.01)

	# then
	assert not controller.searching
	assert controller.exit_code() == 0
	paths = [
		controller.resultsModel.data(controller.resultsModel.index(row, 0), controller.resultsModel.PathRole)
		for row in range(controller.resultsModel.rowCount())
	]
	assert any(isinstance(path, str) and path.endswith("README.md") for path in paths)
	controller.shutdown(thread_wait_ms=500)
