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
from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette


if TYPE_CHECKING:
	from collections.abc import Sequence

# Selection highlight used for ListView rows, ComboBox dropdown selection, etc.
_SELECTION_HIGHLIGHT = QColor("#1565c0")  # dark accessible blue
_SELECTION_HIGHLIGHT_TEXT = QColor("#ffffff")

# Material named blue when no system accent can be detected.
_MATERIAL_ACCENT_FALLBACK = "Blue"

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
	"""Prefer the desktop light/dark scheme so Quick Controls match the OS."""
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


def _resolve_material_accent(app: QCoreApplication) -> str:
	return _accent_from_xdg_portal() or _accent_from_palette(app) or _MATERIAL_ACCENT_FALLBACK


def _apply_material_accent(app: QCoreApplication):
	"""Set Material accent from system tint, or Material Blue if detection fails."""
	os.environ.setdefault("QT_QUICK_CONTROLS_MATERIAL_ACCENT", _resolve_material_accent(app))


def apply_qt_quick_theme(app: QCoreApplication):
	"""Pick Qt Quick Controls style per platform.

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
	so desktop controls fit fixed window heights, and tries to pick a system
	accent colour for Material (XDG portal, then palette highlight, else
	``Blue``).
	"""
	if sys.platform == "win32":
		# Universal theme env still needed if we fall back to Universal.
		os.environ.setdefault("QT_QUICK_CONTROLS_UNIVERSAL_THEME", "System")
		if not _set_quick_style("FluentWinUI3"):
			if not _set_quick_style("Universal"):
				_set_quick_style("Windows")
		follow_system_color_scheme(app)
		_patch_fusion_selection_palette(app)
	elif sys.platform == "darwin":
		_set_quick_style("macOS")
		follow_system_color_scheme(app)
	else:
		# Dense: desktop-sized controls (Normal is touch-oriented and overflows our
		# fixed installer/GUI window heights, clipping footer actions like Next).
		os.environ.setdefault("QT_QUICK_CONTROLS_MATERIAL_THEME", "System")
		os.environ.setdefault("QT_QUICK_CONTROLS_MATERIAL_VARIANT", "Dense")
		_apply_material_accent(app)
		if not _set_quick_style("Material"):
			_set_quick_style("Fusion")
		follow_system_color_scheme(app)


__all__ = ["apply_qt_quick_theme", "follow_system_color_scheme"]
