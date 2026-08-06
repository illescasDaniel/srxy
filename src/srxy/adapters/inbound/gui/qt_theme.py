"""Qt Quick theme helpers so Windows dark mode stays consistent."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette


# Selection highlight used for ListView rows, ComboBox dropdown selection, etc.
_SELECTION_HIGHLIGHT = QColor("#1565c0")  # dark accessible blue
_SELECTION_HIGHLIGHT_TEXT = QColor("#ffffff")


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


def apply_qt_quick_theme(app: QCoreApplication):
	"""Pick Qt Quick Controls style per platform.

	- Windows: ``Universal`` (WinUI-like), falling back to ``Windows``.
	- macOS: ``macOS`` (native Aqua controls).
	- Other: Qt default (typically ``Fusion`` on Linux).

	Windows Universal defaults to Light unless ``QT_QUICK_CONTROLS_UNIVERSAL_THEME``
	is set (or ``Universal.theme`` is set in QML). We use the env var on Windows
	only so shared QML never imports Universal (which would force that style on
	macOS).
	"""
	if sys.platform == "win32":
		os.environ.setdefault("QT_QUICK_CONTROLS_UNIVERSAL_THEME", "System")
		if not _set_quick_style("Universal"):
			_set_quick_style("Windows")
		follow_system_color_scheme(app)
		_patch_fusion_selection_palette(app)
	elif sys.platform == "darwin":
		_set_quick_style("macOS")
		follow_system_color_scheme(app)
	else:
		follow_system_color_scheme(app)


__all__ = ["apply_qt_quick_theme", "follow_system_color_scheme"]
