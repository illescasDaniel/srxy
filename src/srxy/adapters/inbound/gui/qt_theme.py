"""Qt Quick theme helpers so Windows dark mode stays consistent."""

from __future__ import annotations

import sys

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette


# Selection highlight used for ListView rows, ComboBox dropdown selection, etc.
# Checkbox indicator colours are handled directly in Main.qml (StyledCheckBox)
# so they are not affected by this palette patch.
_SELECTION_HIGHLIGHT = QColor("#1565c0")  # dark accessible blue
_SELECTION_HIGHLIGHT_TEXT = QColor("#ffffff")


def _patch_fusion_selection_palette(app: QCoreApplication):
	"""Pin the selection-highlight palette to a reliably accessible dark blue.

	Fusion on Windows inherits the system accent colour for ``Highlight``, which
	can be a light pastel on some configurations.  This affects ListView rows,
	ComboBox dropdown selection, and other highlighted widgets.  CheckBox
	indicator colours are now handled by QML (``StyledCheckBox`` in Main.qml)
	and are unaffected by this palette change.

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


def apply_qt_quick_theme(app: QCoreApplication):
	"""Prefer native controls and follow the OS light/dark scheme."""
	using_fusion = False
	if sys.platform == "win32":
		try:
			from PySide6.QtQuickControls2 import QQuickStyle
		except ImportError:
			pass
		else:
			# Prefer Universal (WinUI-like) when present, then fall back to Windows.
			try:
				QQuickStyle.setStyle("Universal")
			except Exception:
				QQuickStyle.setStyle("Windows")
			else:
				if getattr(QQuickStyle, "name", lambda: "")() != "Universal":
					QQuickStyle.setStyle("Windows")
		follow_system_color_scheme(app)
	else:
		using_fusion = True
		follow_system_color_scheme(app)
	if using_fusion:
		_patch_fusion_selection_palette(app)


__all__ = ["apply_qt_quick_theme", "follow_system_color_scheme"]
