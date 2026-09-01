from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QCoreApplication
from tests.helpers import set_fake_home

from srxy.adapters.inbound.cli.cli import build_parser
from srxy.adapters.inbound.gui.controller import SearchController
from srxy.adapters.inbound.gui.preview import PREVIEW_MAX_BYTES, PREVIEW_MAX_LINES
from srxy.application.search_session import (
	SearchActivityEvent,
	SearchErrorEvent,
	SearchFinishedEvent,
	SearchResultEvent,
)
from srxy.domain.models import FileSearchResult, SkippedFile
from srxy.domain.progress import ACTIVITY_SPINNER_FRAMES, ActivityUpdate


pytestmark = [pytest.mark.unit, pytest.mark.gui, pytest.mark.xdist_group("gui")]


@pytest.fixture(scope="module")
def qapp() -> QCoreApplication:
	os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
	from PySide6.QtGui import QGuiApplication

	app = QCoreApplication.instance()
	if app is None:
		app = QGuiApplication([])
	assert isinstance(app, QCoreApplication)
	return app


def test_given_query_when_controller_syncs_then_builds_file_query(qapp: QCoreApplication, tmp_path: Path):
	(tmp_path / "note.txt").write_text("alpha beta\n", encoding="utf-8")
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller.simpleQuery = "alpha"
	controller.path = str(tmp_path)
	synced = controller.sync_args_for_tests()
	assert synced.query == "alpha"
	assert Path(synced.path) == tmp_path


def test_given_default_cli_path_when_opening_gui_then_uses_home(
	qapp: QCoreApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
	# given
	home = tmp_path / "home"
	home.mkdir()
	set_fake_home(monkeypatch, home)
	args = build_parser().parse_args(["", ".", "--cli"])

	# when
	controller = SearchController(args)

	# then
	assert Path(str(controller.path)) == home
	assert Path(controller.sync_args_for_tests().path) == home


def test_given_explicit_path_when_opening_gui_then_keeps_path(qapp: QCoreApplication, tmp_path: Path):
	# given / when
	args = build_parser().parse_args(["", str(tmp_path), "--cli"])
	controller = SearchController(args)

	# then
	assert Path(str(controller.path)) == tmp_path


@pytest.mark.parametrize(
	"raw,expected",
	[
		# Windows file:/// URL still containing scheme
		("file:///C:/Users/kaumi/Downloads", "C:/Users/kaumi/Downloads"),
		# Windows path with stray leading slash (QML replace("file://","") bug)
		("/C:/Users/kaumi/Downloads", "C:/Users/kaumi/Downloads"),
		("/D:/projects/src", "D:/projects/src"),
		# Already clean Windows path — unchanged
		("C:/Users/kaumi/Downloads", "C:/Users/kaumi/Downloads"),
		# Unix path — leading slash preserved
		("/home/user/docs", "/home/user/docs"),
		("file:///home/user/docs", "/home/user/docs"),
		# Relative path — unchanged
		("./relative", "./relative"),
	],
)
def test_given_browsed_path_when_normalizing_then_strips_url_prefix(raw: str, expected: str):
	from srxy.adapters.inbound.gui.controller import _normalize_browsed_path  # pyright: ignore[reportPrivateUsage]

	assert _normalize_browsed_path(raw) == expected


def test_given_windows_url_when_controller_sets_path_then_no_leading_slash(
	qapp: QCoreApplication,
	tmp_path: Path,
):
	"""Setting a Windows-style QUrl path (file:///C:/...) normalises to C:/..."""
	args = build_parser().parse_args(["", str(tmp_path), "--cli"])
	controller = SearchController(args)

	controller.path = "file:///C:/Users/kaumi/Downloads"
	assert not controller.path.startswith("/")
	assert controller.path == "C:/Users/kaumi/Downloads"

	controller.path = "/C:/Users/kaumi/Downloads"
	assert controller.path == "C:/Users/kaumi/Downloads"


def test_given_search_finished_when_handling_event_then_updates_results_model(qapp: QCoreApplication, tmp_path: Path):
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	result = FileSearchResult(path=tmp_path / "note.txt", score=0.9, breakdown={"content": 0.9}, lines=[])
	controller.handle_search_event_for_tests(SearchResultEvent(result))
	controller.handle_search_event_for_tests(SearchFinishedEvent(results=[result], skipped_files=[]))
	assert controller.resultsModel.rowCount() == 1
	assert controller.status.endswith("matched")


def test_given_search_finished_with_skipped_files_when_handling_event_then_sets_search_warnings(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	skipped = SkippedFile(path=tmp_path / "silent.mp3", size_bytes=100, reason="transcribe_no_speech")

	# when
	controller.handle_search_event_for_tests(SearchFinishedEvent(results=[], skipped_files=[skipped]))

	# then
	assert controller.hasSearchWarnings is True
	assert "silent.mp3" in str(controller.searchWarnings)


def test_given_new_search_when_beginning_search_then_clears_search_warnings(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	skipped = SkippedFile(path=tmp_path / "silent.mp3", size_bytes=100, reason="transcribe_no_speech")
	controller.handle_search_event_for_tests(SearchFinishedEvent(results=[], skipped_files=[skipped]))
	assert controller.hasSearchWarnings is True
	monkeypatch.setattr(controller, "_start_search_worker", lambda _args: None)

	# when
	controller._begin_search(args)  # pyright: ignore[reportPrivateUsage]

	# then
	assert controller.hasSearchWarnings is False


def test_given_previous_selection_when_beginning_new_search_then_selection_is_cleared(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given — a prior search left a selected row and populated matches
	path = tmp_path / "note.txt"
	path.write_text("alpha beta\n", encoding="utf-8")
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	result = FileSearchResult(path=path, score=0.9, breakdown={"content": 0.9}, lines=[])
	controller.handle_search_event_for_tests(SearchFinishedEvent(results=[result], skipped_files=[]))
	assert controller.selectedResult == 0
	monkeypatch.setattr(controller, "_start_search_worker", lambda _args: None)

	# when
	controller._begin_search(args)  # pyright: ignore[reportPrivateUsage]

	# then — stale selection is dropped before the results model is reset, so the
	# QML results ListView never points currentIndex at a deleted row.
	assert controller.selectedResult == -1
	assert controller.matchesModel.rowCount() == 0


def test_given_indeterminate_activity_when_searching_then_status_spinner_animates(
	qapp: QCoreApplication, tmp_path: Path
):
	"""Spinner glyph animates via ``activitySpinner``; status body stays stable."""
	from PySide6.QtTest import QTest

	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller._set_searching(True)  # pyright: ignore[reportPrivateUsage]
	controller.handle_search_event_for_tests(SearchActivityEvent(ActivityUpdate(label="OCR · photo.png")))
	QTest.qWait(300)
	qapp.processEvents()

	assert "OCR · photo.png" in str(controller.status)
	assert str(controller.status).split(" ", 1)[0] not in set(ACTIVITY_SPINNER_FRAMES)
	assert str(controller.activitySpinner) in ACTIVITY_SPINNER_FRAMES
	first_spin = str(controller.activitySpinner)
	first_status = str(controller.status)
	QTest.qWait(150)
	qapp.processEvents()
	assert str(controller.status) == first_status
	assert str(controller.activitySpinner) != first_spin
	assert controller._activity_spinner_timer is not None  # pyright: ignore[reportPrivateUsage]
	controller._set_searching(False)  # pyright: ignore[reportPrivateUsage]


def test_given_activity_clear_when_handling_event_then_stops_status_spinner(qapp: QCoreApplication, tmp_path: Path):
	from srxy.application.search_session import SearchProgressEvent

	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller._set_searching(True)  # pyright: ignore[reportPrivateUsage]
	controller.handle_search_event_for_tests(SearchProgressEvent(current=5, total=10))
	assert str(controller.progressCount) == "5/10"
	assert controller.progressIndeterminate is False
	controller.handle_search_event_for_tests(SearchActivityEvent(ActivityUpdate(label="OCR · photo.png")))
	assert controller._activity is not None  # pyright: ignore[reportPrivateUsage]
	assert str(controller.activitySpinner) in ACTIVITY_SPINNER_FRAMES
	# File count stays visible while activity occupies the status line.
	assert str(controller.progressCount) == "5/10"

	controller.handle_search_event_for_tests(SearchActivityEvent(None))

	assert controller._activity is None  # pyright: ignore[reportPrivateUsage]
	assert controller._activity_spinner_timer is None  # pyright: ignore[reportPrivateUsage]
	assert str(controller.activitySpinner) == ""
	controller._set_searching(False)  # pyright: ignore[reportPrivateUsage]


def test_given_search_progress_when_handling_event_then_updates_file_count(qapp: QCoreApplication, tmp_path: Path):
	from srxy.application.search_session import SearchProgressEvent

	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	assert str(controller.progressCount) == ""
	assert controller.progressIndeterminate is False

	controller.handle_search_event_for_tests(SearchProgressEvent(current=3, total=12))

	assert str(controller.progressCount) == "3/12"
	assert float(controller.progress) == 25.0  # pyright: ignore[reportArgumentType]
	assert controller.progressIndeterminate is False
	assert "3/12" in str(controller.status)


def test_given_sticky_searching_activity_when_progress_arrives_then_status_shows_scanning(
	qapp: QCoreApplication, tmp_path: Path
):
	from PySide6.QtTest import QTest

	from srxy.application.search_session import SearchProgressEvent
	from srxy.i18n import tr

	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller._set_searching(True)  # pyright: ignore[reportPrivateUsage]
	controller.handle_search_event_for_tests(SearchActivityEvent(ActivityUpdate(label=tr("activity.searching"))))
	QTest.qWait(50)
	qapp.processEvents()

	controller.handle_search_event_for_tests(SearchProgressEvent(current=1, total=2))

	assert str(controller.progressCount) == "1/2"
	assert "1/2" in str(controller.status)
	assert "OCR ·" not in str(controller.status)

	controller.handle_search_event_for_tests(SearchActivityEvent(ActivityUpdate(label="OCR · photo.png")))
	QTest.qWait(300)
	qapp.processEvents()

	assert "OCR · photo.png" in str(controller.status)

	controller.handle_search_event_for_tests(SearchProgressEvent(current=2, total=2))

	assert str(controller.progressCount) == "2/2"
	assert "OCR · photo.png" in str(controller.status)
	controller._set_searching(False)  # pyright: ignore[reportPrivateUsage]


def test_given_search_start_when_no_total_yet_then_progress_is_indeterminate(qapp: QCoreApplication, tmp_path: Path):
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	# Simulate the startSearch progress reset without spinning a worker.
	controller._set_progress_value(0.0, indeterminate=True)  # pyright: ignore[reportPrivateUsage]
	assert controller.progressIndeterminate is True
	assert float(controller.progress) == 0.0  # pyright: ignore[reportArgumentType]


def test_given_determinate_activity_when_handling_event_then_status_shows_percent_not_bar(
	qapp: QCoreApplication, tmp_path: Path
):
	"""OCR page / transcribe segment % must not overwrite the file-scan progress bar."""
	from PySide6.QtTest import QTest

	from srxy.application.search_session import SearchProgressEvent

	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller._set_searching(True)  # pyright: ignore[reportPrivateUsage]
	controller.handle_search_event_for_tests(SearchProgressEvent(current=95, total=100))
	assert float(controller.progress) == 95.0  # pyright: ignore[reportArgumentType]
	assert str(controller.progressCount) == "95/100"

	controller.handle_search_event_for_tests(
		SearchActivityEvent(ActivityUpdate(label="OCR · scan.pdf", current=10, total=10))
	)
	QTest.qWait(300)
	qapp.processEvents()

	# File-scan bar stays put; page completion % only appears in status text.
	assert float(controller.progress) == 95.0  # pyright: ignore[reportArgumentType]
	assert str(controller.progressCount) == "95/100"
	assert controller.progressIndeterminate is False
	assert "100%" in str(controller.status)
	assert "OCR · scan.pdf" in str(controller.status)
	assert str(controller.activitySpinner) in ACTIVITY_SPINNER_FRAMES
	controller._set_searching(False)  # pyright: ignore[reportPrivateUsage]


def test_given_aggregated_ocr_activity_when_handling_event_then_status_shows_file_count(
	qapp: QCoreApplication, tmp_path: Path
):
	from PySide6.QtTest import QTest

	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller._set_searching(True)  # pyright: ignore[reportPrivateUsage]
	controller.handle_search_event_for_tests(SearchActivityEvent(ActivityUpdate(label="OCR · 3 files")))
	QTest.qWait(300)
	qapp.processEvents()

	assert "OCR · 3 files" in str(controller.status)
	assert str(controller.activitySpinner) in ACTIVITY_SPINNER_FRAMES
	controller._set_searching(False)  # pyright: ignore[reportPrivateUsage]


def test_given_search_finished_when_activity_active_then_clears_status_spinner(qapp: QCoreApplication, tmp_path: Path):
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller._set_searching(True)  # pyright: ignore[reportPrivateUsage]
	controller.handle_search_event_for_tests(SearchActivityEvent(ActivityUpdate(label="CLIP · img.png")))
	assert controller._activity is not None  # pyright: ignore[reportPrivateUsage]
	assert controller._activity_spinner_timer is not None  # pyright: ignore[reportPrivateUsage]

	controller.handle_search_event_for_tests(SearchFinishedEvent(results=[], skipped_files=[]))

	assert controller._activity is None  # pyright: ignore[reportPrivateUsage]
	assert controller._activity_spinner_timer is None  # pyright: ignore[reportPrivateUsage]
	assert str(controller.activitySpinner) == ""
	assert controller.progressIndeterminate is False
	controller._set_searching(False)  # pyright: ignore[reportPrivateUsage]


def test_given_python_file_when_selecting_result_then_preview_is_plain_text_with_gutter(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	path = tmp_path / "sample.py"
	path.write_text("def hello():\n\treturn 1\n", encoding="utf-8")
	args = build_parser().parse_args(["hello", str(tmp_path), "--cli"])
	controller = SearchController(args)
	result = FileSearchResult(path=path, score=0.9, breakdown={"content": 0.9}, lines=[])
	controller.handle_search_event_for_tests(SearchFinishedEvent(results=[result], skipped_files=[]))
	controller.flush_preview_for_tests()

	# when / then
	assert float(controller.progress) == 100.0  # pyright: ignore[reportArgumentType]
	preview = str(controller.previewText)
	assert "<br/>" not in preview
	assert "def hello" in preview
	assert controller.previewLineCount == 2
	assert "1" in str(controller.previewGutterText)
	assert "2" in str(controller.previewGutterText)
	controller.shutdown(thread_wait_ms=1000)


def test_given_selected_result_when_reading_header_then_path_and_metadata_split(qapp: QCoreApplication, tmp_path: Path):
	# given
	path = tmp_path / "nested" / "sample.py"
	path.parent.mkdir(parents=True)
	path.write_text("def hello():\n\treturn 1\n", encoding="utf-8")
	args = build_parser().parse_args(["hello", str(tmp_path), "--cli"])
	controller = SearchController(args)
	result = FileSearchResult(path=path, score=0.9, breakdown={"content": 0.9}, lines=[])
	controller.handle_search_event_for_tests(SearchFinishedEvent(results=[result], skipped_files=[]))
	controller.flush_preview_for_tests()

	# when / then
	assert str(controller.previewFilePath) == path.as_posix()
	header = str(controller.previewHeader)
	assert path.as_posix() not in header
	assert "matched" in header
	assert str(controller.previewContentType) == "PY"
	controller.shutdown(thread_wait_ms=1000)


def test_given_no_gpu_capabilities_when_clamping_then_disables_semantic(qapp: QCoreApplication, tmp_path: Path):
	from srxy.adapters.inbound.gui.capabilities import Capabilities

	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli", "--semantic"])
	controller = SearchController(args)
	controller.set_capabilities_for_tests(
		Capabilities(
			semantic_deps=True,
			has_gpu=False,
			ocr=True,
			ffmpeg=True,
			transcribe_deps=True,
			semantic_enabled=False,
			semantic_image_enabled=False,
			transcribe_enabled=False,
			ocr_enabled=True,
		)
	)
	assert controller.isFeatureEnabled("semantic") is False
	assert "GPU" in controller.unavailableReason("semantic")
	assert "Currently unavailable" not in controller.helpText("semantic")


def test_given_uppercase_multi_term_joins_when_syncing_then_builds_valid_query(qapp: QCoreApplication, tmp_path: Path):
	# given
	args = build_parser().parse_args(["", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller.queryMode = "multi"
	controller.termRowsJson = json.dumps(
		[{"term": "alpha", "join": ""}, {"term": "beta", "join": "OR"}, {"term": "gamma", "join": "AND"}]
	)

	# when
	synced = controller.sync_args_for_tests()
	preview = str(controller.queryPreview)

	# then
	assert "alpha" in synced.query
	assert "beta" in synced.query
	assert "gamma" in synced.query
	assert "|" in synced.query
	assert "&" in synced.query
	assert not preview.startswith("invalid:")


def test_given_fresh_controller_when_search_starts_then_has_searched_becomes_true(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	(tmp_path / "note.txt").write_text("alpha\n", encoding="utf-8")
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	assert controller.hasSearched is False

	# when
	controller.startSearch()

	# then
	assert controller.hasSearched is True
	controller.cancelSearch()
	deadline = time.monotonic() + 30
	while controller.searching and time.monotonic() < deadline:
		qapp.processEvents()
		time.sleep(0.01)
	assert not controller.searching
	controller.shutdown(thread_wait_ms=1000)


def test_given_search_finished_when_worker_exits_then_clears_thread_refs(qapp: QCoreApplication, tmp_path: Path):
	# given
	(tmp_path / "note.txt").write_text("alpha\n", encoding="utf-8")
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)

	# when
	controller.startSearch()
	deadline = time.monotonic() + 30
	while controller.searching and time.monotonic() < deadline:
		qapp.processEvents()
		time.sleep(0.01)

	# then
	assert not controller.searching
	deadline = time.monotonic() + 5
	while controller.search_thread_for_tests() is not None and time.monotonic() < deadline:
		qapp.processEvents()
		time.sleep(0.01)
	assert controller.search_thread_for_tests() is None
	controller.shutdown(thread_wait_ms=1000)


def test_given_back_to_back_searches_when_completed_then_both_succeed(qapp: QCoreApplication, tmp_path: Path):
	# given — overlapping teardown used to SIGBUS via worker.deleteLater on the QThread
	(tmp_path / "readme.txt").write_text("readme content\n", encoding="utf-8")
	(tmp_path / "other.txt").write_text("other\n", encoding="utf-8")
	args = build_parser().parse_args(["readme", str(tmp_path), "--cli"])
	controller = SearchController(args)

	# when — run several searches as soon as each reports idle
	for _ in range(5):
		controller.startSearch()
		deadline = time.monotonic() + 30
		while controller.searching and time.monotonic() < deadline:
			qapp.processEvents()
			time.sleep(0.01)
		assert not controller.searching
		assert controller.resultsModel.rowCount() >= 1

	# then
	assert controller.exit_code() == 0
	controller.shutdown(thread_wait_ms=1000)


def test_given_running_threads_when_shutdown_then_cancels_and_waits(qapp: QCoreApplication, tmp_path: Path):
	# given
	(tmp_path / "note.txt").write_text("alpha\n", encoding="utf-8")
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller.startSearch()
	process = MagicMock()
	process.returncode = None
	controller.set_search_subprocess_for_tests(process)

	# when
	controller.shutdown(thread_wait_ms=1000)
	qapp.processEvents()

	# then
	process.kill.assert_called_once()
	assert controller.search_subprocess_for_tests() is None


def test_given_deleted_update_thread_when_shutdown_then_does_not_raise(qapp: QCoreApplication, tmp_path: Path):
	# given — update worker deleteLater'd the C++ QThread but left a Python wrapper
	from PySide6.QtCore import QThread

	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	thread = QThread()
	controller.set_update_thread_for_tests(thread)
	thread.deleteLater()
	qapp.processEvents()

	# when / then
	controller.shutdown(thread_wait_ms=100)


def test_given_start_search_when_called_then_does_not_refresh_capabilities(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	(tmp_path / "note.txt").write_text("alpha\n", encoding="utf-8")
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller.set_capabilities_for_tests(controller.capabilities_for_tests())
	calls: list[str] = []

	def _track_refresh():
		calls.append("refresh")

	monkeypatch.setattr(controller, "refreshCapabilities", _track_refresh)

	# when
	controller.startSearch()
	deadline = time.monotonic() + 30
	while controller.searching and time.monotonic() < deadline:
		qapp.processEvents()
		time.sleep(0.01)

	# then
	assert calls == []
	controller.shutdown(thread_wait_ms=1000)


def test_given_capabilities_when_refresh_capabilities_then_does_not_import_torch(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given — Options used to import torch / fork nvidia-smi on a QThread and SIGSEGV.
	import builtins
	from typing import Any

	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	real_import = builtins.__import__

	def _guarded_import(name: str, *args_: Any, **kwargs: Any):
		if name == "torch" or name.startswith("torch."):
			raise AssertionError("torch must not be imported during capabilities refresh")
		return real_import(name, *args_, **kwargs)

	monkeypatch.setattr(builtins, "__import__", _guarded_import)
	monkeypatch.setattr(
		"srxy.adapters.inbound.gui.capabilities.has_accelerated_gpu_nofork",
		lambda: False,
	)

	# when
	controller.refreshCapabilities()

	# then
	assert controller.isFeatureEnabled("semantic") is False


def test_given_invalid_filters_when_apply_filters_json_then_keeps_previous_state(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	before = controller.filtersJson()

	# when
	error = controller.applyFiltersJson(
		json.dumps(
			{
				"top_files": "not-a-number",
				"max_matches": "50",
				"threshold": "35",
				"semantic_image_threshold": "18",
				"transcribe_threshold": "25",
				"size_limits": {"text_mib": "100", "ocr_mib": "50", "transcribe_mib": "500"},
			}
		)
	)

	# then
	assert error
	assert controller.filtersJson() == before


def test_given_invalid_filters_when_validate_filters_json_then_returns_error_without_applying(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	before = controller.filtersJson()
	payload = json.dumps(
		{
			"top_files": "",
			"max_matches": "50",
			"threshold": "abc",
			"semantic_image_threshold": "18",
			"transcribe_threshold": "25",
			"size_limits": {"text_mib": "100", "ocr_mib": "50", "transcribe_mib": "500"},
		}
	)

	# when
	error = controller.validateFiltersJson(payload)

	# then
	assert error
	assert (
		"must be a number" in error.lower()
		or "between" in error.lower()
		or "required" in error.lower()
		or "number" in error.lower()
	)
	assert controller.filtersJson() == before


def test_given_negative_threshold_when_validate_filters_json_then_returns_error(qapp: QCoreApplication, tmp_path: Path):
	# given
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	payload = json.dumps(
		{
			"top_files": "",
			"max_matches": "50",
			"threshold": "-5",
			"semantic_image_threshold": "18",
			"transcribe_threshold": "25",
			"size_limits": {"text_mib": "100", "ocr_mib": "50", "transcribe_mib": "500"},
		}
	)

	# when / then
	assert controller.validateFiltersJson(payload)
	assert (
		controller.validateFiltersJson(
			json.dumps(
				{
					"top_files": "",
					"max_matches": "50",
					"threshold": "35",
					"semantic_image_threshold": "18",
					"transcribe_threshold": "25",
					"size_limits": {"text_mib": "100", "ocr_mib": "50", "transcribe_mib": "500"},
				}
			)
		)
		== ""
	)


def test_given_cancel_requested_when_search_error_event_then_status_cancelled_without_error_dialog(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	from srxy.i18n import tr

	args = build_parser().parse_args(["", str(tmp_path), "--cli"])
	controller = SearchController(args)
	errors: list[str] = []
	controller.errorOccurred.connect(errors.append)
	controller.cancelSearch()

	# when
	controller.handle_search_event_for_tests(SearchErrorEvent("search worker exited unexpectedly"))

	# then
	assert errors == []
	assert controller.status == tr("status.search_cancelled")
	assert controller.exit_code() == 2


def test_given_result_row_when_selecting_then_selected_result_property_updates(qapp: QCoreApplication, tmp_path: Path):
	# given
	path = tmp_path / "note.txt"
	path.write_text("alpha\n", encoding="utf-8")
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	result = FileSearchResult(path=path, score=0.9, breakdown={"content": 0.9}, lines=[])
	controller.handle_search_event_for_tests(SearchFinishedEvent(results=[result], skipped_files=[]))

	# when
	controller.selectResult(0)

	# then
	assert controller.selectedResult == 0


def test_given_large_file_when_selecting_result_then_preview_is_capped_with_footer(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	path = tmp_path / "large.txt"
	path.write_text(("line " * 20 + "\n") * 3000, encoding="utf-8")
	args = build_parser().parse_args(["line", str(tmp_path), "--cli"])
	controller = SearchController(args)
	result = FileSearchResult(path=path, score=0.9, breakdown={"content": 0.9}, lines=[])
	controller.handle_search_event_for_tests(SearchFinishedEvent(results=[result], skipped_files=[]))
	controller.flush_preview_for_tests()

	# then
	preview = str(controller.previewText)
	assert "Preview truncated" in str(controller.previewFooter)
	assert preview.count("\n") + 1 <= PREVIEW_MAX_LINES
	assert len(preview.encode("utf-8")) <= PREVIEW_MAX_BYTES
	controller.shutdown(thread_wait_ms=1000)


def test_given_huge_file_when_resolving_preview_then_read_is_capped(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	path = tmp_path / "huge.bin"
	path.write_bytes(b"x" * (PREVIEW_MAX_BYTES * 4))
	args = build_parser().parse_args(["x", str(tmp_path), "--cli"])
	controller = SearchController(args)
	result = FileSearchResult(path=path, score=0.9, breakdown={"content": 0.9}, lines=[])
	reads: list[int] = []
	real_open = Path.open

	def tracking_open(
		self: Path,
		mode: str = "r",
		buffering: int = -1,
		encoding: str | None = None,
		errors: str | None = None,
		newline: str | None = None,
	):
		handle = real_open(self, mode, buffering, encoding, errors, newline)
		if self == path:
			original_read = handle.read

			def capped_read(size: int = -1):
				reads.append(size)
				return original_read(size)

			handle.read = capped_read  # type: ignore[method-assign]
		return handle

	monkeypatch.setattr(Path, "open", tracking_open)

	# when
	controller.handle_search_event_for_tests(SearchFinishedEvent(results=[result], skipped_files=[]))
	controller.flush_preview_for_tests()

	# then — never asks for the whole file (sample sniff + capped preview read)
	assert reads
	assert all(
		size in {8192, PREVIEW_MAX_BYTES + 1} or (isinstance(size, int) and 0 < size <= PREVIEW_MAX_BYTES + 1)
		for size in reads
	)
	assert max(reads) <= PREVIEW_MAX_BYTES + 1
	controller.shutdown(thread_wait_ms=1000)


def test_given_selected_path_when_higher_score_inserts_above_then_selection_retargets(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	low = tmp_path / "low.txt"
	high = tmp_path / "high.txt"
	low.write_text("alpha\n", encoding="utf-8")
	high.write_text("alpha\n", encoding="utf-8")
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller.handle_search_event_for_tests(
		SearchResultEvent(result=FileSearchResult(path=low, score=0.5, breakdown={"content": 0.5}, lines=[]))
	)
	controller.selectResult(0)
	controller.flush_preview_for_tests()
	assert controller.selectedResult == 0
	assert str(controller.previewFilePath) == low.as_posix()

	# when — better score inserts above the current row
	controller.handle_search_event_for_tests(
		SearchResultEvent(result=FileSearchResult(path=high, score=0.9, breakdown={"content": 0.9}, lines=[]))
	)

	# then — highlight follows the originally selected path
	assert controller.selectedResult == 1
	assert str(controller.previewFilePath) == low.as_posix()
	controller.shutdown(thread_wait_ms=1000)


def test_given_many_result_events_when_flushing_batch_then_model_updates_once_per_flush(
	qapp: QCoreApplication, tmp_path: Path
):
	"""Progressive events buffer until flush — avoids per-hit ListView churn."""
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	model = controller.resultsModel
	assert model is not None
	model.set_stream_append(True)
	inserts_before = []

	def _on_inserted(*_args):
		inserts_before.append(1)

	model.rowsInserted.connect(_on_inserted)
	for index in range(20):
		path = tmp_path / f"f{index}.txt"
		path.write_text("alpha\n", encoding="utf-8")
		controller._on_search_event(  # noqa: SLF001 — intentional: skip test helper flush
			SearchResultEvent(
				result=FileSearchResult(path=path, score=0.5 + index * 0.01, breakdown={"content": 0.5}, lines=[]),
				labels=f"label-{index}",
			)
		)
	assert model.rowCount() == 0
	assert inserts_before == []
	controller.flush_pending_results_for_tests()
	assert model.rowCount() == 20
	assert len(inserts_before) == 1  # stream-append: one contiguous rowsInserted range
	# After the first flush, further coalescing uses the longer batch window.
	assert controller._results_flush_started is True  # noqa: SLF001
	controller._schedule_results_flush()  # noqa: SLF001
	assert controller._results_flush_timer is not None  # noqa: SLF001
	assert controller._results_flush_timer.interval() == 1000  # noqa: SLF001
	controller.shutdown(thread_wait_ms=1000)


def test_given_precomputed_labels_when_flushing_batch_then_gui_skips_match_labels(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch
):
	import srxy.adapters.inbound.gui.models as models_mod

	calls = {"n": 0}
	real = models_mod.match_labels

	def _counting_match_labels(*args, **kwargs):
		calls["n"] += 1
		return real(*args, **kwargs)

	monkeypatch.setattr(models_mod, "match_labels", _counting_match_labels)
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	path = tmp_path / "note.txt"
	path.write_text("alpha\n", encoding="utf-8")
	controller.handle_search_event_for_tests(
		SearchResultEvent(
			result=FileSearchResult(path=path, score=0.9, breakdown={"content": 0.9}, lines=[]),
			labels="name, content",
		)
	)
	assert calls["n"] == 0
	model = controller.resultsModel
	assert model is not None
	assert model.data(model.index(0, 0), model.LabelsRole) == "name, content"
	assert calls["n"] == 0
	controller.shutdown(thread_wait_ms=1000)


def test_given_misnamed_media_when_previewing_then_content_type_shows_mismatch(qapp: QCoreApplication, tmp_path: Path):
	from pathlib import Path as P

	fixture = P(__file__).resolve().parents[1] / "fixtures" / "content_kind" / "beep.ogg"
	path = tmp_path / "secret.txt"
	path.write_bytes(fixture.read_bytes())
	args = build_parser().parse_args(["beep", str(tmp_path), "--cli"])
	controller = SearchController(args)
	result = FileSearchResult(path=path, score=0.9, breakdown={"name": 0.9}, lines=[])
	controller.handle_search_event_for_tests(SearchFinishedEvent(results=[result], skipped_files=[]))
	controller.flush_preview_for_tests()
	content_type = str(controller.previewContentType)
	assert "named .txt" in content_type
	assert content_type.split(" · ", 1)[0] in {"OGG", "OGA", "OPUS"}
	controller.shutdown(thread_wait_ms=1000)


def test_given_selected_path_when_search_finishes_then_selection_is_preserved(qapp: QCoreApplication, tmp_path: Path):
	# given
	first = tmp_path / "a.txt"
	second = tmp_path / "b.txt"
	first.write_text("alpha\n", encoding="utf-8")
	second.write_text("alpha\n", encoding="utf-8")
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller.handle_search_event_for_tests(
		SearchResultEvent(result=FileSearchResult(path=first, score=0.4, breakdown={"content": 0.4}, lines=[]))
	)
	controller.handle_search_event_for_tests(
		SearchResultEvent(result=FileSearchResult(path=second, score=0.8, breakdown={"content": 0.8}, lines=[]))
	)
	controller.selectResult(1)  # select the lower-scoring path
	controller.flush_preview_for_tests()
	assert str(controller.previewFilePath) == first.as_posix()

	# when
	controller.handle_search_event_for_tests(
		SearchFinishedEvent(
			results=[
				FileSearchResult(path=second, score=0.8, breakdown={"content": 0.8}, lines=[]),
				FileSearchResult(path=first, score=0.4, breakdown={"content": 0.4}, lines=[]),
			],
			skipped_files=[],
		)
	)
	controller.flush_preview_for_tests()

	# then
	assert controller.selectedResult == 1
	assert str(controller.previewFilePath) == first.as_posix()
	controller.shutdown(thread_wait_ms=1000)


def test_given_controller_when_results_empty_then_hint_follows_search_state(qapp: QCoreApplication, tmp_path: Path):
	# given — query must not match, otherwise a fast worker can fill results before cancel
	from srxy.i18n import tr

	(tmp_path / "note.txt").write_text("alpha\n", encoding="utf-8")
	args = build_parser().parse_args(["zzzz-no-match-token", str(tmp_path), "--cli"])
	controller = SearchController(args)

	# then — before any search
	assert controller.resultsEmptyHint == tr("results.empty.before")

	# when — search starts
	controller.startSearch()
	assert controller.hasSearched is True
	assert controller.resultsEmptyHint == tr("results.empty.searching")

	# when — cancel leaves an empty, post-search table
	controller.cancelSearch()
	deadline = time.monotonic() + 30
	while controller.searching and time.monotonic() < deadline:
		qapp.processEvents()
		time.sleep(0.01)
	assert controller.resultsEmptyHint == tr("results.empty.none")

	# when — results present
	result = FileSearchResult(path=tmp_path / "note.txt", score=0.9, breakdown={"name": 0.9}, lines=[])
	controller.handle_search_event_for_tests(SearchFinishedEvent(results=[result], skipped_files=[]))
	assert controller.resultsEmptyHint == ""
	controller.shutdown(thread_wait_ms=1000)


def test_given_cancelled_search_when_thread_finishes_then_stale_stays_true(qapp: QCoreApplication, tmp_path: Path):
	# given — cancel must not commit a search baseline (Search accent follows stale)
	(tmp_path / "note.txt").write_text("alpha\n", encoding="utf-8")
	args = build_parser().parse_args(["zzzz-no-match-token", str(tmp_path), "--cli"])
	controller = SearchController(args)
	assert controller.stale is True

	# when
	controller.startSearch()
	controller.cancelSearch()
	deadline = time.monotonic() + 30
	while controller.searching and time.monotonic() < deadline:
		qapp.processEvents()
		time.sleep(0.01)

	# then — cancelled run cleared results; keep inviting Search (accent)
	assert not controller.searching
	assert controller.stale is True
	controller.shutdown(thread_wait_ms=1000)


def test_given_completed_then_cancelled_research_when_finished_then_stale_again(qapp: QCoreApplication, tmp_path: Path):
	# given — a successful baseline, then cancel a re-run of the same query
	(tmp_path / "readme.txt").write_text("readme content\n", encoding="utf-8")
	args = build_parser().parse_args(["readme", str(tmp_path), "--cli"])
	controller = SearchController(args)

	controller.startSearch()
	deadline = time.monotonic() + 30
	while controller.searching and time.monotonic() < deadline:
		qapp.processEvents()
		time.sleep(0.01)
	assert not controller.searching
	assert controller.stale is False

	# when — re-run clears results at start; cancel must restore stale/accent
	controller.startSearch()
	assert controller.searching
	controller.cancelSearch()
	deadline = time.monotonic() + 30
	while controller.searching and time.monotonic() < deadline:
		qapp.processEvents()
		time.sleep(0.01)

	# then
	assert not controller.searching
	assert controller.stale is True
	controller.shutdown(thread_wait_ms=1000)


def test_given_ampersand_simple_query_when_syncing_then_treats_term_as_literal(qapp: QCoreApplication, tmp_path: Path):
	# given
	args = build_parser().parse_args(["", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller.path = str(tmp_path)
	controller.queryMode = "simple"
	controller.simpleQuery = "hello&"

	# when
	synced = controller.sync_args_for_tests()
	preview = str(controller.queryPreview)

	# then
	assert "hello&" in synced.query or '"hello&"' in synced.query
	assert preview == ""
	assert controller.queryIssue == ""
	assert controller.canSearch is True


def test_given_slash_in_simple_query_when_syncing_then_sanitizes_path_separators(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	args = build_parser().parse_args(["", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller.path = str(tmp_path)
	controller.queryMode = "simple"
	controller.simpleQuery = "foo/bar\\baz"

	# when
	synced = controller.sync_args_for_tests()

	# then
	assert "/" not in synced.query
	assert "foo" in synced.query and "bar" in synced.query and "baz" in synced.query
	assert controller.queryPreview == ""


def test_given_ampersand_multi_term_when_syncing_then_first_term_is_literal(qapp: QCoreApplication, tmp_path: Path):
	# given
	args = build_parser().parse_args(["", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller.path = str(tmp_path)
	controller.queryMode = "multi"
	controller.termRowsJson = json.dumps([{"term": "hello&", "join": ""}, {"term": "other", "join": "and"}])

	# when
	synced = controller.sync_args_for_tests()

	# then
	assert "hello&" in synced.query or '"hello&"' in synced.query
	assert "other" in synced.query
	assert "&" in synced.query
	assert not str(controller.queryPreview).startswith("invalid:")


def test_given_invalid_path_when_checking_can_search_then_reports_path_issue(qapp: QCoreApplication, tmp_path: Path):
	# given
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller.simpleQuery = "alpha"

	# when
	controller.path = "some text here"

	# then
	assert controller.pathIssue
	assert controller.canSearch is False


def test_given_empty_query_when_checking_can_search_then_disabled(qapp: QCoreApplication, tmp_path: Path):
	# given
	args = build_parser().parse_args(["", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller.path = str(tmp_path)

	# when
	controller.simpleQuery = ""

	# then
	assert controller.queryIssue == ""
	assert controller.canSearch is False


def test_given_invalid_advanced_query_when_checking_then_query_issue_set(qapp: QCoreApplication, tmp_path: Path):
	# given
	args = build_parser().parse_args(["", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller.path = str(tmp_path)
	controller.queryMode = "advanced"

	# when
	controller.advancedQuery = "("

	# then
	assert controller.queryIssue
	assert controller.canSearch is False


def test_given_spanish_when_set_language_then_gui_labels_and_privacy_translate(
	qapp: QCoreApplication,
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	from srxy.i18n import set_language

	monkeypatch.setenv("SRXY_SKIP_UPDATE_CHECK", "1")
	set_language("en")
	args = build_parser().parse_args(["", str(tmp_path), "--cli"])
	controller = SearchController(args)
	english_privacy = str(controller.aboutPrivacyHtml)
	assert "Privacy" in english_privacy or "privacy" in english_privacy
	assert controller.i18nTr("gui.search") == "Search"

	# when
	controller.setLanguage("es")

	# then
	assert controller.language == "es"
	assert controller.i18nTr("gui.search") == "Buscar"
	assert controller.i18nTr("gui.section.where") == "Dónde buscar"
	assert "Dónde:" in str(controller.optionsSummary)
	assert "Nombres" in str(controller.optionsSummary)
	assert "Todos los archivos" in str(controller.filtersSummary)
	assert "necesita una GPU" in controller.i18nTr("unavailable.semantic_gpu")
	spanish_privacy = str(controller.aboutPrivacyHtml)
	assert "aviso de privacidad" in spanish_privacy.lower()
	assert "terceros" in spanish_privacy.lower()
	assert spanish_privacy != english_privacy
	assert "instalador de escritorio de srxy" not in spanish_privacy.lower()
	assert "este instalador" not in spanish_privacy.lower()
	assert "qué puede descargar srxy" in spanish_privacy.lower()

	# cleanup
	controller.setLanguage("en")
	set_language("en")
	assert controller.i18nTr("gui.search") == "Search"


def _make_preview_controller(qapp: QCoreApplication, tmp_path: Path, text: str, query: str = "alpha"):
	path = tmp_path / "sample.txt"
	path.write_text(text, encoding="utf-8")
	args = build_parser().parse_args([query, str(tmp_path), "--cli"])
	controller = SearchController(args)
	result = FileSearchResult(path=path, score=0.9, breakdown={"content": 0.9}, lines=[])
	controller.handle_search_event_for_tests(SearchFinishedEvent(results=[result], skipped_files=[]))
	controller.flush_preview_for_tests()
	return controller


def test_given_preview_when_find_next_and_previous_then_wraps_and_reports_status(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	controller = _make_preview_controller(qapp, tmp_path, "alpha\nbeta\nalpha\n")

	# when
	controller.openPreviewFind()
	controller.setPreviewFindQuery("alpha")

	# then
	assert controller.previewFindOpen is True
	assert controller.previewFindStatus == "1 / 2"
	controller.previewFindNext()
	assert controller.previewFindStatus == "2 / 2"
	controller.previewFindNext()
	assert controller.previewFindStatus == "1 / 2"
	controller.previewFindPrevious()
	assert controller.previewFindStatus == "2 / 2"
	controller.shutdown(thread_wait_ms=1000)


def test_given_preview_when_find_no_match_then_status_reports_no_matches(qapp: QCoreApplication, tmp_path: Path):
	# given
	controller = _make_preview_controller(qapp, tmp_path, "alpha\n")

	# when
	controller.setPreviewFindQuery("zzz")

	# then
	assert controller.previewFindStatus == "No matches"
	assert controller.previewFindOpen is False
	controller.shutdown(thread_wait_ms=1000)


def test_given_preview_when_closing_find_then_clears_query(qapp: QCoreApplication, tmp_path: Path):
	# given
	controller = _make_preview_controller(qapp, tmp_path, "alpha\n")
	controller.setPreviewFindQuery("alpha")
	assert controller.previewFindStatus == "1 / 1"

	# when
	controller.closePreviewFind()

	# then
	assert controller.previewFindQuery == ""
	assert controller.previewFindOpen is False
	assert controller.previewFindStatus == ""
	controller.shutdown(thread_wait_ms=1000)


def test_given_preview_when_theme_changes_then_gutter_color_updates(qapp: QCoreApplication, tmp_path: Path):
	# given
	path = tmp_path / "sample.py"
	path.write_text("def x():\n\treturn 1\n", encoding="utf-8")
	args = build_parser().parse_args(["return", str(tmp_path), "--cli"])
	controller = SearchController(args)
	result = FileSearchResult(path=path, score=0.9, breakdown={"content": 0.9}, lines=[])
	controller.handle_search_event_for_tests(SearchFinishedEvent(results=[result], skipped_files=[]))
	controller.flush_preview_for_tests()

	# when
	light = str(controller.previewGutterColor)
	controller.setPreviewTheme(False)
	dark = str(controller.previewGutterColor)

	# then
	assert light == "#888888"
	assert dark == "#6e7681"
	assert "def x" in str(controller.previewText)
	controller.shutdown(thread_wait_ms=1000)


def test_given_attached_document_when_selecting_then_preview_loads_via_worker(qapp: QCoreApplication, tmp_path: Path):
	# given — attaching a document enables the async preview path
	from PySide6.QtGui import QTextDocument

	class _QuickDoc:
		def __init__(self):
			self._doc = QTextDocument()

		def textDocument(self):
			return self._doc

	path = tmp_path / "note.txt"
	path.write_text("alpha\nbeta\n", encoding="utf-8")
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller.attachPreviewDocument(_QuickDoc())
	result = FileSearchResult(path=path, score=0.9, breakdown={"content": 0.9}, lines=[])

	# when
	controller.handle_search_event_for_tests(SearchFinishedEvent(results=[result], skipped_files=[]))
	assert str(controller.previewText) == "Loading preview…"
	controller.flush_preview_for_tests()

	# then
	assert "alpha" in str(controller.previewText)
	assert controller.previewLineCount == 2
	controller.shutdown(thread_wait_ms=1000)


def test_given_deleted_preview_document_when_applying_then_still_emits_and_clears_loading(
	qapp: QCoreApplication, tmp_path: Path
):
	# given — attach then simulate QML destroying the C++ document
	from PySide6.QtGui import QTextDocument

	class _QuickDoc:
		def __init__(self):
			self._doc = QTextDocument()

		def textDocument(self):
			return self._doc

	path = tmp_path / "note.txt"
	path.write_text("alpha\n", encoding="utf-8")
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	quick = _QuickDoc()
	controller.attachPreviewDocument(quick)
	controller._preview_message = "Loading preview…"  # pyright: ignore[reportPrivateUsage]
	controller._preview_plain_text = ""  # pyright: ignore[reportPrivateUsage]
	# Drop the only reference so Shiboken marks the C++ object deleted.
	quick._doc = QTextDocument()  # replace with a fresh doc, then delete the old attach target
	# Force the controller to see a dead quick wrapper instead of crashing the process.
	controller._preview_quick_document = object()  # pyright: ignore[reportPrivateUsage]

	# when
	controller._on_preview_ready(  # pyright: ignore[reportPrivateUsage]
		controller._preview_generation,  # pyright: ignore[reportPrivateUsage]
		("alpha\n", path, "", False, "", "TXT", ".txt"),
	)

	# then — must leave loading and not raise
	assert str(controller.previewText) == "alpha\n"
	controller.shutdown(thread_wait_ms=1000)


def test_given_stale_preview_generation_when_worker_finishes_then_result_is_ignored(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	from PySide6.QtGui import QTextDocument

	class _QuickDoc:
		def __init__(self):
			self._doc = QTextDocument()

		def textDocument(self):
			return self._doc

	path = tmp_path / "note.txt"
	path.write_text("alpha\n", encoding="utf-8")
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller.attachPreviewDocument(_QuickDoc())

	# when — deliver a stale worker payload after a newer generation
	controller._preview_generation = 5  # pyright: ignore[reportPrivateUsage]
	controller._on_preview_ready(  # pyright: ignore[reportPrivateUsage]
		4,
		("stale text", path, "", False, "", "TXT", ".txt"),
	)

	# then
	assert "stale text" not in str(controller.previewText)
	controller.shutdown(thread_wait_ms=1000)


def test_given_selected_result_when_opening_folder_then_desktop_reveal_is_called(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	path = tmp_path / "note.txt"
	path.write_text("alpha\n", encoding="utf-8")
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	desktop = MagicMock()
	controller = SearchController(args, desktop=desktop)
	result = FileSearchResult(path=path, score=0.9, breakdown={"content": 0.9}, lines=[])
	controller.handle_search_event_for_tests(SearchFinishedEvent(results=[result], skipped_files=[]))

	# when
	controller.openResultFolder(0)

	# then
	desktop.reveal_path.assert_called_once_with(path)


def test_given_settings_when_opening_then_snapshot_is_available(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SKIP_UPDATE_CHECK", "1")
	monkeypatch.setenv("SRXY_CACHE_DIR", str(tmp_path / "cache"))
	args = build_parser().parse_args(["", str(tmp_path), "--cli"])
	controller = SearchController(args)

	# when
	controller.openSettings()

	# then
	assert controller.settingsOpen is True
	payload = json.loads(str(controller.settingsJson))
	assert [row["kind"] for row in payload["models"]] == [
		"semantic_text",
		"semantic_image",
		"transcribe",
		"all",
	]
	controller.closeSettings()
	assert controller.settingsOpen is False


def test_given_clear_confirm_when_accepted_then_clears_model(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	from unittest.mock import patch

	import srxy.application.settings_maintenance as maintenance

	monkeypatch.setenv("SRXY_SKIP_UPDATE_CHECK", "1")
	monkeypatch.setenv("SRXY_CACHE_DIR", str(tmp_path / "cache"))
	args = build_parser().parse_args(["", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller.openSettings()
	controller.confirmClearModel("semantic_image")
	assert controller.settingsConfirmOpen is True

	# when
	with patch.object(maintenance, "clear_model_kind") as clear_kind:
		controller.acceptSettingsConfirm()

	# then
	assert controller.settingsConfirmOpen is False
	clear_kind.assert_called_once_with("semantic_image")
	controller.shutdown(thread_wait_ms=100)


def test_given_searching_when_redownload_requested_then_emits_busy_error(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SKIP_UPDATE_CHECK", "1")
	args = build_parser().parse_args(["", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller._searching = True  # pyright: ignore[reportPrivateUsage]
	errors: list[str] = []
	controller.errorOccurred.connect(errors.append)

	# when
	controller.redownloadModel("semantic_text")

	# then
	assert errors
	assert "search" in errors[0].lower() or "download" in errors[0].lower()
	controller.shutdown(thread_wait_ms=100)


def test_given_idle_controller_when_redownload_then_queues_and_starts_worker(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SKIP_UPDATE_CHECK", "1")
	args = build_parser().parse_args(["", str(tmp_path), "--cli"])
	controller = SearchController(args)
	started: list[str] = []

	def _fake_start(kind: str):
		started.append(kind)

	controller._start_download_worker = _fake_start  # pyright: ignore[reportPrivateUsage]

	# when
	controller.redownloadModel("all")

	# then
	queue = controller._download_queue  # pyright: ignore[reportPrivateUsage]
	assert [item.kind for item in queue] == ["semantic_text", "semantic_image", "transcribe"]
	assert started == ["semantic_text"]
	assert controller._settings_redownload is True  # pyright: ignore[reportPrivateUsage]
	controller._download_queue = []  # pyright: ignore[reportPrivateUsage]
	controller._settings_redownload = False  # pyright: ignore[reportPrivateUsage]
	controller.shutdown(thread_wait_ms=100)


def test_given_cache_present_when_clearing_then_removes_db(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	from srxy.adapters.outbound.cache.cache import cache_db_path, cache_key_path

	monkeypatch.setenv("SRXY_SKIP_UPDATE_CHECK", "1")
	monkeypatch.setenv("SRXY_CACHE_DIR", str(tmp_path / "cache"))
	cache_root = tmp_path / "cache"
	cache_root.mkdir()
	db = cache_db_path()
	key = cache_key_path()
	db.write_bytes(b"db")
	key.write_bytes(b"key")
	args = build_parser().parse_args(["", str(tmp_path), "--cli"])
	controller = SearchController(args)

	# when
	controller.clearResultsCache()

	# then
	assert not db.exists()
	assert not key.exists()
	controller.shutdown(thread_wait_ms=100)


def test_given_download_all_confirm_when_accepted_then_queues_all_models(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SKIP_UPDATE_CHECK", "1")
	args = build_parser().parse_args(["", str(tmp_path), "--cli"])
	controller = SearchController(args)
	started: list[str] = []
	controller._start_download_worker = started.append  # pyright: ignore[reportPrivateUsage]

	# when
	controller.confirmDownloadAllModels()
	assert controller.settingsConfirmOpen is True
	controller.acceptSettingsConfirm()

	# then
	queue = controller._download_queue  # pyright: ignore[reportPrivateUsage]
	assert [item.kind for item in queue] == ["semantic_text", "semantic_image", "transcribe"]
	assert started == ["semantic_text"]
	controller._download_queue = []  # pyright: ignore[reportPrivateUsage]
	controller._settings_redownload = False  # pyright: ignore[reportPrivateUsage]
	controller.shutdown(thread_wait_ms=100)


def test_given_preferences_file_when_reset_then_deletes_and_refreshes_language(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	from srxy.application.search_options import SearchOptions
	from srxy.application.settings import save_persisted_search_prefs, set_language_setting, settings_path
	from srxy.i18n import set_language

	monkeypatch.setenv("SRXY_SKIP_UPDATE_CHECK", "1")
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	set_language("es")
	set_language_setting("es")
	from dataclasses import replace

	from srxy.application.search_filters import default_search_filters

	custom_filters = replace(default_search_filters(), top_files="10")
	save_persisted_search_prefs(
		persist_options=True,
		persist_filters=True,
		options=SearchOptions(include_hidden=True, include_archives=True),
		filters=custom_filters,
	)
	args = build_parser().parse_args(["", str(tmp_path), "--cli"])
	controller = SearchController(args)
	assert controller.language == "es"
	assert settings_path().is_file()
	assert json.loads(controller.optionsJson())["include_hidden"] is True
	assert json.loads(controller.filtersJson())["top_files"] == "10"

	# when
	controller.confirmResetPreferences()
	controller.acceptSettingsConfirm()

	# then — file gone, language cleared, session options/filters back to factory
	assert not settings_path().exists()
	assert "SRXY_LANGUAGE" not in os.environ
	payload = json.loads(str(controller.settingsJson))
	assert payload["preferences"]["present"] is False
	options = json.loads(controller.optionsJson())
	assert options["include_hidden"] is False
	assert options["include_archives"] is False
	assert options["persist_options"] is False
	filters = json.loads(controller.filtersJson())
	assert filters["persist_filters"] is False
	assert filters["top_files"] == ""
	assert options == {**json.loads(controller.defaultOptionsJson()), "persist_options": False}
	assert filters == {**json.loads(controller.defaultFiltersJson()), "persist_filters": False}
	controller.shutdown(thread_wait_ms=100)
	assert not settings_path().exists()
	set_language("en")


def test_given_persisted_options_when_controller_starts_then_restores(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	from srxy.application.search_options import SearchOptions
	from srxy.application.settings import save_persisted_search_prefs

	save_persisted_search_prefs(
		persist_options=True,
		persist_filters=False,
		options=SearchOptions(include_hidden=True, include_archives=True),
	)
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])

	# when
	controller = SearchController(args)
	payload = json.loads(controller.optionsJson())

	# then
	assert payload["persist_options"] is True
	assert payload["include_hidden"] is True
	assert payload["include_archives"] is True
	controller.shutdown(thread_wait_ms=100)


def test_given_persist_flag_when_shutdown_then_writes_settings(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	settings = tmp_path / "settings.json"
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(settings))
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	error = controller.applyOptionsJson(
		json.dumps(
			{
				**json.loads(controller.defaultOptionsJson()),
				"include_noise": True,
				"persist_options": True,
			}
		)
	)
	assert error == ""

	# when
	controller.shutdown(thread_wait_ms=100)

	# then
	from srxy.application.settings import load_persisted_search_prefs

	prefs = load_persisted_search_prefs()
	assert prefs.persist_options is True
	assert prefs.options is not None
	assert prefs.options.include_noise is True


def test_given_unpersist_when_shutdown_then_clears_payload(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	settings = tmp_path / "settings.json"
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(settings))
	from srxy.application.search_options import SearchOptions
	from srxy.application.settings import save_persisted_search_prefs

	save_persisted_search_prefs(
		persist_options=True,
		persist_filters=False,
		options=SearchOptions(include_hidden=True),
	)
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	error = controller.applyOptionsJson(json.dumps({**json.loads(controller.optionsJson()), "persist_options": False}))
	assert error == ""

	# when
	controller.shutdown(thread_wait_ms=100)

	# then
	from srxy.application.settings import load_persisted_search_prefs, load_settings

	prefs = load_persisted_search_prefs()
	assert prefs.persist_options is False
	assert prefs.options is None
	assert "options" not in load_settings()


def test_given_default_options_json_when_reset_then_factory_defaults(qapp: QCoreApplication, tmp_path: Path):
	# given
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller.applyOptionsJson(
		json.dumps({**json.loads(controller.defaultOptionsJson()), "include_hidden": True, "persist_options": True})
	)

	# when
	defaults = json.loads(controller.defaultOptionsJson())

	# then — defaults are factory values; session persist flag untouched until push
	assert defaults["include_hidden"] is False
	assert defaults["search_names"] is True
	assert "persist_options" not in defaults
	assert json.loads(controller.optionsJson())["persist_options"] is True
	controller.shutdown(thread_wait_ms=100)


def _gpu_capabilities(*, semantic: bool = True) -> object:
	from srxy.adapters.inbound.gui.capabilities import Capabilities

	return Capabilities(
		semantic_deps=True,
		has_gpu=semantic,
		ocr=True,
		ffmpeg=True,
		transcribe_deps=True,
		semantic_enabled=semantic,
		semantic_image_enabled=semantic,
		transcribe_enabled=semantic,
		ocr_enabled=True,
	)


def test_given_persisted_semantic_when_controller_starts_then_survives_probe(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	"""Regression: default_capabilities() has semantic_enabled=False; clamp must not wipe
	persisted Similar-meaning before the deferred GPU probe finishes."""
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	from srxy.application.search_options import SearchOptions
	from srxy.application.settings import save_persisted_search_prefs

	save_persisted_search_prefs(
		persist_options=True,
		persist_filters=False,
		options=SearchOptions(semantic=True, search_names=True, search_contents=True),
	)

	def _probe():
		return _gpu_capabilities(semantic=True)

	_probe.cache_clear = lambda: None  # type: ignore[attr-defined]
	monkeypatch.setattr("srxy.adapters.inbound.gui.controller.probe_capabilities", _probe)

	# when
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	payload = json.loads(controller.optionsJson())

	# then
	assert payload["persist_options"] is True
	assert payload["semantic"] is True
	controller.shutdown(thread_wait_ms=100)


def test_given_persist_options_when_apply_then_writes_settings_immediately(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller.set_capabilities_for_tests(_gpu_capabilities(semantic=True))

	# when — OK commits to disk without waiting for aboutToQuit
	error = controller.applyOptionsJson(
		json.dumps(
			{
				**json.loads(controller.defaultOptionsJson()),
				"semantic": True,
				"persist_options": True,
			}
		)
	)
	assert error == ""

	# then
	from srxy.application.settings import load_persisted_search_prefs

	prefs = load_persisted_search_prefs()
	assert prefs.persist_options is True
	assert prefs.options is not None
	assert prefs.options.semantic is True

	# and a fresh controller restores them after probe
	def _probe():
		return _gpu_capabilities(semantic=True)

	_probe.cache_clear = lambda: None  # type: ignore[attr-defined]
	monkeypatch.setattr("srxy.adapters.inbound.gui.controller.probe_capabilities", _probe)
	restored = SearchController(build_parser().parse_args(["alpha", str(tmp_path), "--cli"]))
	assert json.loads(restored.optionsJson())["semantic"] is True
	controller.shutdown(thread_wait_ms=100)
	restored.shutdown(thread_wait_ms=100)


def test_given_unwritable_settings_when_persist_then_emits_error(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	args = build_parser().parse_args(["alpha", str(tmp_path), "--cli"])
	controller = SearchController(args)
	errors: list[str] = []
	controller.errorOccurred.connect(errors.append)
	monkeypatch.setattr(
		"srxy.application.settings.save_persisted_search_prefs",
		lambda **_kwargs: False,
	)

	# when
	controller.applyOptionsJson(json.dumps({**json.loads(controller.defaultOptionsJson()), "persist_options": True}))

	# then
	assert errors
	assert "settings.json" in errors[0]
	controller.shutdown(thread_wait_ms=100)
