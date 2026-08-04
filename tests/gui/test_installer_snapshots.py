"""Installer wizard chrome text-tree snapshots."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication

from srxy.adapters.inbound.installer.controller import InstallerController


pytestmark = [pytest.mark.unit, pytest.mark.gui]

_SNAPSHOTS = Path(__file__).resolve().parent / "snapshots"
_UPDATE = os.environ.get("UPDATE_GUI_SNAPSHOTS", "").strip() in {"1", "true", "yes"}


def _chrome_tree(controller: InstallerController) -> str:
	lines = [
		"installerWindow:",
		"  title: srxy installer",
		f"  mode: {controller.mode}",
		f"  page: {controller.page}",
		f"  language: {controller.language}",
		f"  hasGpu: {controller.hasGpu}",
		f"  privacyAck: {controller.privacyAck}",
		f"  downloadTesseract: {controller.downloadTesseract}",
		f"  downloadFfmpeg: {controller.downloadFfmpeg}",
		f"  installSemantic: {controller.installSemantic}",
		f"  prefetchModels: {controller.prefetchModels}",
		f"  addToPath: {controller.addToPath}",
		f"  busy: {controller.busy}",
		f"  finished: {controller.finished}",
		"  modes: Install or update srxy, Reinstall srxy, Uninstall srxy",
		"  pages: mode, prefix, privacy, options, path, uninstall, progress",
		"  optionLabels: Text in images, Audio/video helper, Smarter search (needs a GPU), Download AI models now (nested under Smarter search)",
		"  optionSubtitles: Tesseract, ffmpeg, PyTorch and related packages (PyPI), Hugging Face model files",
		"  pathCheckbox: Also let me run srxy from the Terminal",
		"  languageCombo: English, Español",
		"  buttons: Back, Next, Install, Reinstall, Uninstall, Launch, Finish, Close, Browse…, Info (i), GPU warning (!)",
		"  helpMenu: (installer uses language combo on mode page)",
	]
	return "\n".join(lines) + "\n"


def _assert_snapshot(name: str, tree: str):
	path = _SNAPSHOTS / name
	if _UPDATE or not path.is_file():
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(tree, encoding="utf-8")
	assert path.read_text(encoding="utf-8") == tree


def _ensure_qt_core():
	# Avoid pytest-qt QApplication vs QGuiApplication clashes under xdist.
	if QCoreApplication.instance() is None:
		QCoreApplication([])


def test_given_installer_controller_when_snapshotting_chrome_then_matches(
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	_ensure_qt_core()
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_NO_GPU", "1")
	monkeypatch.delenv("SRXY_LANGUAGE", raising=False)
	# Keep vendor defaults platform-stable (Windows/macOS x86_64 disable catalog downloads).
	monkeypatch.setattr(
		"srxy.adapters.inbound.installer.controller.vendor_downloads_supported",
		lambda: True,
	)
	controller = InstallerController()
	controller.setLanguage("en")

	# when
	tree = _chrome_tree(controller)

	# then
	_assert_snapshot("installer_chrome.snap.txt", tree)
	assert controller.hasGpu is False
