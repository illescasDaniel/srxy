"""PySide6 desktop adapter (Qt clipboard + OS open)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QGuiApplication

from srxy.adapters.outbound.os.desktop import open_path, reveal_path


class QtDesktopAdapter:
	"""DesktopPort for the GUI — Qt clipboard, archive-aware OS open."""

	def open_path(self, path: Path):
		open_path(path)

	def reveal_path(self, path: Path):
		reveal_path(path)

	def copy_text(self, text: str):
		QGuiApplication.clipboard().setText(text)
