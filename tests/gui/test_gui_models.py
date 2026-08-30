"""ResultsModel signals: row-based mutations, never a full model reset.

Regression guard for the QML ``DelegateModel::cancel: index out range``
warning: full ``beginResetModel``/``endResetModel`` in ``clear()`` and
``replace_results()`` invalidated rows while the ListView's async
``currentIndex`` binding and in-flight delegate incubations were stale.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication

from srxy.adapters.inbound.gui.models import ResultsModel
from srxy.domain.models import FileSearchResult


pytestmark = [pytest.mark.unit, pytest.mark.gui, pytest.mark.xdist_group("gui")]


@pytest.fixture(scope="module")
def qapp() -> QCoreApplication:
	import os

	os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
	app = QCoreApplication.instance()
	if app is None:
		from PySide6.QtGui import QGuiApplication

		app = QGuiApplication([])
	assert isinstance(app, QCoreApplication)
	return app


def _result(path: Path, score: float) -> FileSearchResult:
	return FileSearchResult(path=path, score=score, breakdown={"content": score}, lines=[])


class _SignalRecorder:
	def __init__(self) -> None:
		self.reset: list[object] = []
		self.removed: list[tuple[int, int]] = []
		self.inserted: list[tuple[int, int]] = []

	def on_reset(self, *args: object):
		self.reset.append(args)

	def on_removed(self, _parent: object, first: int, last: int):
		self.removed.append((first, last))

	def on_inserted(self, _parent: object, first: int, last: int):
		self.inserted.append((first, last))


def _wire(model: ResultsModel, recorder: _SignalRecorder) -> None:
	model.modelReset.connect(recorder.on_reset)
	model.rowsRemoved.connect(recorder.on_removed)
	model.rowsInserted.connect(recorder.on_inserted)


def test_given_populated_model_when_clear_then_emits_rows_removed_not_reset(
	qapp: QCoreApplication,
	tmp_path: Path,
):
	# given
	model = ResultsModel()
	model.replace_results([_result(tmp_path / f"file{i}.txt", 0.9 - i * 0.1) for i in range(3)])
	recorder = _SignalRecorder()
	_wire(model, recorder)

	# when
	model.clear()

	# then — row removal, not a full reset (the QML delegate-model warning source)
	assert model.rowCount() == 0
	assert recorder.removed == [(0, 2)]
	assert not recorder.reset


def test_given_empty_model_when_clear_then_no_signals(qapp: QCoreApplication):
	# given
	model = ResultsModel()
	recorder = _SignalRecorder()
	_wire(model, recorder)

	# when
	model.clear()

	# then
	assert model.rowCount() == 0
	assert recorder.removed == []
	assert not recorder.reset


def test_given_populated_model_when_replace_results_then_removes_and_inserts_rows(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	model = ResultsModel()
	model.replace_results([_result(tmp_path / "old.txt", 0.8)])
	recorder = _SignalRecorder()
	_wire(model, recorder)

	# when — same row count, different content
	model.replace_results([_result(tmp_path / "new.txt", 0.9)])

	# then — a remove + insert pair, never modelReset
	assert model.rowCount() == 1
	assert recorder.removed == [(0, 0)]
	assert recorder.inserted == [(0, 0)]
	assert not recorder.reset


def test_given_populated_model_when_replace_results_grows_then_emits_removed_and_inserted(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	model = ResultsModel()
	model.replace_results([_result(tmp_path / "old.txt", 0.8)])
	recorder = _SignalRecorder()
	_wire(model, recorder)

	# when
	model.replace_results([_result(tmp_path / f"new{i}.txt", 0.9 - i * 0.1) for i in range(3)])

	# then
	assert model.rowCount() == 3
	assert recorder.removed == [(0, 0)]
	assert recorder.inserted == [(0, 2)]
	assert not recorder.reset


def test_given_empty_model_when_replace_results_then_only_inserts(qapp: QCoreApplication, tmp_path: Path):
	# given
	model = ResultsModel()
	recorder = _SignalRecorder()
	_wire(model, recorder)

	# when
	model.replace_results([_result(tmp_path / "new.txt", 0.9)])

	# then
	assert model.rowCount() == 1
	assert recorder.removed == []
	assert recorder.inserted == [(0, 0)]
	assert not recorder.reset


def test_given_results_when_index_of_path_then_returns_row(qapp: QCoreApplication, tmp_path: Path):
	# given
	low = _result(tmp_path / "low.txt", 0.4)
	high = _result(tmp_path / "high.txt", 0.9)
	model = ResultsModel()
	model.insert_result(low)
	model.insert_result(high)

	# when / then
	assert model.index_of_path(high.path) == 0
	assert model.index_of_path(low.path) == 1
	assert model.index_of_path(tmp_path / "missing.txt") == -1


def test_given_duplicate_path_when_insert_result_then_ignored(qapp: QCoreApplication, tmp_path: Path):
	# given
	model = ResultsModel()
	path = tmp_path / "note.txt"
	assert model.insert_result(_result(path, 0.5)) is True

	# when / then
	assert model.insert_result(_result(path, 0.9)) is False
	assert model.rowCount() == 1


def test_given_batch_when_insert_results_then_sorted_unique(qapp: QCoreApplication, tmp_path: Path):
	model = ResultsModel()
	recorder = _SignalRecorder()
	_wire(model, recorder)
	added = model.insert_results(
		[
			_result(tmp_path / "a.txt", 0.4),
			_result(tmp_path / "b.txt", 0.9),
			_result(tmp_path / "a.txt", 0.7),
		]
	)
	assert added == 2
	assert model.rowCount() == 2
	assert model.result_at(0).path.name == "b.txt"
	assert model.index_of_path(tmp_path / "a.txt") == 1
	assert not recorder.reset


def test_given_partial_model_when_merge_results_then_adds_missing(qapp: QCoreApplication, tmp_path: Path):
	model = ResultsModel()
	model.insert_result(_result(tmp_path / "a.txt", 0.5))
	added = model.merge_results(
		[
			_result(tmp_path / "a.txt", 0.5),
			_result(tmp_path / "b.txt", 0.8),
		]
	)
	assert added == 1
	assert model.rowCount() == 2
	assert model.index_of_path(tmp_path / "b.txt") == 0


def test_given_batch_when_insert_results_then_reindexes_once(qapp: QCoreApplication, tmp_path: Path, monkeypatch):
	model = ResultsModel()
	model.insert_result(_result(tmp_path / "seed.txt", 0.1))
	calls = {"n": 0}
	original = model._reindex_paths

	def _counting_reindex():
		calls["n"] += 1
		original()

	monkeypatch.setattr(model, "_reindex_paths", _counting_reindex)
	added = model.insert_results([(_result(tmp_path / f"f{i}.txt", 0.5 + i * 0.01), f"label-{i}") for i in range(12)])
	assert added == 12
	assert calls["n"] == 1


def test_given_stream_append_when_insert_results_then_one_contiguous_range(qapp: QCoreApplication, tmp_path: Path):
	model = ResultsModel()
	model.set_stream_append(True)
	recorder = _SignalRecorder()
	_wire(model, recorder)
	added = model.insert_results(
		[
			(_result(tmp_path / "a.txt", 0.4), "a"),
			(_result(tmp_path / "b.txt", 0.9), "b"),
		]
	)
	assert added == 2
	assert model.rowCount() == 2
	# Append keeps arrival/batch order among new rows (sorted within the batch input).
	assert model.result_at(0).path.name == "b.txt"
	assert model.result_at(1).path.name == "a.txt"
	assert recorder.inserted == [(0, 1)]
	assert not recorder.reset
	assert model.sort_by_score() is False  # already score-desc within this tiny set


def test_given_unsorted_stream_when_sort_by_score_then_reorders(qapp: QCoreApplication, tmp_path: Path):
	model = ResultsModel()
	model.set_stream_append(True)
	model.insert_results([(_result(tmp_path / "low.txt", 0.2), "l"), (_result(tmp_path / "high.txt", 0.9), "h")])
	# Force unsorted order by a second append batch with a mid score first... actually first batch sorts input.
	model.set_stream_append(True)
	model.insert_results([(_result(tmp_path / "mid.txt", 0.5), "m")])
	assert [model.result_at(i).path.name for i in range(model.rowCount())] == ["high.txt", "low.txt", "mid.txt"]
	assert model.sort_by_score() is True
	assert [model.result_at(i).path.name for i in range(model.rowCount())] == ["high.txt", "mid.txt", "low.txt"]


def test_given_precomputed_labels_when_reading_data_then_uses_cache_without_match_labels(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch
):
	import srxy.adapters.inbound.gui.models as models_mod

	calls = {"n": 0}
	real = models_mod.match_labels

	def _counting_match_labels(*args, **kwargs):
		calls["n"] += 1
		return real(*args, **kwargs)

	monkeypatch.setattr(models_mod, "match_labels", _counting_match_labels)
	model = ResultsModel()
	path = tmp_path / "note.txt"
	model.insert_results([(_result(path, 0.9), "name, content")])
	assert calls["n"] == 0
	index = model.index(0, 0)
	assert model.data(index, ResultsModel.LabelsRole) == "name, content"
	assert model.data(index, ResultsModel.LabelsRole) == "name, content"
	assert calls["n"] == 0


def test_given_plain_insert_when_labels_missing_then_computes_once(qapp: QCoreApplication, tmp_path: Path, monkeypatch):
	import srxy.adapters.inbound.gui.models as models_mod

	calls = {"n": 0}
	real = models_mod.match_labels

	def _counting_match_labels(*args, **kwargs):
		calls["n"] += 1
		return real(*args, **kwargs)

	monkeypatch.setattr(models_mod, "match_labels", _counting_match_labels)
	model = ResultsModel()
	path = tmp_path / "note.txt"
	model.insert_result(_result(path, 0.9))
	assert calls["n"] == 1
	index = model.index(0, 0)
	assert model.data(index, ResultsModel.LabelsRole)
	assert model.data(index, ResultsModel.LabelsRole)
	assert calls["n"] == 1
