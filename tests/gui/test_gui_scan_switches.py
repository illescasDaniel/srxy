"""'Which files to scan' switches live in the Filters dialog (SPEC: ignore-rules, moved switches)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QMetaObject
from tests.gui.helpers import ensure_qapp, load_main

from srxy.adapters.inbound.cli.cli import build_parser
from srxy.adapters.inbound.gui.controller import SearchController
from srxy.application.settings import load_persisted_search_prefs


pytestmark = [pytest.mark.unit, pytest.mark.gui]

_SWITCHES = (
	"include_subdirectories",
	"include_archives",
	"include_hidden",
	"include_noise",
	"include_noise_files",
	"match_skipped_names",
)


@pytest.fixture(scope="module")
def qapp() -> QCoreApplication:
	return ensure_qapp()


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # pyright: ignore[reportUnusedFunction]
	monkeypatch.setenv("SRXY_SKIP_UPDATE_CHECK", "1")
	monkeypatch.setenv("SRXY_SETTINGS_PATH", str(tmp_path / "settings.json"))


def _controller(root: Path) -> SearchController:
	return SearchController(build_parser().parse_args(["alpha", str(root), "--cli"]))


def _switches(controller: SearchController) -> dict[str, bool]:
	options = json.loads(controller.optionsJson())
	return {name: options[name] for name in _SWITCHES}


def _filters_payload(controller: SearchController, **overrides: object) -> str:
	payload = json.loads(controller.filtersJson())
	payload.update(overrides)
	return json.dumps(payload)


def test_given_filters_dialog_when_toggling_switches_and_ok_then_options_updated(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	controller = _controller(tmp_path)
	harness = load_main(controller, qapp)
	try:
		harness.open_dialog_via("filtersButton", "filtersDialog")
		assert bool(harness.prop("fltSubdirs", "checked")) is True

		# when
		harness.set_checked("fltSubdirs", False)
		harness.set_checked("fltHidden", True)
		harness.set_checked("fltArchives", True)
		harness.apply_dialog_ok("filtersOkButton", "filtersDialog")

		# then
		switches = _switches(controller)
		assert switches["include_subdirectories"] is False
		assert switches["include_hidden"] is True
		assert switches["include_archives"] is True
		assert switches["include_noise"] is False
	finally:
		harness.shutdown()


def test_given_toggled_switches_when_cancelling_filters_then_options_unchanged(qapp: QCoreApplication, tmp_path: Path):
	# given
	controller = _controller(tmp_path)
	before = _switches(controller)
	harness = load_main(controller, qapp)
	try:
		harness.open_dialog_via("filtersButton", "filtersDialog")
		harness.set_checked("fltHidden", True)
		harness.set_checked("fltNoise", True)

		# when
		assert QMetaObject.invokeMethod(harness.find("filtersDialog"), "reject")
		harness.wait_until(
			lambda: (
				not (bool(harness.prop("filtersDialog", "opened")) or bool(harness.prop("filtersDialog", "visible")))
			),
			timeout_ms=5_000,
		)

		# then
		assert _switches(controller) == before
		harness.open_dialog_via("filtersButton", "filtersDialog")
		assert bool(harness.prop("fltHidden", "checked")) is False
		assert bool(harness.prop("fltNoise", "checked")) is False
	finally:
		harness.shutdown()


def test_given_non_default_switches_when_pressing_filters_reset_then_defaults_in_draft_until_ok(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	controller = _controller(tmp_path)
	assert (
		controller.applyFiltersJson(
			_filters_payload(controller, include_subdirectories=False, include_hidden=True, match_skipped_names=True)
		)
		== ""
	)
	harness = load_main(controller, qapp)
	try:
		harness.open_dialog_via("filtersButton", "filtersDialog")
		assert bool(harness.prop("fltHidden", "checked")) is True

		# when
		harness.click("fltReset")

		# then
		assert bool(harness.prop("fltSubdirs", "checked")) is True
		assert bool(harness.prop("fltHidden", "checked")) is False
		assert bool(harness.prop("fltMatchSkipped", "checked")) is False
		assert _switches(controller)["include_hidden"] is True
		harness.apply_dialog_ok("filtersOkButton", "filtersDialog")
		assert _switches(controller) == {name: name == "include_subdirectories" for name in _SWITCHES}
	finally:
		harness.shutdown()


def test_given_non_default_switches_when_options_dialog_reset_and_ok_then_switches_untouched(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	controller = _controller(tmp_path)
	assert controller.applyFiltersJson(_filters_payload(controller, include_noise=True, include_archives=True)) == ""
	before = _switches(controller)
	harness = load_main(controller, qapp)
	try:
		harness.open_dialog_via("optionsButton", "optionsDialog")

		# when
		harness.click("optReset")
		harness.apply_dialog_ok("optionsOkButton", "optionsDialog")

		# then
		assert _switches(controller) == before
	finally:
		harness.shutdown()


def test_given_switches_without_remember_filters_when_restarting_then_defaults(qapp: QCoreApplication, tmp_path: Path):
	# given
	controller = _controller(tmp_path)
	payload = _filters_payload(controller, include_hidden=True, include_noise=True, persist_filters=False)
	assert controller.applyFiltersJson(payload) == ""

	# when
	controller.shutdown(thread_wait_ms=100)
	restarted = _controller(tmp_path)

	# then
	assert load_persisted_search_prefs().scan is None
	assert _switches(restarted)["include_hidden"] is False
	assert _switches(restarted)["include_noise"] is False
	restarted.shutdown(thread_wait_ms=100)


def test_given_switches_with_remember_filters_when_restarting_then_restored_without_persisted_options(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	controller = _controller(tmp_path)
	payload = _filters_payload(controller, include_hidden=True, include_subdirectories=False, persist_filters=True)
	assert controller.applyFiltersJson(payload) == ""

	# when
	controller.shutdown(thread_wait_ms=100)
	restarted = _controller(tmp_path)

	# then
	prefs = load_persisted_search_prefs()
	assert prefs.persist_options is False
	assert prefs.options is None
	assert prefs.scan is not None
	switches = _switches(restarted)
	assert switches["include_hidden"] is True
	assert switches["include_subdirectories"] is False
	restarted.shutdown(thread_wait_ms=100)


def test_given_remembered_switches_when_applying_options_with_persist_then_scan_kept_and_not_in_options_blob(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	from srxy.application.settings import load_settings

	controller = _controller(tmp_path)
	assert controller.applyFiltersJson(_filters_payload(controller, include_hidden=True, persist_filters=True)) == ""

	# when
	error = controller.applyOptionsJson(
		json.dumps({**json.loads(controller.defaultOptionsJson()), "search_folders": False, "persist_options": True})
	)
	controller.shutdown(thread_wait_ms=100)

	# then
	assert error == ""
	assert _switches(controller)["include_hidden"] is True
	data = load_settings()
	assert data["scan"]["include_hidden"] is True
	assert "include_hidden" not in data["options"]


def _close_dialog(harness: object, dialog: str, method: str):
	assert QMetaObject.invokeMethod(harness.find(dialog), method)  # pyright: ignore[reportAttributeAccessIssue]
	harness.wait_until(  # pyright: ignore[reportAttributeAccessIssue]
		lambda: not (bool(harness.prop(dialog, "opened")) or bool(harness.prop(dialog, "visible"))),  # pyright: ignore[reportAttributeAccessIssue]
		timeout_ms=5_000,
	)


def test_given_file_names_unticked_when_cancelling_options_then_skipped_names_stays_enabled(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	controller = _controller(tmp_path)
	harness = load_main(controller, qapp)
	try:
		harness.open_dialog_via("optionsButton", "optionsDialog")
		harness.set_checked("optNames", False)

		# when
		_close_dialog(harness, "optionsDialog", "reject")
		harness.open_dialog_via("filtersButton", "filtersDialog")

		# then
		assert bool(harness.prop("fltMatchSkipped", "enabled")) is True
	finally:
		harness.shutdown()


def test_given_file_names_unticked_when_confirming_options_then_skipped_names_is_disabled(
	qapp: QCoreApplication, tmp_path: Path
):
	# given
	controller = _controller(tmp_path)
	harness = load_main(controller, qapp)
	try:
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
