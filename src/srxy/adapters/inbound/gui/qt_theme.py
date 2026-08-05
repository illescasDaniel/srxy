"""Qt Quick theme helpers so Windows dark mode stays consistent."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication


def follow_system_color_scheme(app: QGuiApplication):
	"""Prefer the desktop light/dark scheme so Quick Controls match the OS."""
	hints = app.styleHints()
	set_scheme = getattr(hints, "setColorScheme", None)
	if set_scheme is None:
		return
	color_scheme = getattr(Qt, "ColorScheme", None)
	if color_scheme is None:
		return
	unknown = getattr(color_scheme, "Unknown", None)
	if unknown is not None:
		set_scheme(unknown)


def apply_qt_quick_theme(app: QGuiApplication):
	"""Use Fusion on Windows so dark/light palettes apply to Controls + Dialogs.

	The native Windows Quick style keeps light control chrome while
	``ApplicationWindow`` may already follow a dark system palette, which
	produces illegible mixed themes (white-on-white About text, etc.).
	"""
	if sys.platform == "win32":
		try:
			from PySide6.QtQuickControls2 import QQuickStyle
		except ImportError:
			pass
		else:
			QQuickStyle.setStyle("Fusion")
	follow_system_color_scheme(app)


__all__ = ["apply_qt_quick_theme", "follow_system_color_scheme"]
