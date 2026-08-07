"""Installer wizard chrome text-tree snapshots."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication

from srxy.adapters.inbound.installer.controller import InstallerController
from srxy.i18n import tr


pytestmark = [pytest.mark.unit, pytest.mark.gui]

_SNAPSHOTS = Path(__file__).resolve().parent / "snapshots"
_UPDATE = os.environ.get("UPDATE_GUI_SNAPSHOTS", "").strip() in {"1", "true", "yes"}


def _chrome_tree(controller: InstallerController) -> str:
	models_nested = (
		f"{tr('installer.options.models')} (nested under {tr('installer.options.semantic').split('(')[0].strip()})"
	)
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
		"  modes: "
		+ ", ".join(
			[
				tr("installer.mode.install"),
				tr("installer.mode.reinstall"),
				tr("installer.mode.uninstall"),
			]
		),
		"  pages: mode, prefix, privacy, options, tessdata, path, uninstall, progress",
		"  optionLabels: "
		+ ", ".join(
			[
				tr("installer.options.tesseract"),
				tr("installer.options.ffmpeg"),
				tr("installer.options.semantic"),
				models_nested,
			]
		),
		"  optionSubtitles: "
		+ ", ".join(
			[
				tr("installer.options.tesseract_sub"),
				tr("installer.options.ffmpeg_sub"),
				tr("installer.options.semantic_sub"),
				tr("installer.options.models_sub"),
			]
		),
		f"  tessdataPage: {tr('installer.tessdata.title')}; {tr('installer.tessdata.body')}",
		f"  pathCheckbox: {tr('installer.path.checkbox')}",
		f"  languageCombo: {tr('menu.language.en')}, {tr('menu.language.es')}",
		"  buttons: "
		+ ", ".join(
			[
				tr("common.back"),
				tr("common.next"),
				tr("installer.button.install"),
				tr("installer.button.reinstall"),
				tr("installer.button.uninstall"),
				tr("installer.button.launch"),
				tr("common.finish"),
				tr("common.close"),
				tr("gui.browse"),
				"Info (i)",
				"GPU warning (!)",
			]
		),
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


def _make_controller(monkeypatch: pytest.MonkeyPatch, *, language: str) -> InstallerController:
	_ensure_qt_core()
	monkeypatch.setenv("SRXY_INSTALLER_FORCE_NO_GPU", "1")
	monkeypatch.delenv("SRXY_LANGUAGE", raising=False)
	# Keep vendor defaults platform-stable (Windows/macOS x86_64 disable catalog downloads).
	monkeypatch.setattr(
		"srxy.adapters.inbound.installer.controller.vendor_downloads_supported",
		lambda: True,
	)
	controller = InstallerController()
	controller.setLanguage(language)
	return controller


def test_given_installer_controller_when_snapshotting_chrome_then_matches(
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	controller = _make_controller(monkeypatch, language="en")

	# when
	tree = _chrome_tree(controller)

	# then
	_assert_snapshot("installer_chrome.snap.txt", tree)
	assert controller.hasGpu is False


def test_given_spanish_installer_controller_when_snapshotting_chrome_then_matches(
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	controller = _make_controller(monkeypatch, language="es")

	# when
	tree = _chrome_tree(controller)

	# then
	_assert_snapshot("installer_chrome_es.snap.txt", tree)
	assert controller.language == "es"
	assert tr("installer.mode.install") in tree
