"""Ignore rules in the GUI: controller slots, persistence and QML objects (SPEC: ignore-rules)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtCore import Q_ARG, QCoreApplication, QMetaObject, QObject, QPointF, QUrl
from PySide6.QtQuick import QQuickItem
from tests.gui.helpers import ensure_qapp, load_main

from srxy.adapters.inbound.cli.cli import build_parser
from srxy.adapters.inbound.gui.controller import SearchController
from srxy.adapters.outbound.archive.archive_search import archive_member_path
from srxy.application.search_session import SearchFinishedEvent
from srxy.domain.models import FileSearchResult


pytestmark = [pytest.mark.unit, pytest.mark.gui]


@pytest.fixture(scope="module")
def qapp() -> QCoreApplication:
	return ensure_qapp()


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # pyright: ignore[reportUnusedFunction]
	monkeypatch.setenv("SRXY_SKIP_UPDATE_CHECK", "1")
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))


def _controller(root: Path) -> SearchController:
	args = build_parser().parse_args(["alpha", str(root), "--cli"])
	return SearchController(args)


def _show_results(controller: SearchController, root: Path, paths: list[Path]):
	"""Put result rows in the model and mark ``root`` as the root those results came from."""
	results = [
		FileSearchResult(path=path, score=0.9 - index / 100, breakdown={"name": 0.9}, lines=[])
		for index, path in enumerate(paths)
	]
	controller.handle_search_event_for_tests(SearchFinishedEvent(results=results, skipped_files=[]))
	# startSearch snapshots the root of the displayed results; tests skip the real search.
	controller._results_root = root  # pyright: ignore[reportPrivateUsage]


def _filters_payload(controller: SearchController, **overrides: object) -> str:
	payload = json.loads(controller.filtersJson())
	payload.update(overrides)
	return json.dumps(payload)


def _ignore_text(controller: SearchController) -> str:
	return json.loads(controller.filtersJson())["ignore_patterns"]


def _choices(controller: SearchController, row: int) -> list[dict[str, str]]:
	return json.loads(controller.resultIgnoreChoicesJson(row))


def _choice_by_kind(controller: SearchController, row: int, kind: str) -> dict[str, str]:
	matching = [choice for choice in _choices(controller, row) if choice["kind"] == kind]
	assert len(matching) == 1, (kind, _choices(controller, row))
	return matching[0]


def _persisted_filters():
	from srxy.application.settings import load_persisted_search_prefs

	return load_persisted_search_prefs().filters


class _SignalCounter:
	def __init__(self, signal):
		self.count = 0
		signal.connect(self._bump)

	def _bump(self):
		self.count += 1


# --- validation --------------------------------------------------------------------------------


def test_given_invalid_pattern_on_line_2_when_validating_then_message_names_line_2(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	controller = _controller(tmp_path)

	# when
	message = controller.validateIgnorePatterns("*.log\n[oops")

	# then
	assert message
	assert "2" in message


def test_given_valid_patterns_when_validating_then_returns_empty_string(qapp: QCoreApplication, tmp_path: Path):
	# given
	controller = _controller(tmp_path)

	# when
	message = controller.validateIgnorePatterns("# note\n\n*.log\n!keep.log\n/build/\n")

	# then
	assert message == ""


def test_given_empty_text_when_validating_then_returns_empty_string(qapp: QCoreApplication, tmp_path: Path):
	# given
	controller = _controller(tmp_path)

	# when / then
	assert controller.validateIgnorePatterns("") == ""


def test_given_1001_lines_when_validating_then_returns_error(qapp: QCoreApplication, tmp_path: Path):
	# given
	controller = _controller(tmp_path)

	# when
	message = controller.validateIgnorePatterns("\n".join(f"p{i}" for i in range(1001)))

	# then
	assert message


def test_given_1000_lines_when_validating_then_returns_empty_string(qapp: QCoreApplication, tmp_path: Path):
	# given
	controller = _controller(tmp_path)

	# when
	message = controller.validateIgnorePatterns("\n".join(f"p{i}" for i in range(1000)))

	# then
	assert message == ""


def test_given_line_over_1024_chars_when_validating_then_returns_error(qapp: QCoreApplication, tmp_path: Path):
	# given
	controller = _controller(tmp_path)

	# when
	message = controller.validateIgnorePatterns("a" * 1025)

	# then
	assert message


# --- filters payload ---------------------------------------------------------------------------


def test_given_default_controller_when_reading_filters_json_then_has_ignore_keys(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	controller = _controller(tmp_path)

	# when
	current = json.loads(controller.filtersJson())
	defaults = json.loads(controller.defaultFiltersJson())

	# then
	assert current["ignore_patterns"] == ""
	assert current["respect_gitignore"] is False
	assert defaults["ignore_patterns"] == ""
	assert defaults["respect_gitignore"] is False


def test_given_ignore_payload_when_applying_filters_json_then_stores_both_values(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	controller = _controller(tmp_path)
	payload = _filters_payload(controller, ignore_patterns="*.log\n/build/", respect_gitignore=True)

	# when
	error = controller.applyFiltersJson(payload)

	# then
	assert error == ""
	stored = json.loads(controller.filtersJson())
	assert stored["ignore_patterns"] == "*.log\n/build/"
	assert stored["respect_gitignore"] is True


def test_given_invalid_pattern_when_applying_filters_json_then_rejects_without_saving(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	controller = _controller(tmp_path)
	before = controller.filtersJson()
	payload = _filters_payload(controller, ignore_patterns="*.log\n[oops", respect_gitignore=True)

	# when
	error = controller.applyFiltersJson(payload)

	# then
	assert error
	assert controller.filtersJson() == before
	assert not (tmp_path / "settings.json").exists()


def test_given_invalid_pattern_when_validating_filters_json_then_returns_error(qapp: QCoreApplication, tmp_path: Path):
	# given
	controller = _controller(tmp_path)
	payload = _filters_payload(controller, ignore_patterns="[oops")

	# when
	error = controller.validateFiltersJson(payload)

	# then
	assert error


def test_given_rules_and_checkbox_when_default_filters_applied_then_list_empty_and_unticked(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	controller = _controller(tmp_path)
	assert (
		controller.applyFiltersJson(_filters_payload(controller, ignore_patterns="*.log", respect_gitignore=True)) == ""
	)

	# when — Reset in the dialog loads defaultFiltersJson into the draft, OK applies it
	defaults = json.loads(controller.defaultFiltersJson())
	error = controller.applyFiltersJson(json.dumps(defaults))

	# then
	assert error == ""
	stored = json.loads(controller.filtersJson())
	assert stored["ignore_patterns"] == ""
	assert stored["respect_gitignore"] is False


def test_given_three_patterns_and_gitignore_when_applied_then_summary_reads_ignoring_3_patterns(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	from srxy.i18n import set_language

	set_language("en")
	controller = _controller(tmp_path)

	# when
	error = controller.applyFiltersJson(
		_filters_payload(controller, ignore_patterns="*.log\n# note\n/build/\n!keep.log", respect_gitignore=True)
	)

	# then
	assert error == ""
	assert "ignoring 3 patterns (+.gitignore)" in str(controller.filtersSummary)


# --- persistence -------------------------------------------------------------------------------


def test_given_remember_filters_on_when_applying_ignore_rules_then_persisted_and_restored(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	controller = _controller(tmp_path)
	payload = _filters_payload(
		controller, ignore_patterns="*.log\n/build/", respect_gitignore=True, persist_filters=True
	)

	# when
	assert controller.applyFiltersJson(payload) == ""
	restarted = _controller(tmp_path)

	# then
	filters = _persisted_filters()
	assert filters is not None
	assert filters.ignore_patterns == "*.log\n/build/"
	assert filters.respect_gitignore is True
	restored = json.loads(restarted.filtersJson())
	assert restored["ignore_patterns"] == "*.log\n/build/"
	assert restored["respect_gitignore"] is True


def test_given_remember_filters_off_when_applying_ignore_rules_then_not_persisted_but_kept_in_session(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	controller = _controller(tmp_path)
	payload = _filters_payload(controller, ignore_patterns="*.log", respect_gitignore=True, persist_filters=False)

	# when
	assert controller.applyFiltersJson(payload) == ""
	restarted = _controller(tmp_path)

	# then
	assert _ignore_text(controller) == "*.log"
	assert _persisted_filters() is None
	restored = json.loads(restarted.filtersJson())
	assert restored["ignore_patterns"] == ""
	assert restored["respect_gitignore"] is False


# --- ignoring from a result row ----------------------------------------------------------------


def test_given_result_row_when_listing_choices_then_offers_file_folder_and_extension(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	(tmp_path / "app").mkdir()
	controller = _controller(tmp_path)
	_show_results(controller, tmp_path, [tmp_path / "app" / "debug.log"])

	# when
	choices = _choices(controller, 0)

	# then
	assert {choice["kind"] for choice in choices} == {"file", "folder", "ext"}
	assert _choice_by_kind(controller, 0, "file")["pattern"] == "/app/debug.log"
	assert _choice_by_kind(controller, 0, "folder")["pattern"] == "/app/"
	assert _choice_by_kind(controller, 0, "ext")["pattern"] == "*.log"
	assert all(choice["label"] for choice in choices)


def test_given_nested_folder_when_choosing_ignore_folder_then_pattern_is_anchored(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	(tmp_path / "app" / "logs").mkdir(parents=True)
	controller = _controller(tmp_path)
	_show_results(controller, tmp_path, [tmp_path / "app" / "logs" / "debug.log"])

	# when
	pattern = _choice_by_kind(controller, 0, "folder")["pattern"]
	controller.addIgnoreRule(pattern)

	# then
	assert pattern == "/app/logs/"
	assert _ignore_text(controller) == "/app/logs/"


def test_given_result_row_when_ignoring_file_then_appends_rule_and_keeps_results(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	(tmp_path / "app").mkdir()
	controller = _controller(tmp_path)
	_show_results(controller, tmp_path, [tmp_path / "app" / "debug.log", tmp_path / "app" / "other.txt"])
	assert controller.applyFiltersJson(_filters_payload(controller, ignore_patterns="*.tmp")) == ""
	rows_before = controller.resultsModel.rowCount()
	summary_signal = _SignalCounter(controller.filtersSummaryChanged)

	# when
	reply = json.loads(controller.addIgnoreRule("/app/debug.log"))

	# then
	assert reply["added"] is True
	assert reply["toast"]
	assert _ignore_text(controller) == "*.tmp\n/app/debug.log"
	assert controller.resultsModel.rowCount() == rows_before
	assert summary_signal.count >= 1


def test_given_added_rule_when_undoing_then_removes_only_that_rule_and_persists(qapp: QCoreApplication, tmp_path: Path):
	# given
	controller = _controller(tmp_path)
	payload = _filters_payload(controller, ignore_patterns="*.tmp\n/build/", persist_filters=True)
	assert controller.applyFiltersJson(payload) == ""
	controller.addIgnoreRule("/app/debug.log")
	assert _ignore_text(controller) == "*.tmp\n/build/\n/app/debug.log"
	filters = _persisted_filters()
	assert filters is not None
	assert filters.ignore_patterns == "*.tmp\n/build/\n/app/debug.log"

	# when
	controller.undoLastIgnoreRule()

	# then
	assert _ignore_text(controller) == "*.tmp\n/build/"
	filters = _persisted_filters()
	assert filters is not None
	assert filters.ignore_patterns == "*.tmp\n/build/"


def test_given_nothing_added_when_undoing_then_list_is_unchanged(qapp: QCoreApplication, tmp_path: Path):
	# given
	controller = _controller(tmp_path)
	assert controller.applyFiltersJson(_filters_payload(controller, ignore_patterns="*.tmp")) == ""

	# when
	controller.undoLastIgnoreRule()

	# then
	assert _ignore_text(controller) == "*.tmp"


def test_given_existing_rule_when_ignoring_again_then_list_is_unchanged(qapp: QCoreApplication, tmp_path: Path):
	# given
	controller = _controller(tmp_path)
	assert controller.applyFiltersJson(_filters_payload(controller, ignore_patterns="*.log")) == ""

	# when
	reply = json.loads(controller.addIgnoreRule("*.log"))

	# then
	assert reply["added"] is False
	assert _ignore_text(controller) == "*.log"


def test_given_duplicate_add_when_undoing_then_original_rule_is_kept(qapp: QCoreApplication, tmp_path: Path):
	# given
	controller = _controller(tmp_path)
	assert controller.applyFiltersJson(_filters_payload(controller, ignore_patterns="*.log")) == ""
	controller.addIgnoreRule("*.log")

	# when
	controller.undoLastIgnoreRule()

	# then
	assert _ignore_text(controller) == "*.log"


def test_given_archive_member_row_when_listing_choices_then_only_archive_is_offered(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	archive = tmp_path / "data" / "bundle.zip"
	archive.parent.mkdir()
	archive.write_bytes(b"")
	controller = _controller(tmp_path)
	_show_results(controller, tmp_path, [archive_member_path(archive, "inner/readme.txt")])

	# when
	choices = _choices(controller, 0)

	# then
	assert [choice["kind"] for choice in choices] == ["archive"]
	assert choices[0]["pattern"] == "/data/bundle.zip"


def test_given_folder_result_row_when_listing_choices_then_offers_this_folder(qapp: QCoreApplication, tmp_path: Path):
	# given
	(tmp_path / "app" / "logs").mkdir(parents=True)
	controller = _controller(tmp_path)
	results = [FileSearchResult(path=tmp_path / "app" / "logs", score=0.9, breakdown={"name": 0.9}, is_dir=True)]
	controller.handle_search_event_for_tests(SearchFinishedEvent(results=results, skipped_files=[]))
	controller._results_root = tmp_path  # pyright: ignore[reportPrivateUsage]

	# when
	choices = _choices(controller, 0)

	# then
	assert [choice["kind"] for choice in choices] == ["this_folder"]
	assert choices[0]["pattern"] == "/app/logs/"


# --- picking paths -----------------------------------------------------------------------------


def test_given_folder_inside_root_when_picking_then_returns_text_with_anchored_folder_rule(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	picked = tmp_path / "src" / "old"
	picked.mkdir(parents=True)
	controller = _controller(tmp_path)

	# when
	reply = json.loads(controller.ignorePatternForPick(QUrl.fromLocalFile(str(picked)).toString(), True, "*.log"))

	# then
	assert "error" not in reply
	assert reply["text"].splitlines() == ["*.log", "/src/old/"]
	assert _ignore_text(controller) == ""


def test_given_empty_text_when_picking_file_inside_root_then_returns_only_that_rule(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	picked = tmp_path / "notes.txt"
	picked.write_text("x", encoding="utf-8")
	controller = _controller(tmp_path)

	# when
	reply = json.loads(controller.ignorePatternForPick(QUrl.fromLocalFile(str(picked)).toString(), False, ""))

	# then
	assert reply["text"].strip() == "/notes.txt"


def test_given_path_outside_root_when_picking_then_returns_error_and_adds_nothing(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	root = tmp_path / "work"
	root.mkdir()
	outside = tmp_path / "other" / "x"
	outside.mkdir(parents=True)
	controller = _controller(root)

	# when
	reply = json.loads(controller.ignorePatternForPick(QUrl.fromLocalFile(str(outside)).toString(), True, "*.log"))

	# then
	assert reply["error"]
	assert "text" not in reply
	assert _ignore_text(controller) == ""


# --- QML objects -------------------------------------------------------------------------------


def test_given_main_window_when_opening_filters_dialog_then_has_ignore_controls(qapp: QCoreApplication, tmp_path: Path):
	# given
	controller = _controller(tmp_path)
	harness = load_main(controller, qapp)
	try:
		# when
		harness.open_dialog_via("filtersButton", "filtersDialog")

		# then
		assert harness.find("fltIgnore") is not None
		assert harness.find("fltRespectGitignore") is not None
	finally:
		harness.shutdown()


def test_given_invalid_ignore_text_when_typing_in_dialog_then_ok_disabled_and_error_shown(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	controller = _controller(tmp_path)
	harness = load_main(controller, qapp)
	try:
		harness.open_dialog_via("filtersButton", "filtersDialog")
		assert bool(harness.prop("filtersOkButton", "enabled")) is True

		# when
		harness.set_text("fltIgnore", "*.log\n[oops")

		# then
		assert bool(harness.prop("filtersOkButton", "enabled")) is False
		assert bool(harness.prop("fltIgnoreError", "visible")) is True
		assert "2" in str(harness.prop("fltIgnoreError", "text"))
		assert bool(harness.prop("fltIgnore", "invalid")) is True
	finally:
		harness.shutdown()


def test_given_ignore_text_and_checkbox_when_pressing_ok_then_controller_filters_updated(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	controller = _controller(tmp_path)
	harness = load_main(controller, qapp)
	try:
		harness.open_dialog_via("filtersButton", "filtersDialog")

		# when
		harness.set_text("fltIgnore", "*.log\n/build/")
		harness.set_checked("fltRespectGitignore", True)
		harness.apply_dialog_ok("filtersOkButton", "filtersDialog")

		# then
		stored = json.loads(controller.filtersJson())
		assert stored["ignore_patterns"] == "*.log\n/build/"
		assert stored["respect_gitignore"] is True
	finally:
		harness.shutdown()


def test_given_filled_ignore_list_when_pressing_reset_then_box_empty_and_checkbox_unticked(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	controller = _controller(tmp_path)
	assert (
		controller.applyFiltersJson(_filters_payload(controller, ignore_patterns="*.log", respect_gitignore=True)) == ""
	)
	harness = load_main(controller, qapp)
	try:
		harness.open_dialog_via("filtersButton", "filtersDialog")
		assert str(harness.prop("fltIgnore", "text")) == "*.log"

		# when
		harness.click("fltReset")

		# then
		assert str(harness.prop("fltIgnore", "text")) == ""
		assert bool(harness.prop("fltRespectGitignore", "checked")) is False
	finally:
		harness.shutdown()


def test_given_main_window_when_loaded_then_toast_and_result_menu_exist_without_qml_errors(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	(tmp_path / "app").mkdir()
	controller = _controller(tmp_path)
	harness = load_main(controller, qapp)
	try:
		_show_results(controller, tmp_path, [tmp_path / "app" / "debug.log"])
		qapp.processEvents()

		# when
		reply = json.loads(controller.addIgnoreRule("/app/debug.log"))
		qapp.processEvents()

		# then
		assert reply["added"] is True
		assert harness.find("toast") is not None
		assert harness.find("resultContextMenu") is not None
	finally:
		harness.shutdown()


def test_given_toast_showing_when_pressing_edit_list_then_filters_dialog_opens_on_ignore_box(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	controller = _controller(tmp_path)
	harness = load_main(controller, qapp)
	try:
		assert QMetaObject.invokeMethod(
			harness.window, "showIgnoreToast", Q_ARG("QVariant", "Ignoring *.log"), Q_ARG("QVariant", True)
		)
		qapp.processEvents()
		assert bool(harness.prop("toast", "visible")) is True

		# when
		harness.click("toastEditList")

		# then
		harness.wait_until(lambda: bool(harness.prop("filtersDialog", "opened")), timeout_ms=5_000)
		harness.wait_until(lambda: bool(harness.prop("fltIgnore", "activeFocus")), timeout_ms=5_000)
		assert bool(harness.prop("toast", "visible")) is False
	finally:
		harness.shutdown()


def test_given_toast_showing_when_pressing_undo_then_last_rule_removed(qapp: QCoreApplication, tmp_path: Path):
	# given
	controller = _controller(tmp_path)
	harness = load_main(controller, qapp)
	try:
		reply = json.loads(controller.addIgnoreRule("*.log"))
		assert reply["added"] is True
		assert QMetaObject.invokeMethod(
			harness.window, "showIgnoreToast", Q_ARG("QVariant", reply["toast"]), Q_ARG("QVariant", True)
		)
		qapp.processEvents()

		# when
		harness.click("toastUndo")

		# then
		assert _ignore_text(controller) == ""
		assert bool(harness.prop("toast", "visible")) is False
	finally:
		harness.shutdown()


_SCAN_LABEL_KEYS = (
	"gui.options.which_files",
	"gui.options.noisy",
	"gui.options.hidden",
	"gui.options.noise",
	"gui.options.noise_files",
	"gui.options.match_skipped",
	"gui.options.subdirs",
	"gui.options.archives",
)


def _texts_under(root: QObject) -> set[str]:
	"""Every non-empty ``text`` property in the QML item subtree below ``root``."""
	found: set[str] = set()
	stack: list[QObject] = [root]
	while stack:
		node = stack.pop()
		text = node.property("text")
		if isinstance(text, str) and text:
			found.add(text)
		if isinstance(node, QQuickItem):
			stack.extend(node.childItems())
		stack.extend(node.children())
	return found


def _menu_item_at(menu: QObject, index: int) -> object:
	from PySide6.QtCore import Q_RETURN_ARG

	return QMetaObject.invokeMethod(menu, "itemAt", Q_RETURN_ARG("QQuickItem*"), Q_ARG("int", index))


def _dialog_texts(harness, dialog_name: str) -> set[str]:
	dialog = harness.find(dialog_name)
	texts: set[str] = set()
	for part in ("contentItem", "header", "footer"):
		item = dialog.property(part)
		if isinstance(item, QObject):
			texts |= _texts_under(item)
	return texts


def test_given_main_window_when_comparing_dialogs_then_scan_switches_only_in_filters(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	from srxy.i18n import tr as t

	controller = _controller(tmp_path)
	harness = load_main(controller, qapp)
	try:
		harness.open_dialog_via("filtersButton", "filtersDialog")
		filters_texts = _dialog_texts(harness, "filtersDialog")
		QMetaObject.invokeMethod(harness.find("filtersDialog"), "close")
		harness.wait_until(lambda: not bool(harness.prop("filtersDialog", "visible")), timeout_ms=5_000)
		harness.open_dialog_via("optionsButton", "optionsDialog")

		# when
		options_texts = _dialog_texts(harness, "optionsDialog")

		# then
		labels = [t(key) for key in _SCAN_LABEL_KEYS]
		assert all(label in filters_texts for label in labels), [x for x in labels if x not in filters_texts]
		assert not [label for label in labels if label in options_texts]
		assert options_texts, "options dialog subtree walk found nothing"
	finally:
		harness.shutdown()


def test_given_result_row_when_adding_ignore_from_row_then_toast_shows_message_and_undo(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	from srxy.i18n import tr as t

	(tmp_path / "app").mkdir()
	controller = _controller(tmp_path)
	harness = load_main(controller, qapp)
	try:
		_show_results(controller, tmp_path, [tmp_path / "app" / "debug.log"])
		pattern = _choice_by_kind(controller, 0, "file")["pattern"]
		assert bool(harness.prop("toast", "visible")) is False

		# when
		assert QMetaObject.invokeMethod(harness.window, "addIgnoreFromRow", Q_ARG("QVariant", pattern))
		qapp.processEvents()

		# then
		assert bool(harness.prop("toast", "visible")) is True
		assert str(harness.prop("toastMessage", "text")) == t("gui.toast.ignoring", pattern=pattern)
		assert str(harness.prop("toastMessage", "text")).startswith("Ignoring \u201c")
		assert bool(harness.prop("toastUndo", "visible")) is True
		assert pattern in _ignore_text(controller)
	finally:
		harness.shutdown()


def test_given_result_menu_choices_when_triggering_ignore_item_then_toast_shows(qapp: QCoreApplication, tmp_path: Path):
	# given
	(tmp_path / "app").mkdir()
	controller = _controller(tmp_path)
	harness = load_main(controller, qapp)
	try:
		_show_results(controller, tmp_path, [tmp_path / "app" / "debug.log"])
		choice = _choice_by_kind(controller, 0, "file")
		harness.set_prop("resultContextMenu", "ignoreChoices", _choices(controller, 0))
		qapp.processEvents()
		menu = harness.find("resultContextMenu")
		items = [
			child
			for index in range(int(menu.property("count")))
			if isinstance(child := _menu_item_at(menu, index), QObject)
		]
		item = next(child for child in items if child.objectName() == "resultIgnore_file")

		# when
		QMetaObject.invokeMethod(item, "triggered")
		qapp.processEvents()

		# then
		assert bool(harness.prop("toast", "visible")) is True
		assert choice["pattern"] in str(harness.prop("toastMessage", "text"))
		assert choice["pattern"] in _ignore_text(controller)
	finally:
		harness.shutdown()


def test_given_search_names_committed_off_when_filters_dialog_open_then_skipped_names_disabled(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	controller = _controller(tmp_path)
	harness = load_main(controller, qapp)
	try:
		harness.open_dialog_via("filtersButton", "filtersDialog")
		assert bool(harness.prop("fltMatchSkipped", "enabled")) is True
		harness.apply_dialog_ok("filtersOkButton", "filtersDialog")
		harness.open_dialog_via("optionsButton", "optionsDialog")
		harness.set_checked("optNames", False)
		harness.set_checked("optContents", True)

		# when
		harness.apply_dialog_ok("optionsOkButton", "optionsDialog")
		harness.open_dialog_via("filtersButton", "filtersDialog")

		# then
		assert bool(harness.prop("fltMatchSkipped", "enabled")) is False
	finally:
		harness.shutdown()


def test_given_filters_dialog_when_laid_out_then_ignore_section_precedes_limits_fields(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	controller = _controller(tmp_path)
	harness = load_main(controller, qapp)
	try:
		# when
		harness.open_dialog_via("filtersButton", "filtersDialog")

		# then
		def scene_y(name: str) -> float:
			item = harness.find(name)
			assert isinstance(item, QQuickItem)
			return item.mapToScene(QPointF(0, 0)).y()

		assert scene_y("fltIgnoreSection") < scene_y("fltSubdirs") < scene_y("fltMaxMatches")
		assert harness.find("fltIgnoreHint") is not None
	finally:
		harness.shutdown()


def test_given_short_window_and_scrolled_down_when_pressing_edit_list_then_ignore_section_is_visible(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	controller = _controller(tmp_path)
	harness = load_main(controller, qapp)
	try:
		harness.window.setProperty("height", 420)
		qapp.processEvents()
		harness.open_dialog_via("filtersButton", "filtersDialog")
		flick = harness.prop("fltScroll", "contentItem")
		flick.setProperty(
			"contentY", max(0.0, float(flick.property("contentHeight")) - float(flick.property("height")))
		)
		qapp.processEvents()
		assert float(flick.property("contentY")) > float(harness.prop("fltIgnoreSection", "y"))
		assert QMetaObject.invokeMethod(harness.find("filtersDialog"), "close")
		harness.wait_until(lambda: not bool(harness.prop("filtersDialog", "visible")), timeout_ms=5_000)
		assert QMetaObject.invokeMethod(
			harness.window, "showIgnoreToast", Q_ARG("QVariant", "Ignoring"), Q_ARG("QVariant", True)
		)
		qapp.processEvents()

		# when
		harness.click("toastEditList")

		# then
		section_y = float(harness.prop("fltIgnoreSection", "y"))
		height = float(flick.property("height"))
		harness.wait_until(
			lambda: float(flick.property("contentY")) <= section_y < float(flick.property("contentY")) + height,
			timeout_ms=5_000,
		)
		content_y = float(flick.property("contentY"))
		assert content_y <= section_y < content_y + height
	finally:
		harness.shutdown()


@pytest.mark.parametrize(
	"existing, pattern",
	[
		("\n".join(f"/p{index}" for index in range(1000)), "/one-too-many"),
		("*.tmp", "/" + "x" * 1030),
	],
	ids=["1001st-line", "line-over-1024-chars"],
)
def test_given_rule_breaking_caps_when_adding_then_error_toast_and_nothing_added(
	qapp: QCoreApplication, tmp_path: Path, existing: str, pattern: str
):
	# given
	controller = _controller(tmp_path)
	assert controller.applyFiltersJson(_filters_payload(controller, ignore_patterns=existing)) == ""

	# when
	reply = json.loads(controller.addIgnoreRule(pattern))

	# then
	assert reply["added"] is False
	assert pattern not in reply["toast"]
	assert _ignore_text(controller) == existing
