from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QColor, QGuiApplication, QPalette

from srxy.adapters.inbound.gui import qt_theme


pytestmark = pytest.mark.unit


@pytest.fixture
def clear_material_accent(monkeypatch: pytest.MonkeyPatch):
	monkeypatch.delenv("QT_QUICK_CONTROLS_MATERIAL_ACCENT", raising=False)


def test_given_valid_rgb01_when_converting_then_returns_hex():
	# given
	r, g, b = 0.23921568691730499, 0.68235296010971069, 0.91372549533843994

	# when
	result = qt_theme._rgb01_to_hex(r, g, b)

	# then
	assert result == "#3daee9"


def test_given_out_of_range_rgb01_when_converting_then_returns_none():
	# given / when / then
	assert qt_theme._rgb01_to_hex(-0.1, 0.5, 0.5) is None
	assert qt_theme._rgb01_to_hex(0.5, 1.1, 0.5) is None


def test_given_busctl_stdout_when_parsing_then_returns_hex():
	# given
	text = "v (ddd) 0.239216 0.682353 0.913725\n"

	# when
	result = qt_theme._parse_rgb01_from_text(text)

	# then
	assert result == "#3daee9"


def test_given_gdbus_stdout_when_parsing_then_returns_hex():
	# given
	text = "(<(0.23921568691730499, 0.68235296010971069, 0.91372549533843994)>,)\n"

	# when
	result = qt_theme._parse_rgb01_from_text(text)

	# then
	assert result == "#3daee9"


def test_given_out_of_range_portal_rgb_when_parsing_then_returns_none():
	# given
	text = "v (ddd) 1.5 0.2 0.3\n"

	# when
	result = qt_theme._parse_rgb01_from_text(text)

	# then
	assert result is None


def test_given_portal_accent_when_applying_material_accent_then_sets_hex_env(
	clear_material_accent: None,
):
	# given
	app = MagicMock(spec=QCoreApplication)

	# when
	with (
		patch.object(qt_theme, "_accent_from_xdg_portal", return_value="#3daee9"),
		patch.object(qt_theme, "_accent_from_palette", return_value="#ff0000"),
	):
		qt_theme._apply_material_accent(app)

	# then
	assert os.environ["QT_QUICK_CONTROLS_MATERIAL_ACCENT"] == "#3daee9"


def test_given_portal_failure_and_palette_accent_when_applying_then_sets_palette_hex(
	clear_material_accent: None,
):
	# given
	app = MagicMock(spec=QCoreApplication)

	# when
	with (
		patch.object(qt_theme, "_accent_from_xdg_portal", return_value=None),
		patch.object(qt_theme, "_accent_from_palette", return_value="#c62828"),
	):
		qt_theme._apply_material_accent(app)

	# then
	assert os.environ["QT_QUICK_CONTROLS_MATERIAL_ACCENT"] == "#c62828"


def test_given_all_detection_failures_when_applying_then_sets_material_blue(
	clear_material_accent: None,
):
	# given
	app = MagicMock(spec=QCoreApplication)

	# when
	with (
		patch.object(qt_theme, "_accent_from_xdg_portal", return_value=None),
		patch.object(qt_theme, "_accent_from_palette", return_value=None),
	):
		qt_theme._apply_material_accent(app)

	# then
	assert os.environ["QT_QUICK_CONTROLS_MATERIAL_ACCENT"] == "Blue"


def test_given_preset_material_accent_when_applying_then_preserves_env(
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setenv("QT_QUICK_CONTROLS_MATERIAL_ACCENT", "Teal")
	app = MagicMock(spec=QCoreApplication)

	# when
	with (
		patch.object(qt_theme, "_accent_from_xdg_portal", return_value="#3daee9"),
		patch.object(qt_theme, "_accent_from_palette", return_value="#c62828"),
	):
		qt_theme._apply_material_accent(app)

	# then
	assert os.environ["QT_QUICK_CONTROLS_MATERIAL_ACCENT"] == "Teal"


def test_given_gray_highlight_when_reading_palette_then_returns_none():
	# given
	app = MagicMock(spec=QGuiApplication)
	palette = QPalette()
	palette.setColor(QPalette.ColorRole.Highlight, QColor("#808080"))
	app.palette.return_value = palette

	# when
	result = qt_theme._accent_from_palette(app)

	# then
	assert result is None


def test_given_vivid_highlight_when_reading_palette_then_returns_hex():
	# given
	app = MagicMock(spec=QGuiApplication)
	palette = QPalette()
	palette.setColor(QPalette.ColorRole.Highlight, QColor("#3daee9"))
	app.palette.return_value = palette

	# when
	result = qt_theme._accent_from_palette(app)

	# then
	assert result == "#3daee9"


def test_given_portal_command_success_when_reading_portal_then_returns_hex():
	# given
	commands = [["busctl", "fake"]]
	stdout = "v (ddd) 0.239216 0.682353 0.913725\n"

	# when
	with (
		patch.object(qt_theme, "_portal_cli_commands", return_value=commands),
		patch.object(qt_theme, "_run_portal_command", return_value=stdout) as run,
	):
		result = qt_theme._accent_from_xdg_portal()

	# then
	assert result == "#3daee9"
	run.assert_called_once_with(commands[0])
