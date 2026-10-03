"""OS file-manager drops onto the GUI path field (Finder / Explorer / …).

QML ``DropArea`` alone is unreliable on macOS: native-looking controls and
GroupBox/ScrollView stacking often mean Finder never receives an accepted
drag (no green ``+`` cursor). A window-level event filter accepts
``text/uri-list`` drags over the Where-to-search strip and forwards them to
``SearchController.handleDroppedPathUrls``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QObject, QPointF
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtQuick import QQuickItem


if TYPE_CHECKING:
	from srxy.adapters.inbound.gui.controller import SearchController


_DEFAULT_TARGET = "pathDropTarget"


class PathDropWindowFilter(QObject):
	"""Accept external file drags over ``pathDropTarget`` on a QQuick window."""

	def __init__(
		self,
		controller: SearchController,
		window: QObject,
		*,
		target_name: str = _DEFAULT_TARGET,
	):
		# Parent to the real controller QObject — unit tests may pass a mock window.
		super().__init__(controller)
		self._controller = controller
		self._window = window
		self._target_name = target_name
		window.installEventFilter(self)

	def _target(self) -> QQuickItem | None:
		item = self._window.findChild(QQuickItem, self._target_name)
		return item if isinstance(item, QQuickItem) else None

	def _in_zone(self, scene_pos: QPointF) -> bool:
		target = self._target()
		if target is None or not target.isVisible():
			return False
		if float(target.width()) <= 0.0 or float(target.height()) <= 0.0:
			return False
		local = target.mapFromScene(scene_pos)
		return bool(target.contains(local))

	def _set_hover(self, active: bool):
		self._controller.set_path_drop_hover(active)

	def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
		if watched is not self._window:
			return False
		etype = event.type()
		if etype in (QEvent.Type.DragEnter, QEvent.Type.DragMove) and isinstance(
			event, (QDragEnterEvent, QDragMoveEvent)
		):
			mime = event.mimeData()
			if mime is None or not mime.hasUrls():
				return False
			if self._in_zone(QPointF(event.position())):
				event.acceptProposedAction()
				self._set_hover(True)
				return True
			if etype == QEvent.Type.DragMove:
				self._set_hover(False)
			return False
		if etype == QEvent.Type.DragLeave:
			self._set_hover(False)
			return False
		if etype == QEvent.Type.Drop and isinstance(event, QDropEvent):
			mime = event.mimeData()
			if mime is None or not mime.hasUrls():
				return False
			if self._in_zone(QPointF(event.position())):
				urls = [url.toString() for url in mime.urls()]
				self._controller.handleDroppedPathUrls(urls)
				self._set_hover(False)
				event.acceptProposedAction()
				return True
			self._set_hover(False)
			return False
		return False


def install_path_drop_filter(
	controller: SearchController,
	window: QObject,
	*,
	target_name: str = _DEFAULT_TARGET,
) -> PathDropWindowFilter:
	"""Install a path-drop filter on ``window``; filter is parented to ``controller``."""
	return PathDropWindowFilter(controller, window, target_name=target_name)


__all__ = ["PathDropWindowFilter", "install_path_drop_filter"]
