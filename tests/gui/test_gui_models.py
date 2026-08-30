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
		app = QCoreApplication([])
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
