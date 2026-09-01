"""Click-driven QML GUI flows (path / query / options / filters / search)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from tests.gui.helpers import ensure_qapp, load_main
from tests.helpers import OCR_FIXTURES_DIR

from srxy.adapters.inbound.cli.cli import build_parser
from srxy.adapters.inbound.gui.controller import SearchController
from srxy.adapters.outbound.ocr.ocr_text import tesseract_available


pytestmark = [pytest.mark.integration, pytest.mark.gui]


@pytest.fixture(scope="module")
def qapp():
	return ensure_qapp()


def _result_paths(controller: SearchController) -> list[str]:
	model = controller.resultsModel
	paths: list[str] = []
	for row in range(model.rowCount()):
		value = model.data(model.index(row, 0), model.PathRole)
		if isinstance(value, str):
			paths.append(value)
	return paths


def test_given_path_query_options_filters_when_searching_then_results_and_progress_settle(
	qapp,
	tmp_path: Path,
):
	# given
	needle = "srxy-flow-needle-alpha"
	(tmp_path / "note.txt").write_text(f"hello {needle} world\n", encoding="utf-8")
	(tmp_path / "other.txt").write_text("unrelated\n", encoding="utf-8")
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	harness = load_main(controller, qapp)
	for _ in range(20):
		qapp.processEvents()

	# when
	harness.set_text("pathField", str(tmp_path))
	harness.set_text("simpleQueryField", needle)

	harness.open_dialog_via("optionsButton", "optionsDialog")
	harness.set_checked("optNames", True)
	harness.set_checked("optContents", True)
	harness.set_checked("optPersist", False)
	harness.apply_dialog_ok("optionsOkButton", "optionsDialog")

	harness.open_dialog_via("filtersButton", "filtersDialog")
	harness.set_text("fltTopFiles", "5")
	harness.set_checked("fltPersist", False)
	harness.apply_dialog_ok("filtersOkButton", "filtersDialog")

	assert bool(harness.prop("searchButton", "enabled")) is True
	harness.click("searchButton")

	# then — progress chrome arms once a search has started
	harness.wait_until(
		lambda: bool(controller.hasSearched) or bool(controller.searching),
		timeout_ms=10_000,
		message="search never started",
	)
	assert harness.find("progressBar") is not None
	harness.wait_search_finished()

	assert controller.resultsModel.rowCount() >= 1
	assert any(path.endswith("note.txt") for path in _result_paths(controller))
	assert float(controller.progress) >= 100.0 or not bool(controller.progressIndeterminate)
	assert str(harness.prop("statusLabel", "text")).strip()
	assert bool(controller.stale) is False
	assert bool(harness.prop("searchButton", "accent")) is False
	filters = json.loads(controller.filtersJson())
	assert str(filters.get("top_files", "")) == "5"

	harness.shutdown()


def test_given_names_only_options_when_searching_then_filename_hit_appears(qapp, tmp_path: Path):
	# given
	(tmp_path / "README.md").write_text("docs without matching body text\n", encoding="utf-8")
	(tmp_path / "notes.txt").write_text("unrelated\n", encoding="utf-8")
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	harness = load_main(controller, qapp)
	for _ in range(20):
		qapp.processEvents()

	# when
	harness.set_text("pathField", str(tmp_path))
	harness.set_text("simpleQueryField", "README")
	harness.open_dialog_via("optionsButton", "optionsDialog")
	harness.set_checked("optNames", True)
	harness.set_checked("optContents", False)
	harness.set_checked("optPersist", False)
	harness.apply_dialog_ok("optionsOkButton", "optionsDialog")
	harness.click("searchButton")
	harness.wait_search_finished()

	# then
	assert controller.exit_code() == 0
	assert any(path.endswith("README.md") for path in _result_paths(controller))
	options = json.loads(controller.optionsJson())
	assert options.get("search_names") is True
	assert options.get("search_contents") is False

	harness.shutdown()


def test_given_invalid_threshold_when_filters_ok_clicked_then_ok_disabled_and_error_visible(
	qapp,
	tmp_path: Path,
):
	# given
	args = build_parser().parse_args(["", str(tmp_path), "--cli"])
	controller = SearchController(args)
	harness = load_main(controller, qapp)
	for _ in range(20):
		qapp.processEvents()
	harness.open_dialog_via("filtersButton", "filtersDialog")
	assert bool(harness.prop("filtersOkButton", "enabled")) is True

	# when — alphanumeric garbage while typing
	harness.set_text("fltThreshold", "nope")

	# then
	assert bool(harness.prop("filtersOkButton", "enabled")) is False
	assert bool(harness.prop("filtersError", "visible")) is True
	assert str(harness.prop("filtersError", "text")).strip()

	# when — restore a valid value
	harness.set_text("fltThreshold", "35")

	# then
	assert bool(harness.prop("filtersOkButton", "enabled")) is True
	assert bool(harness.prop("filtersError", "visible")) is False

	harness.click("filtersOkButton")  # close cleanly if still open
	harness.shutdown()


@pytest.mark.skipif(not tesseract_available(), reason="tesseract binary not on PATH")
def test_given_ocr_folder_when_searching_then_progress_count_appears(qapp):
	# given
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	harness = load_main(controller, qapp)
	for _ in range(20):
		qapp.processEvents()

	# when
	harness.set_text("pathField", str(OCR_FIXTURES_DIR))
	harness.set_text("simpleQueryField", "revenue")
	harness.open_dialog_via("optionsButton", "optionsDialog")
	harness.set_checked("optNames", False)
	harness.set_checked("optContents", True)
	harness.set_checked("optOcr", True)
	harness.set_checked("optPersist", False)
	harness.apply_dialog_ok("optionsOkButton", "optionsDialog")
	harness.click("searchButton")
	harness.wait_until(
		lambda: bool(controller.hasSearched) or bool(controller.searching),
		timeout_ms=10_000,
		message="search never started",
	)

	# then — listing catch-up must surface file totals (e.g. 0/N) during OCR search
	harness.wait_until(
		lambda: bool(re.fullmatch(r"\d+/\d+", str(harness.prop("progressCount", "text")).strip())),
		timeout_ms=30_000,
		message="progressCount never showed determinate file totals",
	)

	harness.wait_search_finished(timeout_ms=120_000)
	harness.shutdown()
