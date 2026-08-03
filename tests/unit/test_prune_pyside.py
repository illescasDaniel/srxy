"""Unit tests for packaging/linux-appimage/prune_pyside.sh."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest


pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
PRUNE_SCRIPT = REPO_ROOT / "packaging" / "linux-appimage" / "prune_pyside.sh"


def _touch(path: Path):
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_bytes(b"x")


def _make_fake_pyside(site: Path) -> Path:
	pside = site / "PySide6"
	# Keepers
	for name in ("QtCore", "QtGui", "QtQml", "QtQuick", "QtQuickControls2", "QtNetwork", "QtDBus", "QtOpenGL"):
		_touch(pside / f"{name}.abi3.so")
	# Removals
	for name in ("QtWebEngineCore", "QtWidgets", "QtMultimedia", "QtCharts"):
		_touch(pside / f"{name}.abi3.so")
	_touch(pside / "QtCore.pyi")
	_touch(pside / "designer")
	_touch(pside / "qmlls")
	_touch(pside / "include" / "QtCore" / "qobject.h")
	_touch(pside / "Qt" / "lib" / "libQt6Core.so.6")
	_touch(pside / "Qt" / "lib" / "libQt6Gui.so.6")
	_touch(pside / "Qt" / "lib" / "libQt6Quick.so.6")
	_touch(pside / "Qt" / "lib" / "libQt6WebEngineCore.so.6")
	_touch(pside / "Qt" / "lib" / "libavcodec.so.61")
	_touch(pside / "Qt" / "qml" / "QtQuick" / "qmldir")
	_touch(pside / "Qt" / "qml" / "QtQuick" / "Controls" / "qmldir")
	_touch(pside / "Qt" / "qml" / "QtQuick" / "Dialogs" / "qmldir")
	_touch(pside / "Qt" / "qml" / "QtQuick" / "Pdf" / "qmldir")
	_touch(pside / "Qt" / "qml" / "QtWebEngine" / "qmldir")
	_touch(pside / "Qt" / "qml" / "Qt" / "labs" / "folderlistmodel" / "qmldir")
	_touch(pside / "Qt" / "qml" / "Qt" / "labs" / "wavefrontmesh" / "qmldir")
	_touch(pside / "Qt" / "plugins" / "platforms" / "libqxcb.so")
	_touch(pside / "Qt" / "plugins" / "multimedia" / "libffmpeg.so")
	_touch(pside / "Qt" / "plugins" / "webview" / "libwebview.so")
	return pside


def test_given_fake_pyside_tree_when_pruning_then_removes_unused_keeps_wizard_stack(tmp_path: Path):
	# given
	site = tmp_path / "lib" / "python3.12" / "site-packages"
	pside = _make_fake_pyside(site)
	venv = tmp_path
	assert PRUNE_SCRIPT.is_file()
	assert os.access(PRUNE_SCRIPT, os.X_OK) or (PRUNE_SCRIPT.stat().st_mode & stat.S_IXUSR)

	# when
	result = subprocess.run(  # noqa: S603
		[str(PRUNE_SCRIPT), str(venv)],
		check=False,
		capture_output=True,
		text=True,
	)

	# then
	assert result.returncode == 0, result.stderr or result.stdout
	assert (pside / "QtCore.abi3.so").is_file()
	assert (pside / "QtQuick.abi3.so").is_file()
	assert (pside / "Qt" / "lib" / "libQt6Core.so.6").is_file()
	assert (pside / "Qt" / "lib" / "libQt6Quick.so.6").is_file()
	assert (pside / "Qt" / "qml" / "QtQuick" / "Controls" / "qmldir").is_file()
	assert (pside / "Qt" / "qml" / "QtQuick" / "Dialogs" / "qmldir").is_file()
	assert (pside / "Qt" / "qml" / "Qt" / "labs" / "folderlistmodel" / "qmldir").is_file()
	assert (pside / "Qt" / "plugins" / "platforms" / "libqxcb.so").is_file()
	assert not (pside / "QtWebEngineCore.abi3.so").exists()
	assert not (pside / "QtWidgets.abi3.so").exists()
	assert not (pside / "Qt" / "lib" / "libQt6WebEngineCore.so.6").exists()
	assert not (pside / "Qt" / "lib" / "libavcodec.so.61").exists()
	assert not (pside / "Qt" / "qml" / "QtWebEngine").exists()
	assert not (pside / "Qt" / "qml" / "QtQuick" / "Pdf").exists()
	assert not (pside / "Qt" / "qml" / "Qt" / "labs" / "wavefrontmesh").exists()
	assert not (pside / "Qt" / "plugins" / "multimedia").exists()
	assert not (pside / "designer").exists()
	assert not (pside / "qmlls").exists()
	assert not (pside / "include").exists()
	assert not (pside / "QtCore.pyi").exists()


def test_given_site_packages_path_when_pruning_then_accepts_direct_site_packages(tmp_path: Path):
	# given
	site = tmp_path / "site-packages"
	pside = _make_fake_pyside(site)

	# when
	result = subprocess.run(  # noqa: S603
		[str(PRUNE_SCRIPT), str(site)],
		check=False,
		capture_output=True,
		text=True,
	)

	# then
	assert result.returncode == 0, result.stderr or result.stdout
	assert (pside / "QtCore.abi3.so").is_file()
	assert not (pside / "QtWebEngineCore.abi3.so").exists()


def test_given_missing_pyside_when_pruning_then_exits_nonzero(tmp_path: Path):
	# given
	empty = tmp_path / "venv"
	(empty / "lib" / "python3.12" / "site-packages").mkdir(parents=True)

	# when
	result = subprocess.run(  # noqa: S603
		[str(PRUNE_SCRIPT), str(empty)],
		check=False,
		capture_output=True,
		text=True,
	)

	# then
	assert result.returncode != 0
	assert "PySide6 not found" in result.stderr
