"""Qt list models for search results and in-file matches."""

from __future__ import annotations

import bisect
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
	Property,
	QAbstractListModel,
	QByteArray,
	QModelIndex,
	QPersistentModelIndex,
	Qt,
	Signal,
	Slot,
)

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
		self._path_keys: set[str] = set()
		self._path_rows: dict[str, int] = {}
		self._labels: dict[str, str] = {}
		self._limit: int | None = None
		self._threshold = 0.35
		self._semantic_image_threshold = 0.25
		self._transcribe_threshold = 0.35
		# While True, progressive inserts append in one contiguous range instead of
		# mid-list bisect inserts (those shift every row index and stall QML ListView).
		self._stream_append = False

	def set_thresholds(self, *, threshold: float, semantic_image_threshold: float, transcribe_threshold: float):
		self._threshold = threshold
		self._semantic_image_threshold = semantic_image_threshold
		self._transcribe_threshold = transcribe_threshold

	def set_limit(self, limit: int | None):
		self._limit = limit

	def set_stream_append(self, enabled: bool) -> None:
		self._stream_append = bool(enabled)

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
			return self._labels.get(result.path.as_posix(), "match")
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

	def index_of_path(self, path: Path | str | None) -> int:
		"""Return the row for ``path``, or ``-1`` when absent."""
		if path is None:
			return -1
		path_key = path.as_posix() if isinstance(path, Path) else str(path)
		return self._path_rows.get(path_key, -1)

	def _reindex_paths(self) -> None:
		self._path_rows = {item.path.as_posix(): index for index, item in enumerate(self._results)}
		self._path_keys = set(self._path_rows)

	def _label_for(self, result: FileSearchResult, label: str | None) -> str:
		if label is not None and label != "":
			return label
		return match_labels(
			result,
			threshold=self._threshold,
			semantic_image_threshold=self._semantic_image_threshold,
			transcribe_threshold=self._transcribe_threshold,
		)

	@Slot()
	def clear(self):
		count = len(self._results)
		if count:
			self.beginRemoveRows(_EMPTY_INDEX, 0, count - 1)
			self._results = []
			self._path_keys.clear()
			self._path_rows.clear()
			self._labels.clear()
			self.endRemoveRows()

	def insert_result(
		self,
		result: FileSearchResult,
		label: str | None = None,
		*,
		reindex: bool = True,
	) -> bool:
		"""Insert ``result`` by descending score. Return True when the model changed."""
		path_key = result.path.as_posix()
		if path_key in self._path_keys:
			return False
		if self._limit is not None and len(self._results) >= self._limit:
			worst = self._results[-1]
			if result.score <= worst.score:
				return False
		index = bisect.bisect_left(self._results, -result.score, key=lambda item: -item.score)
		self.beginInsertRows(_EMPTY_INDEX, index, index)
		self._results.insert(index, result)
		self._path_keys.add(path_key)
		self._labels[path_key] = self._label_for(result, label)
		self.endInsertRows()
		if self._limit is not None and len(self._results) > self._limit:
			last = len(self._results) - 1
			evicted = self._results[last]
			evicted_key = evicted.path.as_posix()
			self.beginRemoveRows(_EMPTY_INDEX, last, last)
			self._results.pop()
			self._path_keys.discard(evicted_key)
			self._labels.pop(evicted_key, None)
			self.endRemoveRows()
		if reindex:
			self._reindex_paths()
		return path_key in self._path_keys

	def insert_results(
		self,
		items: list[tuple[FileSearchResult, str | None]] | list[tuple[FileSearchResult, str]] | list[FileSearchResult],
	) -> int:
		"""Insert many results (score-sorted). Return how many rows were newly added.

		``items`` may be plain ``FileSearchResult`` values or ``(result, labels)`` tuples
		where labels were precomputed off the GUI thread.
		"""
		if not items:
			return 0
		normalized: list[tuple[FileSearchResult, str | None]] = []
		for item in items:
			if isinstance(item, tuple):
				normalized.append(item)
			else:
				normalized.append((item, None))
		unique: list[tuple[FileSearchResult, str | None]] = []
		seen: set[str] = set()
		for result, label in sorted(normalized, key=lambda pair: pair[0].score, reverse=True):
			path_key = result.path.as_posix()
			if path_key in seen or path_key in self._path_keys:
				continue
			seen.add(path_key)
			unique.append((result, label))
		if not unique:
			return 0
		if self._stream_append:
			return self._append_results_range(unique)
		# Prefer incremental inserts over wipe+rebuild (full replace forces the
		# QML ListView to destroy/recreate every delegate).
		added = 0
		for result, label in unique:
			if self.insert_result(result, label, reindex=False):
				added += 1
		if added:
			self._reindex_paths()
		return added

	def _append_results_range(self, unique: list[tuple[FileSearchResult, str | None]]) -> int:
		"""Append ``unique`` as one contiguous insert (ListView-friendly)."""
		if not unique:
			return 0
		to_add = unique
		if self._limit is not None and len(self._results) >= self._limit:
			worst = min(item.score for item in self._results)
			to_add = [(result, label) for result, label in unique if result.score > worst]
			if not to_add:
				return 0
		start = len(self._results)
		end = start + len(to_add) - 1
		self.beginInsertRows(_EMPTY_INDEX, start, end)
		for result, label in to_add:
			path_key = result.path.as_posix()
			self._results.append(result)
			self._path_keys.add(path_key)
			self._labels[path_key] = self._label_for(result, label)
		self.endInsertRows()
		# Evict worst rows if we grew past the limit (rare; only near cap).
		while self._limit is not None and len(self._results) > self._limit:
			worst_i = min(range(len(self._results)), key=lambda i: self._results[i].score)
			evicted = self._results[worst_i]
			evicted_key = evicted.path.as_posix()
			self.beginRemoveRows(_EMPTY_INDEX, worst_i, worst_i)
			self._results.pop(worst_i)
			self._path_keys.discard(evicted_key)
			self._labels.pop(evicted_key, None)
			self.endRemoveRows()
		self._reindex_paths()
		return len(to_add)

	def sort_by_score(self) -> bool:
		"""Re-order rows by descending score. Return True when order changed."""
		if len(self._results) <= 1:
			return False
		ordered = sorted(self._results, key=lambda item: item.score, reverse=True)
		if ordered == self._results:
			return False
		labels = {path: self._labels[path] for path in self._labels}
		self.replace_results(ordered, labels=labels)
		return True

	def merge_results(self, results: list[FileSearchResult]) -> int:
		"""Add any missing hits from ``results`` without wiping the current list."""
		if not results:
			return 0
		if not self._results:
			self.replace_results(results)
			return len(self._results)
		return self.insert_results([(result, None) for result in results])

	def replace_results(
		self,
		results: list[FileSearchResult],
		*,
		labels: dict[str, str] | None = None,
	):
		new_results = sorted(results, key=lambda item: item.score, reverse=True)
		if self._limit is not None:
			new_results = new_results[: self._limit]
		old_count = len(self._results)
		new_count = len(new_results)
		if old_count:
			self.beginRemoveRows(_EMPTY_INDEX, 0, old_count - 1)
			self._results = []
			self._path_keys.clear()
			self._path_rows.clear()
			self._labels.clear()
			self.endRemoveRows()
		if new_count:
			self.beginInsertRows(_EMPTY_INDEX, 0, new_count - 1)
			self._results = new_results
			self._reindex_paths()
			for result in new_results:
				path_key = result.path.as_posix()
				cached = labels.get(path_key) if labels is not None else None
				self._labels[path_key] = self._label_for(result, cached)
			self.endInsertRows()
		else:
			self._path_keys.clear()
			self._path_rows.clear()
			self._labels.clear()


class MatchesModel(QAbstractListModel):
	ScoreRole = Qt.ItemDataRole.UserRole + 1
	LocationRole = Qt.ItemDataRole.UserRole + 2
	TextRole = Qt.ItemDataRole.UserRole + 3
	PlainTextRole = Qt.ItemDataRole.UserRole + 4
	LineNumberRole = Qt.ItemDataRole.UserRole + 5

	maxTextLengthChanged = Signal()

	def __init__(self, parent: Any = None):
		super().__init__(parent)
		self._rows: list[tuple[str, str, float, str, int]] = []
		self._max_text_length = 0

	def _get_max_text_length(self) -> int:
		return self._max_text_length

	maxTextLength = Property(int, _get_max_text_length, notify=maxTextLengthChanged)

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
		self._max_text_length = 0
		self.maxTextLengthChanged.emit()
		self.endResetModel()

	def load_from_result(self, result: FileSearchResult | None, *, query: str):
		self.beginResetModel()
		self._rows = []
		max_len = 0
		if result is not None:
			for location, preview, score, plain, line_number in iter_grouped_line_displays(
				result.lines, query=query, highlight="html"
			):
				self._rows.append((location, preview, score, plain, line_number))
				max_len = max(max_len, len(plain))
		self._max_text_length = max_len
		self.maxTextLengthChanged.emit()
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
