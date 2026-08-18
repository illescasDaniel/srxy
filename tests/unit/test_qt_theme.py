from __future__ import annotations

import os
from pathlib import Path
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
	result = qt_theme._rgb01_to_hex(r, g, b)  # pyright: ignore[reportPrivateUsage]

	# then
	assert result == "#3daee9"


def test_given_out_of_range_rgb01_when_converting_then_returns_none():
	# given / when / then
	assert qt_theme._rgb01_to_hex(-0.1, 0.5, 0.5) is None  # pyright: ignore[reportPrivateUsage]
	assert qt_theme._rgb01_to_hex(0.5, 1.1, 0.5) is None  # pyright: ignore[reportPrivateUsage]


def test_given_busctl_stdout_when_parsing_then_returns_hex():
	# given
	text = "v (ddd) 0.239216 0.682353 0.913725\n"

	# when
	result = qt_theme._parse_rgb01_from_text(text)  # pyright: ignore[reportPrivateUsage]

	# then
	assert result == "#3daee9"


def test_given_gdbus_stdout_when_parsing_then_returns_hex():
	# given
	text = "(<(0.23921568691730499, 0.68235296010971069, 0.91372549533843994)>,)\n"

	# when
	result = qt_theme._parse_rgb01_from_text(text)  # pyright: ignore[reportPrivateUsage]

	# then
	assert result == "#3daee9"


def test_given_out_of_range_portal_rgb_when_parsing_then_returns_none():
	# given
	text = "v (ddd) 1.5 0.2 0.3\n"

	# when
	result = qt_theme._parse_rgb01_from_text(text)  # pyright: ignore[reportPrivateUsage]

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
		qt_theme._apply_material_accent(app)  # pyright: ignore[reportPrivateUsage]

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
		qt_theme._apply_material_accent(app)  # pyright: ignore[reportPrivateUsage]

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
		qt_theme._apply_material_accent(app)  # pyright: ignore[reportPrivateUsage]

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
		qt_theme._apply_material_accent(app)  # pyright: ignore[reportPrivateUsage]

	# then
	assert os.environ["QT_QUICK_CONTROLS_MATERIAL_ACCENT"] == "Teal"


def test_given_gray_highlight_when_reading_palette_then_returns_none():
	# given
	app = MagicMock(spec=QGuiApplication)
	palette = QPalette()
	palette.setColor(QPalette.ColorRole.Highlight, QColor("#808080"))
	app.palette.return_value = palette

	# when
	result = qt_theme._accent_from_palette(app)  # pyright: ignore[reportPrivateUsage]

	# then
	assert result is None


def test_given_vivid_highlight_when_reading_palette_then_returns_hex():
	# given
	app = MagicMock(spec=QGuiApplication)
	palette = QPalette()
	palette.setColor(QPalette.ColorRole.Highlight, QColor("#3daee9"))
	app.palette.return_value = palette

	# when
	result = qt_theme._accent_from_palette(app)  # pyright: ignore[reportPrivateUsage]

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
		result = qt_theme._accent_from_xdg_portal()  # pyright: ignore[reportPrivateUsage]

	# then
	assert result == "#3daee9"
	run.assert_called_once_with(commands[0])


def _windows_theme_app() -> MagicMock:
	# follow_system_color_scheme / palette patch are mocked in these tests.
	return MagicMock(spec=QCoreApplication)


def test_given_fluent_available_when_applying_windows_theme_then_uses_fluent_only(
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setattr(qt_theme.sys, "platform", "win32")
	monkeypatch.delenv("QT_QUICK_CONTROLS_UNIVERSAL_THEME", raising=False)
	app = _windows_theme_app()
	set_style = MagicMock(return_value=True)

	# when
	with (
		patch.object(qt_theme, "_set_quick_style", set_style),
		patch.object(qt_theme, "follow_system_color_scheme") as follow,
		patch.object(qt_theme, "_patch_fusion_selection_palette") as patch_palette,
		patch.object(qt_theme, "resolve_button_accent", return_value=QColor("#1565c0")),
	):
		qt_theme.apply_qt_quick_theme(app)

	# then
	set_style.assert_called_once_with("FluentWinUI3")
	assert os.environ["QT_QUICK_CONTROLS_UNIVERSAL_THEME"] == "System"
	follow.assert_called_once_with(app)
	patch_palette.assert_called_once_with(app)


def test_given_fluent_missing_when_applying_windows_theme_then_falls_back_to_universal(
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setattr(qt_theme.sys, "platform", "win32")
	monkeypatch.delenv("QT_QUICK_CONTROLS_UNIVERSAL_THEME", raising=False)
	app = _windows_theme_app()

	def _set_style(name: str) -> bool:
		return name == "Universal"

	set_style = MagicMock(side_effect=_set_style)

	# when
	with (
		patch.object(qt_theme, "_set_quick_style", set_style),
		patch.object(qt_theme, "follow_system_color_scheme"),
		patch.object(qt_theme, "_patch_fusion_selection_palette"),
		patch.object(qt_theme, "resolve_button_accent", return_value=QColor("#1565c0")),
	):
		qt_theme.apply_qt_quick_theme(app)

	# then
	assert [call.args[0] for call in set_style.call_args_list] == [
		"FluentWinUI3",
		"Universal",
	]
	assert os.environ["QT_QUICK_CONTROLS_UNIVERSAL_THEME"] == "System"


def test_given_fluent_and_universal_missing_when_applying_windows_theme_then_uses_windows(
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setattr(qt_theme.sys, "platform", "win32")
	monkeypatch.delenv("QT_QUICK_CONTROLS_UNIVERSAL_THEME", raising=False)
	app = _windows_theme_app()
	set_style = MagicMock(return_value=False)

	# when
	with (
		patch.object(qt_theme, "_set_quick_style", set_style),
		patch.object(qt_theme, "follow_system_color_scheme"),
		patch.object(qt_theme, "_patch_fusion_selection_palette"),
		patch.object(qt_theme, "resolve_button_accent", return_value=QColor("#1565c0")),
	):
		qt_theme.apply_qt_quick_theme(app)

	# then
	assert [call.args[0] for call in set_style.call_args_list] == [
		"FluentWinUI3",
		"Universal",
		"Windows",
	]
	assert os.environ["QT_QUICK_CONTROLS_UNIVERSAL_THEME"] == "System"


def test_given_preset_universal_theme_when_applying_windows_theme_then_preserves_env(
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setattr(qt_theme.sys, "platform", "win32")
	monkeypatch.setenv("QT_QUICK_CONTROLS_UNIVERSAL_THEME", "Dark")
	app = _windows_theme_app()

	# when
	with (
		patch.object(qt_theme, "_set_quick_style", return_value=True),
		patch.object(qt_theme, "follow_system_color_scheme"),
		patch.object(qt_theme, "_patch_fusion_selection_palette"),
		patch.object(qt_theme, "resolve_button_accent", return_value=QColor("#1565c0")),
	):
		theme = qt_theme.apply_qt_quick_theme(app)

	# then
	assert os.environ["QT_QUICK_CONTROLS_UNIVERSAL_THEME"] == "Dark"
	assert isinstance(theme, qt_theme.SrxyTheme)


def test_given_dark_blue_fill_when_contrast_text_then_returns_white():
	# given / when
	result = qt_theme.contrast_text_on(QColor("#1565c0"))

	# then
	assert result.name(QColor.NameFormat.HexRgb) == "#ffffff"


def test_given_windows_accent_fill_when_contrast_text_then_returns_white():
	# given / when
	result = qt_theme.contrast_text_on(QColor("#0078d4"))

	# then
	assert result.name(QColor.NameFormat.HexRgb) == "#ffffff"


def test_given_light_yellow_fill_when_contrast_text_then_returns_black():
	# given / when
	result = qt_theme.contrast_text_on(QColor("#ffeb3b"))

	# then
	assert result.name(QColor.NameFormat.HexRgb) == "#000000"


def test_given_pastel_accent_when_contrast_text_then_returns_black():
	# given / when
	result = qt_theme.contrast_text_on(QColor("#90caf9"))

	# then
	assert result.name(QColor.NameFormat.HexRgb) == "#000000"


def test_given_material_named_blue_when_mapping_then_returns_hex_color():
	# given / when
	result = qt_theme._material_accent_to_color("Blue")  # pyright: ignore[reportPrivateUsage]

	# then
	assert result.name(QColor.NameFormat.HexRgb) == "#2196f6"


def test_given_windows_theme_when_applying_then_resolves_accent_before_selection_patch(
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setattr(qt_theme.sys, "platform", "win32")
	monkeypatch.delenv("QT_QUICK_CONTROLS_UNIVERSAL_THEME", raising=False)
	app = _windows_theme_app()
	order: list[str] = []

	def _resolve(_app: object) -> QColor:
		order.append("resolve")
		return QColor("#3daee9")

	def _patch(_app: object):
		order.append("patch")

	# when
	with (
		patch.object(qt_theme, "_set_quick_style", return_value=True),
		patch.object(qt_theme, "follow_system_color_scheme"),
		patch.object(qt_theme, "resolve_button_accent", side_effect=_resolve),
		patch.object(qt_theme, "_patch_fusion_selection_palette", side_effect=_patch),
	):
		theme = qt_theme.apply_qt_quick_theme(app)

	# then
	assert order == ["resolve", "patch"]
	assert theme.accent.name(QColor.NameFormat.HexRgb) == "#3daee9"
	assert theme.onAccent.name(QColor.NameFormat.HexRgb) == "#000000"


def test_given_shared_qml_path_when_resolved_then_contains_srxy_controls():
	# given / when
	path = qt_theme.shared_qml_import_path()

	# then
	assert (Path(path) / "SrxyControls" / "AccentButton.qml").is_file()
	assert (Path(path) / "SrxyControls" / "qmldir").is_file()
