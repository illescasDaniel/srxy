"""Tiny QObject that drives splash copy and status during GUI cold-start."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, metadata, version

from PySide6.QtCore import Property, QObject, Signal

from srxy.application.branding import APP_NAME, AUTHOR


def package_version_label() -> str:
	try:
		return version("srxy")
	except PackageNotFoundError:
		return "unknown"


def package_author_label() -> str:
	"""Prefer installed package metadata; fall back to branding constant."""
	try:
		meta = metadata("srxy")
	except PackageNotFoundError:
		return AUTHOR
	author = (meta.get("Author") or "").strip()
	if author:
		return author
	raw = (meta.get("Author-email") or "").strip()
	if raw:
		name = raw.split("<", 1)[0].strip()
		if name:
			return name
	return AUTHOR


class SplashBridge(QObject):
	"""Context property for Splash.qml — static labels plus a live status line."""

	statusChanged = Signal()

	def __init__(self, parent: QObject | None = None):
		super().__init__(parent)
		self._app_name = APP_NAME
		self._author = package_author_label()
		self._version = package_version_label()
		self._status = "Loading…"

	@Property(str, constant=True)
	def appName(self) -> str:
		return self._app_name

	@Property(str, constant=True)
	def author(self) -> str:
		return self._author

	@Property(str, constant=True)
	def version(self) -> str:
		return self._version

	@Property(str, notify=statusChanged)
	def status(self) -> str:
		return self._status

	def set_status(self, text: str):
		if text == self._status:
			return
		self._status = text
		self.statusChanged.emit()


__all__ = [
	"SplashBridge",
	"package_author_label",
	"package_version_label",
]
