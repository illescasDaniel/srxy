"""Qt list models for search results and in-file matches."""

from __future__ import annotations

import bisect
from typing import Any

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, QPersistentModelIndex, Qt, Slot

from srxy.application.search_formatting import format_score_percent, iter_grouped_line_displays, match_labels
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
		count = len(self._results)
		if count:
			self.beginRemoveRows(_EMPTY_INDEX, 0, count - 1)
			self._results = []
			self.endRemoveRows()

	def insert_result(self, result: FileSearchResult):
		path_key = result.path.as_posix()
		for item in self._results:
			if item.path.as_posix() == path_key:
				return
		if self._limit is not None and len(self._results) >= self._limit:
			worst = self._results[-1]
			if result.score <= worst.score:
				return
		# Keep scores descending without resetting the whole model.
		scores = [-item.score for item in self._results]
		index = bisect.bisect_left(scores, -result.score)
		self.beginInsertRows(_EMPTY_INDEX, index, index)
		self._results.insert(index, result)
		self.endInsertRows()
		if self._limit is not None and len(self._results) > self._limit:
			last = len(self._results) - 1
			self.beginRemoveRows(_EMPTY_INDEX, last, last)
			self._results.pop()
			self.endRemoveRows()

	def replace_results(self, results: list[FileSearchResult]):
		new_results = sorted(results, key=lambda item: item.score, reverse=True)
		if self._limit is not None:
			new_results = new_results[: self._limit]
		old_count = len(self._results)
		new_count = len(new_results)
		if old_count:
			self.beginRemoveRows(_EMPTY_INDEX, 0, old_count - 1)
			self._results = []
			self.endRemoveRows()
		if new_count:
			self.beginInsertRows(_EMPTY_INDEX, 0, new_count - 1)
			self._results = new_results
			self.endInsertRows()


class MatchesModel(QAbstractListModel):
	ScoreRole = Qt.ItemDataRole.UserRole + 1
	LocationRole = Qt.ItemDataRole.UserRole + 2
	TextRole = Qt.ItemDataRole.UserRole + 3
	PlainTextRole = Qt.ItemDataRole.UserRole + 4
	LineNumberRole = Qt.ItemDataRole.UserRole + 5

	def __init__(self, parent: Any = None):
		super().__init__(parent)
		self._rows: list[tuple[str, str, float, str, int]] = []

	def rowCount(self, parent: QModelIndex | QPersistentModelIndex = _EMPTY_INDEX) -> int:  # noqa: N802
		if parent.isValid():
			return 0
		return len(self._rows)

	def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
		if not index.isValid() or not (0 <= index.row() < len(self._rows)):
			return None
		location, preview, score, plain, line_number = self._rows[index.row()]
		if role == self.ScoreRole:
			return format_score_percent(score)
		if role in (Qt.ItemDataRole.DisplayRole, self.LocationRole):
			return location
		if role == self.TextRole:
			return preview
		if role == self.PlainTextRole:
			return plain
		if role == self.LineNumberRole:
			return line_number
		return None

	def roleNames(self) -> dict[int, QByteArray]:  # noqa: N802
		return {
			self.ScoreRole: QByteArray(b"score"),
			self.LocationRole: QByteArray(b"location"),
			self.TextRole: QByteArray(b"text"),
			self.PlainTextRole: QByteArray(b"plainText"),
			self.LineNumberRole: QByteArray(b"lineNumber"),
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
			for location, preview, score, plain, line_number in iter_grouped_line_displays(
				result.lines, query=query, highlight="html"
			):
				self._rows.append((location, preview, score, plain, line_number))
		self.endResetModel()

	def row_plain(self, row: int) -> tuple[str, str]:
		if 0 <= row < len(self._rows):
			location, _preview, _score, plain, _line = self._rows[row]
			return location, plain
		return "", ""

	def all_plain_lines(self) -> list[str]:
		return [
			f"{format_score_percent(score)}\t{location}\t{plain}" for location, _p, score, plain, _line in self._rows
		]
