"""Installer wizard chrome text-tree snapshots."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication
from pytestqt.qtbot import QtBot

from srxy.adapters.inbound.installer.controller import InstallerController


pytestmark = [pytest.mark.integration, pytest.mark.gui]

_SNAPSHOTS = Path(__file__).resolve().parent / "snapshots"
_UPDATE = os.environ.get("UPDATE_GUI_SNAPSHOTS", "").strip() in {"1", "true", "yes"}


def _chrome_tree(controller: InstallerController) -> str:
	lines = [
		"installerWindow:",
		"  title: srxy installer",
		f"  mode: {controller.mode}",
		f"  page: {controller.page}",
		f"  hasGpu: {controller.hasGpu}",
		f"  privacyAck: {controller.privacyAck}",
		f"  downloadTesseract: {controller.downloadTesseract}",
		f"  downloadFfmpeg: {controller.downloadFfmpeg}",
		f"  installSemantic: {controller.installSemantic}",
		f"  prefetchModels: {controller.prefetchModels}",
		f"  busy: {controller.busy}",
		f"  finished: {controller.finished}",
		"  modes: Install srxy, Uninstall srxy",
		"  pages: mode, prefix, privacy, options, uninstall, progress",
		"  optionLabels: Text in images, Spoken words helper, AI search extras, Download AI models now",
		"  buttons: Back, Next, Install, Uninstall, Close, Info (i), GPU warning (!)",
	]
	return "\n".join(lines) + "\n"


def _assert_snapshot(name: str, tree: str):
	path = _SNAPSHOTS / name
	if _UPDATE or not path.is_file():
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(tree, encoding="utf-8")
	assert path.read_text(encoding="utf-8") == tree


@pytest.fixture
def qapp(qapp: QGuiApplication) -> QGuiApplication:
	return qapp


def test_given_installer_controller_when_snapshotting_chrome_then_matches(
	qtbot: QtBot,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_NO_GPU", "1")
	controller = InstallerController()

	# when
	tree = _chrome_tree(controller)

	# then
	_assert_snapshot("installer_chrome.snap.txt", tree)
	assert controller.hasGpu is False
	_ = qtbot  # keep pytest-qt app lifecycle
