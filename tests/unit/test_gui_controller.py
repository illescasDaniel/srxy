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
from srxy.application.search_session import SearchFinishedEvent, SearchResultEvent
from srxy.domain.models import FileSearchResult


pytestmark = [pytest.mark.unit, pytest.mark.xdist_group("gui")]


@pytest.fixture(scope="module")
def qapp() -> QCoreApplication:
	os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
	app = QCoreApplication.instance()
	if app is None:
		app = QCoreApplication([])
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


def test_given_python_file_when_selecting_result_then_preview_is_html_with_line_numbers(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	path = tmp_path / "sample.py"
	path.write_text("def hello():\n\treturn 1\n", encoding="utf-8")
	args = build_parser().parse_args(["hello", str(tmp_path), "--cli"])
	controller = SearchController(args)
	result = FileSearchResult(path=path, score=0.9, breakdown={"content": 0.9}, lines=[])
	controller.handle_search_event_for_tests(SearchFinishedEvent(results=[result], skipped_files=[]))

	# when
	controller.selectResult(0)

	# then
	assert float(controller.progress) == 100.0  # pyright: ignore[reportArgumentType]
	preview = str(controller.previewText)
	assert "<br/>" in preview
	assert "def" in preview
	assert "monospace" in preview


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

	# when
	controller.selectResult(0)

	# then
	preview = str(controller.previewText)
	assert "Preview truncated" in preview
	assert len(preview.encode("utf-8")) < 512_000


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
