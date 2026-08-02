from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication, QIcon

from srxy.adapters.inbound.gui.app_icon import (
	apply_app_icon,
	apply_desktop_file_name,
	desktop_file_available,
)
from srxy.resources.icons import app_icon_path, available_icon_sizes


pytestmark = pytest.mark.unit


def test_given_packaged_icons_when_resolving_then_files_exist():
	# given / when
	sizes = available_icon_sizes()
	primary = app_icon_path()

	# then
	assert primary.is_file()
	assert 256 in sizes
	assert app_icon_path(size=256).is_file()


def test_given_qt_app_when_applying_icon_then_window_icon_is_set(qapp: QGuiApplication):
	# given
	assert isinstance(qapp, QGuiApplication)

	# when
	apply_app_icon(qapp)

	# then
	icon = qapp.windowIcon()
	assert isinstance(icon, QIcon)
	assert not icon.isNull()


def test_given_missing_desktop_file_when_applying_name_then_skips(
	qapp: QGuiApplication,
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
	monkeypatch.setenv("XDG_DATA_DIRS", str(tmp_path / "empty"))
	assert desktop_file_available("srxy-installer") is False
	qapp.setDesktopFileName("")

	# when
	apply_desktop_file_name(qapp, "srxy-installer")

	# then
	assert qapp.desktopFileName() == ""


def test_given_desktop_file_when_applying_name_then_sets_it(
	qapp: QGuiApplication,
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	apps = tmp_path / "share" / "applications"
	apps.mkdir(parents=True)
	(apps / "srxy-installer.desktop").write_text("[Desktop Entry]\nName=srxy\n", encoding="utf-8")
	monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
	monkeypatch.setenv("XDG_DATA_DIRS", str(tmp_path / "empty"))
	qapp.setDesktopFileName("")

	# when
	apply_desktop_file_name(qapp, "srxy-installer")

	# then
	assert qapp.desktopFileName() == "srxy-installer"
