"""GUI chrome text-tree snapshots (no ApplicationWindow — offscreen-safe)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication
from pytestqt.qtbot import QtBot

from srxy.adapters.inbound.cli.cli import build_parser, format_score_percent, match_labels
from srxy.adapters.inbound.gui.controller import SearchController


pytestmark = [pytest.mark.integration, pytest.mark.gui]

_SNAPSHOTS = Path(__file__).resolve().parent / "snapshots"
_UPDATE = os.environ.get("UPDATE_GUI_SNAPSHOTS", "").strip() in {"1", "true", "yes"}


def _chrome_tree(controller: SearchController) -> str:
	progress = float(controller.progress)  # pyright: ignore[reportArgumentType]
	capability_keys = ", ".join(sorted(json.loads(str(controller.capabilitiesJson))))
	lines = [
		"mainWindow:",
		"  title: srxy",
		f"  status: {controller.status}",
		f"  progressPercent: {round(progress)}%",
		"  sections: Where to search, What to search, How to search, Search, Search Results, Search progress",
		"  howStack: Options button + summary, Filters button + summary",
		f"  queryMode: {controller.queryMode}",
		f"  simpleQuery: {controller.simpleQuery}",
		f"  path: {controller.path}",
		f"  pathIssue: {controller.pathIssue}",
		f"  queryPreview: {controller.queryPreview}",
		f"  queryIssue: {controller.queryIssue}",
		f"  optionsSummary: {controller.optionsSummary}",
		f"  filtersSummary: {controller.filtersSummary}",
		f"  capabilityKeys: {capability_keys}",
		f"  stale: {controller.stale}",
		f"  hasSearched: {controller.hasSearched}",
		f"  canSearch: {controller.canSearch}",
		"  buttons: Browse…, Search, Options, Filters, Cancel",
		"  menus: Open file, Copy path, Copy all matches, Copy line, Copy location",
		"  panels: Results, Matches in file, File preview",
		"  resultColumns: #, Match, Path, Matched",
		"  matchColumns: #, Match, Location, Text",
	]
	return "\n".join(lines) + "\n"


def _results_tree(controller: SearchController) -> str:
	# Basenames only — tmp_path roots must not leak into committed snapshots.
	progress = float(controller.progress)  # pyright: ignore[reportArgumentType]
	lines = [
		"resultsPanel:",
		f"  status: {controller.status}",
		f"  progressPercent: {round(progress)}%",
		f"  simpleQuery: {controller.simpleQuery}",
		f"  rowCount: {controller.resultsModel.rowCount()}",
		"  results:",
	]
	model = controller.resultsModel
	for row in range(model.rowCount()):
		result = model.result_at(row)
		assert result is not None
		labels = match_labels(
			result,
			threshold=0.35,
			semantic_image_threshold=0.25,
			transcribe_threshold=0.35,
		)
		lines.append(f"    - #{row + 1} {result.path.name} score={format_score_percent(result.score)} labels={labels}")
	return "\n".join(lines) + "\n"


def _assert_snapshot(name: str, tree: str):
	snap_path = _SNAPSHOTS / f"{name}.snap.txt"
	_SNAPSHOTS.mkdir(parents=True, exist_ok=True)
	if _UPDATE or not snap_path.exists():
		snap_path.write_text(tree, encoding="utf-8")
	assert tree == snap_path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def qapp() -> QCoreApplication:
	os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
	app = QCoreApplication.instance()
	if app is None:
		app = QGuiApplication([])
	assert isinstance(app, QCoreApplication)
	return app


def test_given_default_controller_when_dumping_chrome_then_matches_snapshot(qapp: QCoreApplication):
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	_assert_snapshot("main_window", _chrome_tree(controller))


def test_given_uppercase_readme_when_search_completes_then_results_tree_matches_snapshot(
	qapp: QCoreApplication,
	qtbot: QtBot,
	tmp_path: Path,
):
	# given
	(tmp_path / "README.md").write_text("docs without matching body text\n", encoding="utf-8")
	(tmp_path / "notes.txt").write_text("unrelated\n", encoding="utf-8")
	args = build_parser().parse_args(["README", str(tmp_path), "--names-only", "--cli"])
	controller = SearchController(args)

	# when
	controller.startSearch()
	qtbot.waitUntil(lambda: not controller.searching, timeout=60000)

	# then
	assert controller.exit_code() == 0
	assert controller.resultsModel.rowCount() >= 1
	_assert_snapshot("readme_name_search_results", _results_tree(controller))
