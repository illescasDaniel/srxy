from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication

from srxy.adapters.inbound.cli.cli import build_parser
from srxy.adapters.inbound.gui.controller import SearchController
from srxy.application.search_session import SearchFinishedEvent, SearchResultEvent
from srxy.domain.models import FileSearchResult


pytestmark = [pytest.mark.unit]


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
	assert "GPU" in controller.helpText("semantic")


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
