"""GUI chrome text-tree snapshots (no ApplicationWindow — offscreen-safe)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication
from pytestqt.qtbot import QtBot
from tests.gui.helpers import load_main

from srxy.adapters.inbound.cli.cli import build_parser
from srxy.adapters.inbound.gui.controller import SearchController
from srxy.application.search_formatting import format_score_percent, match_labels
from srxy.application.search_session import SearchFinishedEvent
from srxy.domain.models import FileSearchResult


pytestmark = [pytest.mark.unit, pytest.mark.gui]

_SNAPSHOTS = Path(__file__).resolve().parent / "snapshots"
_UPDATE = os.environ.get("UPDATE_GUI_SNAPSHOTS", "").strip() in {"1", "true", "yes"}


def _display_path(path: str) -> str:
	home = str(Path.home())
	if path == home or path.rstrip("/") == home.rstrip("/"):
		return "~"
	return path


def _chrome_tree(controller: SearchController) -> str:
	progress = float(controller.progress)  # pyright: ignore[reportArgumentType]
	capability_keys = ", ".join(sorted(json.loads(str(controller.capabilitiesJson))))
	t = controller.i18nTr
	sections = ", ".join(
		[
			t("gui.section.where"),
			t("gui.section.what"),
			t("gui.section.how"),
			t("gui.section.results"),
			t("gui.section.progress"),
		]
	)
	buttons = ", ".join(
		[
			t("gui.browse"),
			t("gui.search"),
			t("gui.options"),
			t("gui.filters"),
			t("gui.cancel"),
		]
	)
	menus = ", ".join(
		[
			t("gui.menu.open_file"),
			t("gui.menu.copy_path"),
			t("gui.menu.copy_all_matches"),
			t("gui.menu.copy_line"),
			t("gui.menu.copy_location"),
		]
	)
	help_menu = (
		f"{t('menu.about')}, {t('menu.check_updates')}, "
		f"{t('menu.language')} ({t('menu.language.en')} / {t('menu.language.es')})"
	)
	settings_menu = (
		f"{t('menu.settings.download_all')}, {t('menu.settings.reset_cache')}, "
		f"{t('menu.settings.reset_preferences')}, {t('menu.settings.open')}"
	)
	lines = [
		"mainWindow:",
		"  title: srxy",
		f"  status: {controller.status}",
		f"  progressPercent: {round(progress)}%",
		f"  progressCount: {controller.progressCount}",
		f"  language: {controller.language}",
		f"  sections: {sections}",
		"  howStack: What + How row (query+Search left; mode/Options/Filters right)",
		f"  queryMode: {controller.queryMode}",
		f"  simpleQuery: {controller.simpleQuery}",
		f"  path: {_display_path(str(controller.path))}",
		f"  pathIssue: {controller.pathIssue}",
		f"  queryPreview: {controller.queryPreview}",
		f"  queryIssue: {controller.queryIssue}",
		f"  optionsSummary: {controller.optionsSummary}",
		f"  filtersSummary: {controller.filtersSummary}",
		f"  capabilityKeys: {capability_keys}",
		f"  stale: {controller.stale}",
		f"  hasSearched: {controller.hasSearched}",
		f"  resultsEmptyHint: {controller.resultsEmptyHint}",
		f"  canSearch: {controller.canSearch}",
		f"  buttons: {buttons}",
		f"  menus: {menus}",
		f"  settingsMenu: {settings_menu}",
		f"  helpMenu: {help_menu}",
		f"  dialogs: {t('settings.title')}, {t('about.title')}, {t('update.title')}, {t('help.dialog_title')}, "
		f"{t('gui.download_model')}, {t('gui.downloading')}, {t('gui.error')}, "
		f"{t('gui.search_warnings.title')}",
		f"  panels: {t('gui.results')}, {t('gui.matches_in_file')}, File preview",
		f"  resultColumns: {t('gui.col.hash')}, {t('gui.col.match')}, {t('gui.col.path')}, {t('gui.col.matched')}",
		f"  matchColumns: {t('gui.col.hash')}, {t('gui.col.match')}, {t('gui.col.location')}, {t('gui.col.text')}",
	]
	return "\n".join(lines) + "\n"


def _results_tree(controller: SearchController) -> str:
	# Basenames only — tmp_path roots must not leak into committed snapshots.
	progress = float(controller.progress)  # pyright: ignore[reportArgumentType]
	lines = [
		"resultsPanel:",
		f"  status: {controller.status}",
		f"  progressPercent: {round(progress)}%",
		f"  progressCount: {controller.progressCount}",
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
	from srxy.i18n import set_language

	set_language("en")
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	controller.setLanguage("en")
	_assert_snapshot("main_window", _chrome_tree(controller))


@pytest.mark.integration
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


def test_given_ignore_editor_states_when_rendered_then_text_tree_matches_snapshot(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	args = build_parser().parse_args(["", str(tmp_path), "--cli"])
	controller = SearchController(args)
	controller.setLanguage("en")
	harness = load_main(controller, qapp)
	try:
		harness.open_dialog_via("filtersButton", "filtersDialog")
		lines = ["filtersDialog.ignoreEditor:"]

		# when
		for state, text in (("empty", ""), ("filled", "*.log\n/build/"), ("invalid", "*.log\n[unclosed")):
			harness.set_text("fltIgnore", text)
			lines.extend(
				[
					f"  {state}:",
					f"    text: {harness.prop('fltIgnore', 'text')!r}",
					f"    example: {harness.prop('fltIgnorePlaceholder', 'text')!r}",
					f"    exampleVisible: {harness.prop('fltIgnorePlaceholder', 'visible')}",
					f"    errorVisible: {harness.prop('fltIgnoreError', 'visible')}",
					f"    okEnabled: {harness.prop('filtersOkButton', 'enabled')}",
				]
			)

		# then
		_assert_snapshot("filters_ignore_editor", "\n".join(lines) + "\n")
	finally:
		harness.shutdown()


def _ignore_tree(controller: SearchController, root: Path) -> str:
	from srxy.adapters.outbound.archive.archive_search import archive_member_path

	t = controller.i18nTr
	json.loads(controller.addIgnoreRule("*.log"))
	filters = json.loads(controller.filtersJson())
	filters.update(ignore_patterns="*.log\n[oops", respect_gitignore=True)
	lines = [
		"filtersDialog.ignoreSection:",
		f"  title: {t('filters.ignore.section')}",
		f"  placeholder: {t('filters.ignore.placeholder')!r}",
		f"  buttons: {t('filters.ignore.add_file')}, {t('filters.ignore.add_folder')}",
		f"  checkbox: {t('filters.ignore.also_respect_gitignore')}",
		f"  hint: {t('filters.ignore.hint')}",
		f"  helpKey: ignore -> {controller.helpText('ignore')[:40]}",
		f"  invalidLineError: {controller.validateIgnorePatterns('*.log' + chr(10) + '[oops')}",
		f"  appliedError: {controller.validateFiltersJson(json.dumps(filters))}",
		f"  summaryAfterAdd: {controller.filtersSummary}",
		"resultContextMenu.ignore:",
		f"  toast: {json.loads(controller.addIgnoreRule('/app/debug.log'))['toast']}",
		f"  toastButtons: {t('gui.toast.undo')}, {t('gui.toast.edit_list')}",
	]
	files = [root / "app" / "debug.log", archive_member_path(root / "data" / "b.zip", "inner/x.txt")]
	for index, path in enumerate(files):
		results = [FileSearchResult(path=path, score=0.9, breakdown={"name": 0.9}, lines=[])]
		controller.handle_search_event_for_tests(SearchFinishedEvent(results=results, skipped_files=[]))
		controller._results_root = root  # pyright: ignore[reportPrivateUsage]
		lines.append(f"  row{index} ({path.name}):")
		for choice in json.loads(controller.resultIgnoreChoicesJson(0)):
			lines.append(f"    - {choice['kind']}: {choice['label']} -> {choice['pattern']}")
	return "\n".join(lines) + "\n"


def test_given_ignore_rules_when_dumping_filters_and_menu_then_matches_snapshot(
	qapp: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	from srxy.i18n import set_language

	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))
	set_language("en")
	args = build_parser().parse_args(["", ".", "--cli"])
	controller = SearchController(args)
	controller.setLanguage("en")

	# when
	tree = _ignore_tree(controller, Path("/work"))

	# then
	_assert_snapshot("filters_ignore", tree)
