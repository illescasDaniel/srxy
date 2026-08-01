"""Qt list models for search results and in-file matches."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, QPersistentModelIndex, Qt, Slot

from srxy.adapters.inbound.cli.cli import format_score_percent, iter_grouped_line_displays, match_labels
from srxy.domain.models import FileSearchResult


_EMPTY_INDEX = QModelIndex()


class ResultsModel(QAbstractListModel):
	ScoreRole = Qt.ItemDataRole.UserRole + 1
	PathRole = Qt.ItemDataRole.UserRole + 2
	LabelsRole = Qt.ItemDataRole.UserRole + 3

	def __init__(self, parent: Any = None):
		super().__init__(parent)
		self._results: list[FileSearchResult] = []
		self._limit: int | None = None
		self._threshold = 0.35
		self._semantic_image_threshold = 0.25
		self._transcribe_threshold = 0.35

	def set_thresholds(self, *, threshold: float, semantic_image_threshold: float, transcribe_threshold: float):
		self._threshold = threshold
		self._semantic_image_threshold = semantic_image_threshold
		self._transcribe_threshold = transcribe_threshold

	def set_limit(self, limit: int | None):
		self._limit = limit

	def rowCount(self, parent: QModelIndex | QPersistentModelIndex = _EMPTY_INDEX) -> int:  # noqa: N802
		if parent.isValid():
			return 0
		return len(self._results)

	def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
		if not index.isValid() or not (0 <= index.row() < len(self._results)):
			return None
		result = self._results[index.row()]
		if role in (Qt.ItemDataRole.DisplayRole, self.PathRole):
			return result.path.as_posix()
		if role == self.ScoreRole:
			return format_score_percent(result.score)
		if role == self.LabelsRole:
			return match_labels(
				result,
				threshold=self._threshold,
				semantic_image_threshold=self._semantic_image_threshold,
				transcribe_threshold=self._transcribe_threshold,
			)
		return None

	def roleNames(self) -> dict[int, QByteArray]:  # noqa: N802
		return {
			self.ScoreRole: QByteArray(b"score"),
			self.PathRole: QByteArray(b"path"),
			self.LabelsRole: QByteArray(b"labels"),
		}

	def result_at(self, row: int) -> FileSearchResult | None:
		if 0 <= row < len(self._results):
			return self._results[row]
		return None

	@Slot()
	def clear(self):
		self.beginResetModel()
		self._results = []
		self.endResetModel()

	def insert_result(self, result: FileSearchResult):
		path_key = result.path.as_posix()
		if any(item.path.as_posix() == path_key for item in self._results):
			return
		self._results.append(result)
		self._results.sort(key=lambda item: item.score, reverse=True)
		if self._limit is not None and len(self._results) > self._limit:
			self._results = self._results[: self._limit]
		self.beginResetModel()
		self.endResetModel()

	def replace_results(self, results: list[FileSearchResult]):
		self.beginResetModel()
		self._results = sorted(results, key=lambda item: item.score, reverse=True)
		if self._limit is not None:
			self._results = self._results[: self._limit]
		self.endResetModel()


class MatchesModel(QAbstractListModel):
	ScoreRole = Qt.ItemDataRole.UserRole + 1
	LocationRole = Qt.ItemDataRole.UserRole + 2
	TextRole = Qt.ItemDataRole.UserRole + 3
	PlainTextRole = Qt.ItemDataRole.UserRole + 4

	def __init__(self, parent: Any = None):
		super().__init__(parent)
		self._rows: list[tuple[str, str, float, str]] = []

	def rowCount(self, parent: QModelIndex | QPersistentModelIndex = _EMPTY_INDEX) -> int:  # noqa: N802
		if parent.isValid():
			return 0
		return len(self._rows)

	def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
		if not index.isValid() or not (0 <= index.row() < len(self._rows)):
			return None
		location, preview, score, plain = self._rows[index.row()]
		if role == self.ScoreRole:
			return format_score_percent(score)
		if role in (Qt.ItemDataRole.DisplayRole, self.LocationRole):
			return location
		if role == self.TextRole:
			return preview
		if role == self.PlainTextRole:
			return plain
		return None

	def roleNames(self) -> dict[int, QByteArray]:  # noqa: N802
		return {
			self.ScoreRole: QByteArray(b"score"),
			self.LocationRole: QByteArray(b"location"),
			self.TextRole: QByteArray(b"text"),
			self.PlainTextRole: QByteArray(b"plainText"),
		}

	@Slot()
	def clear(self):
		self.beginResetModel()
		self._rows = []
		self.endResetModel()

	def load_from_result(self, result: FileSearchResult | None, *, query: str):
		self.beginResetModel()
		self._rows = []
		if result is not None:
			for location, preview, score, plain in iter_grouped_line_displays(
				result.lines, query=query, highlight="html"
			):
				self._rows.append((location, preview, score, plain))
		self.endResetModel()

	def row_plain(self, row: int) -> tuple[str, str]:
		if 0 <= row < len(self._rows):
			location, _preview, _score, plain = self._rows[row]
			return location, plain
		return "", ""

	def all_plain_lines(self) -> list[str]:
		return [f"{format_score_percent(score)}\t{location}\t{plain}" for location, _p, score, plain in self._rows]
