from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QCoreApplication

from srxy.adapters.inbound.cli.cli import build_parser
from srxy.adapters.inbound.gui.controller import SearchController


pytestmark = [pytest.mark.unit, pytest.mark.xdist_group("gui")]


@pytest.fixture(scope="module")
def qapp() -> QCoreApplication:
	os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
	app = QCoreApplication.instance()
	if app is None:
		from PySide6.QtGui import QGuiApplication

		app = QGuiApplication([])
	assert isinstance(app, QCoreApplication)
	return app


def test_given_controller_when_about_to_quit_signal_fired_then_shutdown_runs(qapp: QCoreApplication, tmp_path: Path):
	# given
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	shutdown = MagicMock()
	controller.shutdown = shutdown  # type: ignore[method-assign]

	# when
	qapp.aboutToQuit.connect(controller.shutdown)
	qapp.aboutToQuit.emit()

	# then
	shutdown.assert_called_once()


def test_given_run_gui_when_loading_then_connects_shutdown_to_about_to_quit(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	monkeypatch.setenv("SRXY_SKIP_UPDATE_CHECK", "1")
	quit_slots: list[object] = []

	class FakeApp:
		def __init__(self, _argv: list[str]):
			self.aboutToQuit = MagicMock()
			self.aboutToQuit.connect = quit_slots.append

		def setApplicationName(self, _name: str):
			return None

		def setOrganizationName(self, _name: str):
			return None

		def exec(self) -> int:
			for slot in quit_slots:
				slot()  # type: ignore[operator]
			return 0

	class FakeEngine:
		def __init__(self):
			self.rootContext = MagicMock(return_value=MagicMock(setContextProperty=MagicMock()))

		def rootObjects(self) -> list[object]:
			return [object()]

		def load(self, _url: Any):
			return None

	with (
		patch("srxy.adapters.inbound.gui.app.QGuiApplication", FakeApp),
		patch("srxy.adapters.inbound.gui.app.QQmlApplicationEngine", FakeEngine),
		patch("srxy.adapters.inbound.gui.app.apply_app_icon"),
		patch("srxy.adapters.inbound.gui.app.apply_desktop_file_name"),
		patch("srxy.adapters.inbound.gui.app.apply_qt_quick_theme"),
		patch("srxy.i18n.qt.install_qt_translator"),
		patch("srxy.i18n.get_language", return_value="en"),
		patch("srxy.adapters.inbound.gui.app.build_app_services"),
	):
		from srxy.adapters.inbound.gui.app import run_gui

		code = run_gui(args)

	assert len(quit_slots) == 1
	assert callable(quit_slots[0])
	assert code == 0
