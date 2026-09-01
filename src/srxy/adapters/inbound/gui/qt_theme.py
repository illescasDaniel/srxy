"""Qt Quick theme helpers so Windows dark mode stays consistent.

Windows prefers FluentWinUI3 (theme experiment): unsupported controls such as
SplitView fall back to Fusion until Qt ships Fluent styles for them.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Property, QCoreApplication, QObject, Qt, Slot
from PySide6.QtGui import QColor, QGuiApplication, QPalette


if TYPE_CHECKING:
	from collections.abc import Sequence

# Selection highlight used for ListView rows, ComboBox dropdown selection, etc.
_SELECTION_HIGHLIGHT = QColor("#1565c0")  # dark accessible blue
_SELECTION_HIGHLIGHT_TEXT = QColor("#ffffff")

# Material named blue when no system accent can be detected.
_MATERIAL_ACCENT_FALLBACK = "Blue"

# Qt 6.11 Material defaults to M3 tonal surfaces (#fffbfe light / #1c1b1f dark),
# which read pinkish / purple-grey. Prefer flat neutrals; pick by light/dark so
# System theme is not locked to white.
_MATERIAL_BACKGROUND_LIGHT = "#ffffff"
_MATERIAL_BACKGROUND_DARK = "#303030"

# Qt Material accent names → approximate Material Design 500 hex (for AccentButton).
_MATERIAL_NAMED_HEX: dict[str, str] = {
	"Red": "#f44336",
	"Pink": "#e91e63",
	"Purple": "#9c27b0",
	"DeepPurple": "#673ab7",
	"Indigo": "#3f51b5",
	"Blue": "#2196f6",
	"LightBlue": "#03a9f4",
	"Cyan": "#00bcd4",
	"Teal": "#009688",
	"Green": "#4caf50",
	"LightGreen": "#8bc34a",
	"Lime": "#cddc39",
	"Yellow": "#ffeb3b",
	"Amber": "#ffc107",
	"Orange": "#ff9800",
	"DeepOrange": "#ff5722",
	"Brown": "#795548",
	"Grey": "#9e9e9e",
	"BlueGrey": "#607d8b",
}

_PORTAL_DEST = "org.freedesktop.portal.Desktop"
_PORTAL_PATH = "/org/freedesktop/portal/desktop"
_PORTAL_IFACE = "org.freedesktop.portal.Settings"
_PORTAL_NAMESPACE = "org.freedesktop.appearance"
_PORTAL_KEY = "accent-color"
_PORTAL_TIMEOUT_S = 0.5

# Three floats in portal/CLI text (gdbus / busctl / dbus-send).
_RGB_FLOATS_RE = re.compile(
	r"(-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)"
	r"(?:\s*,\s*|\s+)"
	r"(-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)"
	r"(?:\s*,\s*|\s+)"
	r"(-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)"
)


def _relative_luminance(color: QColor) -> float:
	"""WCAG 2.x relative luminance for an sRGB colour."""

	def _channel(value: int) -> float:
		s = value / 255.0
		if s <= 0.03928:
			return s / 12.92
		return ((s + 0.055) / 1.055) ** 2.4

	return 0.2126 * _channel(color.red()) + 0.7152 * _channel(color.green()) + 0.0722 * _channel(color.blue())


def _contrast_ratio(foreground: QColor, background: QColor) -> float:
	lighter = max(_relative_luminance(foreground), _relative_luminance(background))
	darker = min(_relative_luminance(foreground), _relative_luminance(background))
	return (lighter + 0.05) / (darker + 0.05)


def contrast_text_on(fill: QColor) -> QColor:
	"""Pick black or white text for WCAG contrast against ``fill``.

	Prefers white on dark/saturated fills (the CTA convention) whenever white
	still clears the AA 4.5:1 threshold; otherwise falls back to the
	higher-contrast colour. This avoids black text on mid-tones such as the
	Windows accent ``#0078d4``, where black wins by a hair but reads poorly.
	"""
	black = QColor("#000000")
	white = QColor("#ffffff")
	white_ratio = _contrast_ratio(white, fill)
	if white_ratio >= 4.5:
		return white
	black_ratio = _contrast_ratio(black, fill)
	return black if black_ratio > white_ratio else white


class SrxyTheme(QObject):
	"""QML-facing accent colours for primary CTAs (``AccentButton``)."""

	def __init__(self, accent: QColor, parent: QObject | None = None):
		super().__init__(parent)
		self._accent = QColor(accent)
		# Aqua default/highlighted push buttons always use white label text.
		# Qt's palette Highlight (e.g. ``#308cc6``) often fails white AA 4.5:1,
		# so WCAG contrast_text_on would pick black — wrong for the native bevel.
		if sys.platform == "darwin":
			self._on_accent = QColor("#ffffff")
		else:
			self._on_accent = contrast_text_on(self._accent)

	@Property(QColor, constant=True)
	def accent(self) -> QColor:
		return QColor(self._accent)

	@Property(QColor, constant=True)
	def onAccent(self) -> QColor:
		return QColor(self._on_accent)

	@Slot(QColor, result=QColor)
	def contrastOn(self, fill: QColor) -> QColor:
		return contrast_text_on(fill)


def _apply_button_accent_palette(app: QCoreApplication, accent: QColor):
	"""Pin ``QPalette.Accent`` (FluentWinUI3 highlighted-button fill) to ``accent``.

	FluentWinUI3 paints its highlighted/default button with ``palette.accent``
	rather than a style accent. Qt's platform theme usually populates it from the
	OS accent, but we set it explicitly so the native accent matches
	``SrxyTheme.accent`` — the same colour ``AccentButton.foreground`` computes
	WCAG contrast against. Material/Fusion/macOS ignore this role, so it is
	harmless there.
	"""
	if not isinstance(app, QGuiApplication):
		return
	accent_role = getattr(QPalette.ColorRole, "Accent", None)
	if accent_role is None:
		return
	try:
		palette = app.palette()
	except AttributeError:
		return
	for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
		palette.setColor(group, accent_role, accent)
	app.setPalette(palette)


def _patch_fusion_selection_palette(app: QCoreApplication):
	"""Pin the selection-highlight palette to a reliably accessible dark blue.

	Universal on Windows inherits the system accent colour for ``Highlight``, which
	can be a light pastel on some configurations.  This affects ListView rows,
	ComboBox dropdown selection, and other highlighted widgets.

	Accepts ``QCoreApplication`` so the signature matches
	``follow_system_color_scheme``; silently skips non-GUI instances that
	appear in test contexts (``QCoreApplication`` has no ``setPalette``).
	"""
	if not isinstance(app, QGuiApplication):
		return
	try:
		palette = app.palette()
	except AttributeError:
		return
	for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
		palette.setColor(group, QPalette.ColorRole.Highlight, _SELECTION_HIGHLIGHT)
		palette.setColor(group, QPalette.ColorRole.HighlightedText, _SELECTION_HIGHLIGHT_TEXT)
	app.setPalette(palette)


def follow_system_color_scheme(app: QCoreApplication):
	"""Prefer the desktop light/dark scheme so Quick Controls match the OS.

	Accepts ``QCoreApplication`` for call-site convenience; silently skips
	non-GUI instances that appear in test contexts (``QCoreApplication`` has
	no ``styleHints``).
	"""
	if not isinstance(app, QGuiApplication):
		return
	hints = app.styleHints()
	set_scheme = getattr(hints, "setColorScheme", None)
	if set_scheme is None:
		return
	color_scheme = getattr(Qt, "ColorScheme", None)
	if color_scheme is None:
		return
	current_getter = getattr(hints, "colorScheme", None)
	current = current_getter() if callable(current_getter) else current_getter
	unknown = getattr(color_scheme, "Unknown", None)
	if current is not None and current != unknown:
		set_scheme(current)
	elif unknown is not None:
		set_scheme(unknown)


def _set_quick_style(name: str) -> bool:
	try:
		from PySide6.QtQuickControls2 import QQuickStyle
	except ImportError:
		return False
	QQuickStyle.setStyle(name)
	style_name = getattr(QQuickStyle, "name", None)
	if callable(style_name):
		return style_name() == name
	return True


def prefer_native_file_dialogs():
	"""Route Qt Quick file/folder dialogs through the XDG desktop portal on Linux.

	Qt Quick's ``FolderDialog``/``FileDialog`` use a native dialog only when the
	platform theme provides one. On Linux the KDE/GNOME themes that Qt selects by
	default do not, so those dialogs fall back to the Qt Quick (non-native)
	implementation. Selecting the ``xdgdesktopportal`` platform theme (bundled
	with PySide6) serves file dialogs via ``org.freedesktop.portal.FileChooser``,
	which opens the desktop's native picker (e.g. KDE's).

	Must be called before ``QGuiApplication`` is constructed, since the platform
	theme is read once at startup. A user-set ``QT_QPA_PLATFORMTHEME`` is
	preserved, so this only fills in the missing default on Linux.
	"""
	if sys.platform.startswith("linux"):
		os.environ.setdefault("QT_QPA_PLATFORMTHEME", "xdgdesktopportal")


def _rgb01_to_hex(r: float, g: float, b: float) -> str | None:
	"""Convert sRGB [0,1] components to ``#rrggbb``, or ``None`` if unset/out of range."""
	if not all(0.0 <= c <= 1.0 for c in (r, g, b)):
		return None
	return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def _parse_rgb01_from_text(text: str) -> str | None:
	match = _RGB_FLOATS_RE.search(text)
	if match is None:
		return None
	try:
		r, g, b = (float(match.group(i)) for i in (1, 2, 3))
	except ValueError:
		return None
	return _rgb01_to_hex(r, g, b)


def _portal_cli_commands() -> list[list[str]]:
	"""Build candidate CLI invocations for XDG portal ``accent-color``.

	PySide6's ``QDBusArgument`` cannot reliably demarshal ``(ddd)`` structures
	(operator>> does not return extracted doubles to Python and can abort). Use
	session-bus CLI tools that are common on Linux desktops instead.
	"""
	commands: list[list[str]] = []
	if shutil.which("busctl"):
		commands.append(
			[
				"busctl",
				"--user",
				"call",
				_PORTAL_DEST,
				_PORTAL_PATH,
				_PORTAL_IFACE,
				"ReadOne",
				"ss",
				_PORTAL_NAMESPACE,
				_PORTAL_KEY,
			]
		)
	if shutil.which("gdbus"):
		commands.append(
			[
				"gdbus",
				"call",
				"--session",
				"--dest",
				_PORTAL_DEST,
				"--object-path",
				_PORTAL_PATH,
				"--method",
				f"{_PORTAL_IFACE}.ReadOne",
				_PORTAL_NAMESPACE,
				_PORTAL_KEY,
			]
		)
	if shutil.which("dbus-send"):
		commands.append(
			[
				"dbus-send",
				"--session",
				"--print-reply",
				f"--dest={_PORTAL_DEST}",
				_PORTAL_PATH,
				f"{_PORTAL_IFACE}.ReadOne",
				f"string:{_PORTAL_NAMESPACE}",
				f"string:{_PORTAL_KEY}",
			]
		)
	return commands


def _run_portal_command(command: Sequence[str]) -> str | None:
	try:
		completed = subprocess.run(  # noqa: S603 — fixed session-bus CLI argv from shutil.which
			list(command),
			check=False,
			capture_output=True,
			text=True,
			timeout=_PORTAL_TIMEOUT_S,
		)
	except (OSError, subprocess.TimeoutExpired):
		return None
	if completed.returncode != 0:
		return None
	return completed.stdout or None


def _accent_from_xdg_portal() -> str | None:
	"""Read ``org.freedesktop.appearance`` / ``accent-color`` via the session bus."""
	for command in _portal_cli_commands():
		stdout = _run_portal_command(command)
		if not stdout:
			continue
		hex_color = _parse_rgb01_from_text(stdout)
		if hex_color is not None:
			return hex_color
	return None


def _is_usable_accent(color: QColor) -> bool:
	"""Reject near-gray / near-black / near-white palette highlights."""
	r = color.red()
	g = color.green()
	b = color.blue()
	mx = max(r, g, b)
	mn = min(r, g, b)
	if mx == 0:
		return False
	if (mx - mn) < 30:
		return False
	if mn > 230:
		return False
	if mx < 40:
		return False
	return True


def _accent_from_palette(app: QCoreApplication) -> str | None:
	if not isinstance(app, QGuiApplication):
		return None
	try:
		color = app.palette().color(QPalette.ColorRole.Highlight)
	except AttributeError:
		return None
	if not _is_usable_accent(color):
		return None
	return color.name(QColor.NameFormat.HexRgb)


def _material_accent_to_color(value: str) -> QColor:
	"""Map Material env accent (``#rrggbb`` or named) to a ``QColor``."""
	stripped = value.strip()
	if stripped.startswith("#"):
		color = QColor(stripped)
		if color.isValid():
			return color
	named = _MATERIAL_NAMED_HEX.get(stripped)
	if named is not None:
		return QColor(named)
	return QColor(_SELECTION_HIGHLIGHT)


def _resolve_material_accent(app: QCoreApplication) -> str:
	return _accent_from_xdg_portal() or _accent_from_palette(app) or _MATERIAL_ACCENT_FALLBACK


def _apply_material_accent(app: QCoreApplication):
	"""Set Material accent from system tint, or Material Blue if detection fails."""
	os.environ.setdefault("QT_QUICK_CONTROLS_MATERIAL_ACCENT", _resolve_material_accent(app))


def _is_dark_color_scheme(app: QCoreApplication) -> bool:
	"""True when the app / desktop colour scheme is dark.

	Prefers ``QStyleHints.colorScheme`` after ``follow_system_color_scheme``;
	falls back to window-palette lightness when the scheme is unknown (common
	under offscreen / headless tests).
	"""
	if not isinstance(app, QGuiApplication):
		return False
	hints = app.styleHints()
	color_scheme = getattr(Qt, "ColorScheme", None)
	if color_scheme is not None:
		current_getter = getattr(hints, "colorScheme", None)
		current = current_getter() if callable(current_getter) else current_getter
		dark = getattr(color_scheme, "Dark", None)
		light = getattr(color_scheme, "Light", None)
		if current is not None and current == dark:
			return True
		if current is not None and current == light:
			return False
	try:
		window = app.palette().color(QPalette.ColorRole.Window)
	except AttributeError:
		return False
	return window.lightnessF() < 0.5


def _resolve_material_background(app: QCoreApplication) -> str:
	if _is_dark_color_scheme(app):
		return _MATERIAL_BACKGROUND_DARK
	return _MATERIAL_BACKGROUND_LIGHT


def _apply_material_background(app: QCoreApplication):
	"""Neutralise Material's pinkish M3 surface using the active light/dark scheme."""
	os.environ.setdefault(
		"QT_QUICK_CONTROLS_MATERIAL_BACKGROUND",
		_resolve_material_background(app),
	)


def _palette_accent_or_fallback(app: QCoreApplication) -> QColor:
	hex_color = _accent_from_palette(app)
	if hex_color is not None:
		return QColor(hex_color)
	return QColor(_SELECTION_HIGHLIGHT)


def resolve_button_accent(app: QCoreApplication) -> QColor:
	"""System accent for primary CTAs (before Windows selection-palette patch)."""
	if sys.platform in {"win32", "darwin"}:
		return _palette_accent_or_fallback(app)
	raw = os.environ.get("QT_QUICK_CONTROLS_MATERIAL_ACCENT") or _resolve_material_accent(app)
	return _material_accent_to_color(raw)


def shared_qml_import_path() -> str:
	"""Directory containing the ``SrxyControls`` QML module (AccentButton, etc.)."""
	return str(Path(__file__).resolve().parent.parent / "shared" / "qml")


def apply_qt_quick_theme(app: QCoreApplication) -> SrxyTheme:
	"""Pick Qt Quick Controls style per platform and return accent theme for QML.

	- Windows: ``FluentWinUI3``, then ``Universal``, then ``Windows``.
	- macOS: ``macOS`` (native Aqua controls).
	- Linux / other: ``Material`` (Dense), falling back to ``Fusion``.

	FluentWinUI3 follows the OS/palette (no ``*_THEME`` env). It is still a
	theme experiment: controls Fluent does not style yet (notably ``SplitView``
	in the GUI results pane) render with Fusion until Qt adds support.

	Universal and Material default to Light unless their ``*_THEME`` env vars are
	set (or the matching attached property is set in QML). We set those env vars
	in Python only so shared QML never imports FluentWinUI3/Universal/Material
	(which would force that style on macOS). Linux also sets Material ``Dense``
	so desktop controls fit fixed window heights, picks a system accent colour
	for Material (XDG portal, then palette highlight, else ``Blue``), and
	overrides Material's pinkish M3 default background with a flat neutral
	(``#ffffff`` light / ``#303030`` dark) from the active colour scheme.

	Returns a ``SrxyTheme`` with ``accent`` / ``onAccent`` for ``AccentButton``.
	On Windows, accent is read from the palette *before* the ListView selection
	highlight is patched to a fixed blue.
	"""
	if sys.platform == "win32":
		# Universal theme env still needed if we fall back to Universal.
		os.environ.setdefault("QT_QUICK_CONTROLS_UNIVERSAL_THEME", "System")
		if not _set_quick_style("FluentWinUI3"):
			if not _set_quick_style("Universal"):
				_set_quick_style("Windows")
		follow_system_color_scheme(app)
		button_accent = resolve_button_accent(app)
		_patch_fusion_selection_palette(app)
	elif sys.platform == "darwin":
		_set_quick_style("macOS")
		follow_system_color_scheme(app)
		button_accent = resolve_button_accent(app)
	else:
		# Dense: desktop-sized controls (Normal is touch-oriented and overflows our
		# fixed installer/GUI window heights, clipping footer actions like Next).
		os.environ.setdefault("QT_QUICK_CONTROLS_MATERIAL_THEME", "System")
		os.environ.setdefault("QT_QUICK_CONTROLS_MATERIAL_VARIANT", "Dense")
		# Scheme before background: MATERIAL_BACKGROUND is a single colour and
		# must match light vs dark (a fixed #ffffff would lock dark mode to white).
		follow_system_color_scheme(app)
		_apply_material_accent(app)
		_apply_material_background(app)
		if not _set_quick_style("Material"):
			_set_quick_style("Fusion")
		button_accent = resolve_button_accent(app)

	_apply_button_accent_palette(app, button_accent)
	return SrxyTheme(button_accent)


__all__ = [
	"SrxyTheme",
	"apply_qt_quick_theme",
	"contrast_text_on",
	"follow_system_color_scheme",
	"prefer_native_file_dialogs",
	"resolve_button_accent",
	"shared_qml_import_path",
]
