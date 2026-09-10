"""Contract tests for the macOS offline PySide installer (no full Darwin build).

Mirrors tests/unit/test_windows_pyside_packaging.py — script layout / content so
CI can catch regressions without building a .app. A full build + smoke still
needs Darwin (see packaging/macos/README.md).
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[2]
_MACOS = _REPO / "packaging" / "macos"
_PRUNE = _MACOS / "prune-pyside.sh"


def _require_bash_script():
	if sys.platform == "win32":
		pytest.skip("macOS prune script is not run on Windows")
	if shutil.which("bash") is None:
		pytest.skip("bash not available")


def _touch(path: Path):
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_bytes(b"x")


def test_given_macos_offline_scripts_when_checking_layout_then_present():
	# given / when / then
	for path in (
		_MACOS / "build-offline.sh",
		_MACOS / "prune-pyside.sh",
		_MACOS / "smoke-offline.sh",
		_MACOS / "README.md",
	):
		assert path.is_file(), f"missing {path}"


def test_given_shared_qml_when_checking_then_macos_dialog_selector_present():
	# given / when / then — hatch must ship +macos so installed apps get sheet chrome
	controls = _REPO / "src" / "srxy" / "adapters" / "inbound" / "shared" / "qml" / "SrxyControls"
	assert (controls / "SrxyDialog.qml").is_file()
	assert (controls / "+macos" / "SrxyDialog.qml").is_file()
	qmldir = (controls / "qmldir").read_text(encoding="utf-8")
	assert "SrxyDialog 1.0 SrxyDialog.qml" in qmldir
	macos_dialog = (controls / "+macos" / "SrxyDialog.qml").read_text(encoding="utf-8")
	assert "Popup.Native" in macos_dialog
	assert "srxyUseNativeAlerts" in macos_dialog


def test_given_build_script_when_reading_then_pins_pyside_and_prunes():
	# given
	text = (_MACOS / "build-offline.sh").read_text(encoding="utf-8")

	# when / then
	assert 'uv pip install --python "$VENV_PY" "PySide6==6.11.1"' in text
	assert "prune-pyside.sh" in text
	assert "--no-deps" in text
	assert "smoke-offline.sh" in text or "smoke" in text.lower()
	assert "write_icns_from_png" in text  # macOS 26+ iconutil -c is broken


def test_given_prune_script_when_reading_then_keeps_macos_quick_style():
	# given
	text = (_MACOS / "prune-pyside.sh").read_text(encoding="utf-8")

	# when / then
	assert "QtQuickControls2MacOSStyleImpl.framework" in text
	assert "QtQuickControls2Fusion.framework" in text  # macOS Dialog imports Fusion
	assert "QtQuickDialogs2.framework" in text
	# styles/libqmacstyle is kept by omission (not listed under rm_rf plugins).
	assert '"$PLUGINS/styles"' not in text
	assert '"$PLUGINS/platformthemes"' in text  # deliberately removed


def test_given_smoke_script_when_reading_then_asserts_macos_quick_style():
	# given
	text = (_MACOS / "smoke-offline.sh").read_text(encoding="utf-8")

	# when / then — relocated copy + style assert (not just generic Controls load).
	assert "mktemp" in text or "STAGE_DIR" in text
	assert "prefer_macos_quick_controls_style" in text
	assert "apply_qt_quick_theme" in text
	assert 'style != "macOS"' in text or "expected Quick style macOS" in text


def test_given_macos_ci_workflow_when_checking_then_has_offline_job():
	# given
	workflow = (_REPO / ".github" / "workflows" / "macos-installer.yml").read_text(encoding="utf-8")

	# when / then
	assert "build-offline" in workflow
	assert "build-offline.sh" in workflow
	assert "smoke-offline.sh" in workflow


def test_given_fake_macos_pyside_tree_when_pruning_then_keeps_macos_style_paths(tmp_path: Path):
	# given
	_require_bash_script()
	site = tmp_path / "lib" / "python3.12" / "site-packages"
	pside = site / "PySide6"
	_touch(pside / "QtCore.abi3.so")
	_touch(pside / "QtGui.abi3.so")
	_touch(pside / "QtQml.abi3.so")
	_touch(pside / "QtQuick.abi3.so")
	_touch(pside / "QtQuickControls2.abi3.so")
	_touch(pside / "Qt" / "lib" / "QtCore.framework" / "QtCore")
	_touch(pside / "Qt" / "lib" / "QtQuickControls2MacOSStyleImpl.framework" / "QtQuickControls2MacOSStyleImpl")
	_touch(pside / "Qt" / "lib" / "QtQuickControls2Fusion.framework" / "QtQuickControls2Fusion")
	_touch(pside / "Qt" / "lib" / "QtWebEngineCore.framework" / "QtWebEngineCore")
	_touch(pside / "Qt" / "qml" / "QtQuick" / "Controls" / "qmldir")
	_touch(pside / "Qt" / "qml" / "QtQuick" / "Controls" / "macOS" / "qmldir")
	_touch(pside / "Qt" / "qml" / "QtQuick" / "Controls" / "macOS" / "libqtquickcontrols2macosstyleplugin.dylib")
	_touch(pside / "Qt" / "qml" / "QtQuick" / "Controls" / "Fusion" / "qmldir")
	_touch(pside / "Qt" / "qml" / "QtQuick" / "Dialogs" / "qmldir")
	_touch(pside / "Qt" / "qml" / "QtWebEngine" / "qmldir")
	_touch(pside / "Qt" / "plugins" / "platforms" / "libqcocoa.dylib")
	_touch(pside / "Qt" / "plugins" / "styles" / "libqmacstyle.dylib")
	_touch(pside / "Qt" / "plugins" / "multimedia" / "libffmpeg.dylib")
	assert _PRUNE.is_file()
	assert os.access(_PRUNE, os.X_OK) or (_PRUNE.stat().st_mode & stat.S_IXUSR)

	# when
	result = subprocess.run(  # noqa: S603
		[str(_PRUNE), str(tmp_path)],
		check=False,
		capture_output=True,
		text=True,
	)

	# then
	assert result.returncode == 0, result.stderr or result.stdout
	assert (pside / "Qt" / "lib" / "QtQuickControls2MacOSStyleImpl.framework").is_dir()
	assert (pside / "Qt" / "lib" / "QtQuickControls2Fusion.framework").is_dir()
	assert (pside / "Qt" / "qml" / "QtQuick" / "Controls" / "macOS" / "qmldir").is_file()
	assert (pside / "Qt" / "qml" / "QtQuick" / "Controls" / "Fusion" / "qmldir").is_file()
	assert (pside / "Qt" / "plugins" / "styles" / "libqmacstyle.dylib").is_file()
	assert (pside / "Qt" / "plugins" / "platforms" / "libqcocoa.dylib").is_file()
	assert not (pside / "Qt" / "lib" / "QtWebEngineCore.framework").exists()
	assert not (pside / "Qt" / "qml" / "QtWebEngine").exists()
	assert not (pside / "Qt" / "plugins" / "multimedia").exists()
