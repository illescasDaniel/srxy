from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from tests.tui.helpers import assert_labels_visible, assert_svg_snapshot
from textual.widgets import Checkbox, DataTable

from srxy.adapters.inbound.cli.cli import build_parser
from srxy.adapters.inbound.tui.app import SrxyApp
from srxy.adapters.inbound.tui.modals import SearchFiltersModal, SearchOptionsModal
from srxy.application.search_options import format_search_options_summary
from srxy.domain.models import FileSearchResult, LineMatch


pytestmark = [pytest.mark.integration, pytest.mark.tui]


def _build_app(*, argv: list[str], theme: str = "textual-light", auto_start: bool = False) -> SrxyApp:
	args = build_parser().parse_args(argv)
	app = SrxyApp(args, auto_start=auto_start)
	app.theme = theme
	return app


def test_given_tui_when_search_options_toggled_then_search_becomes_stale(tmp_path: Path):
	# given
	app = _build_app(argv=["hello", str(tmp_path)])

	async def run():
		async with app.run_test(size=(100, 30)) as pilot:
			await pilot.pause()
			button = app.query_one("#search-button")
			assert not app.search_options.ocr
			await pilot.click("#search-options-button")
			await pilot.pause()
			assert isinstance(app.screen, SearchOptionsModal)
			modal = app.screen
			modal.query_one("#so-ocr", Checkbox).focus()
			await pilot.press("space")
			await pilot.pause()
			await pilot.click("#search-options-apply")
			await pilot.pause()
			assert app.search_options.ocr
			assert button.has_class("-stale")
			svg = app.export_screenshot(title="srxy-tui-ocr-toggle")
			assert_labels_visible(svg, ("Search options", "Search"))

	asyncio.run(run())


def test_given_uppercase_readme_when_tui_names_search_completes_then_lists_file(tmp_path: Path):
	# given — real engine path; query case must not drop README.md
	(tmp_path / "README.md").write_text("docs without matching body text\n", encoding="utf-8")
	(tmp_path / "notes.txt").write_text("unrelated\n", encoding="utf-8")
	args = build_parser().parse_args(["README", str(tmp_path), "--names-only"])
	app = SrxyApp(args, auto_start=True)
	app.theme = "textual-light"

	async def run():
		with patch("srxy.adapters.inbound.tui.app.run_tui_preflight", new=AsyncMock(return_value=None)):
			async with app.run_test(size=(100, 30)) as pilot:
				table = app.query_one("#results-table", DataTable)
				for _ in range(60):
					await pilot.pause(delay=0.05)
					if table.row_count >= 1:
						break
					table = app.query_one("#results-table", DataTable)
				assert table.row_count >= 1
				assert app.exit_code == 0
				paths = [str(table.get_row_at(row)[1]) for row in range(table.row_count)]
				assert any(path.endswith("README.md") for path in paths)

	# when / then
	asyncio.run(run())


def test_given_name_match_when_tui_results_rendered_then_snapshot_includes_readme():
	# given — fixed path so SVG text snapshots stay stable across runs
	file_path = Path("/fixture/docs/README.md")
	result = FileSearchResult(
		path=file_path,
		score=0.92,
		breakdown={"name": 0.92},
		lines=[],
	)
	args = build_parser().parse_args(["README", "/fixture/docs", "--names-only"])
	app = SrxyApp(args, auto_start=True)
	app.theme = "textual-light"

	async def run():
		with (
			patch("srxy.adapters.inbound.tui.app.run_tui_preflight", new=AsyncMock(return_value=None)),
			patch("srxy.application.search_runner.execute_search", return_value=([result], [])),
		):
			async with app.run_test(size=(100, 30)) as pilot:
				for _ in range(30):
					await pilot.pause(delay=0.05)
					if app.query_one("#results-table", DataTable).row_count == 1:
						break
				svg = app.export_screenshot(title="srxy-tui-readme-name-hit")
				assert_labels_visible(svg, ("README.md", "Match", "Path", "filename"))
				assert_svg_snapshot("srxy_app_readme_name_hit_textual-light", svg)

	# when / then
	asyncio.run(run())


def test_given_completed_search_when_query_edited_then_search_button_becomes_stale(tmp_path: Path):
	# given
	file_path = tmp_path / "notes.txt"
	file_path.write_text("hello world", encoding="utf-8")
	result = FileSearchResult(
		path=file_path,
		score=0.85,
		breakdown={"content": 0.85},
		lines=[LineMatch(line_number=1, text="hello world", score=0.85)],
	)
	args = build_parser().parse_args(["hello", str(tmp_path), "--content-only"])
	app = SrxyApp(args, auto_start=True)

	async def run():
		with (
			patch("srxy.adapters.inbound.tui.app.run_tui_preflight", new=AsyncMock(return_value=None)),
			patch("srxy.application.search_runner.execute_search", return_value=([result], [])),
		):
			async with app.run_test(size=(100, 40)) as pilot:
				button = app.query_one("#search-button")
				for _ in range(30):
					await pilot.pause(delay=0.05)
					if not button.has_class("-stale"):
						break
				await pilot.click("#search-options-button")
				await pilot.pause()
				modal = app.screen
				assert isinstance(modal, SearchOptionsModal)
				from textual.widgets import Checkbox

				modal.query_one("#so-semantic", Checkbox).value = True
				await pilot.pause()
				from srxy.application.search_options import SearchOptions

				modal.dismiss(
					SearchOptions(
						search_names=False,
						search_contents=True,
						search_docs_tags=True,
						semantic=True,
					)
				)
				await pilot.pause()
				assert button.has_class("-stale")

	asyncio.run(run())


def test_given_ocr_result_when_preview_rendered_then_location_and_text_visible(tmp_path: Path):
	# given
	file_path = tmp_path / "scan.png"
	file_path.write_bytes(b"\x89PNG\r\n\x1a\n")
	result = FileSearchResult(
		path=file_path,
		score=0.9,
		breakdown={"ocr": 0.9},
		lines=[LineMatch(line_number=1, text="fixture_ocr_token found", score=0.9, location_kind="ocr")],
	)
	args = build_parser().parse_args(["fixture_ocr", str(tmp_path), "--ocr", "--content-only"])
	app = SrxyApp(args, auto_start=True)

	async def run():
		with (
			patch("srxy.adapters.inbound.tui.app.run_tui_preflight", new=AsyncMock(return_value=None)),
			patch("srxy.application.search_runner.execute_search", return_value=([result], [])),
		):
			async with app.run_test(size=(100, 30)) as pilot:
				for _ in range(30):
					await pilot.pause(delay=0.05)
					if app.query_one("#results-table", DataTable).row_count == 1:
						break
				svg = app.export_screenshot(title="srxy-tui-ocr-preview")
				assert_labels_visible(svg, ("Location", "Text", "ocr"))

	asyncio.run(run())


def test_given_transcript_result_when_preview_rendered_then_transcript_visible(tmp_path: Path):
	# given
	file_path = tmp_path / "speech.wav"
	file_path.write_text("audio", encoding="utf-8")
	result = FileSearchResult(
		path=file_path,
		score=0.8,
		breakdown={"transcript": 0.8},
		lines=[LineMatch(line_number=1, text="thank you very much", score=0.8, location_kind="transcript")],
	)
	args = build_parser().parse_args(["thank you", str(tmp_path), "--transcribe", "--content-only"])
	app = SrxyApp(args, auto_start=True)

	async def run():
		with (
			patch("srxy.adapters.inbound.tui.app.run_tui_preflight", new=AsyncMock(return_value=None)),
			patch("srxy.application.search_runner.execute_search", return_value=([result], [])),
		):
			async with app.run_test(size=(100, 30)) as pilot:
				for _ in range(30):
					await pilot.pause(delay=0.05)
					if app.query_one("#results-table", DataTable).row_count == 1:
						break
				svg = app.export_screenshot(title="srxy-tui-transcript-preview")
				visible = svg.lower()
				assert "transcript" in visible or "thank you" in visible

	asyncio.run(run())


@pytest.mark.integration_full
@pytest.mark.semantic
def test_given_semantic_image_flag_when_search_completes_then_results_table_populated():
	# given
	from tests.helpers import file_search_root, require_file_search_fixtures

	require_file_search_fixtures()
	root = file_search_root()
	file_path = root / "portrait.jpg"
	result = FileSearchResult(
		path=file_path,
		score=0.75,
		breakdown={"semantic_image": 0.75},
		lines=[LineMatch(line_number=1, text="person", score=0.75, location_kind="semantic_image")],
	)
	args = build_parser().parse_args(["person", str(root), "--semantic-image", "--content-only"])
	app = SrxyApp(args, auto_start=True)

	async def run():
		with (
			patch("srxy.adapters.inbound.tui.app.run_tui_preflight", new=AsyncMock(return_value=None)),
			patch("srxy.application.search_session.search_uses_subprocess", return_value=False),
			patch("srxy.application.search_runner.execute_search", return_value=([result], [])),
		):
			async with app.run_test(size=(120, 40)) as pilot:
				for _ in range(30):
					await pilot.pause(delay=0.05)
					if app.query_one("#results-table", DataTable).row_count >= 1:
						break
				assert app.query_one("#results-table", DataTable).row_count >= 1
				svg = app.export_screenshot(title="srxy-tui-semantic-image")
				assert_labels_visible(svg, ("Search", "Search options"))

	asyncio.run(run())


def test_given_semantic_transcribe_ocr_flags_when_launched_then_search_options_reflect_args():
	# given
	app = _build_app(argv=["test", ".", "--semantic-all"])

	async def run():
		async with app.run_test(size=(100, 30)) as pilot:
			await pilot.pause()
			assert app.search_options.semantic
			assert app.search_options.semantic_image
			assert app.search_options.ocr
			assert app.search_options.transcribe
			summary = format_search_options_summary(app.search_options)
			assert "How:" in summary
			assert "Meaning" in summary
			assert "Speech" in summary
			assert "Image text" in summary

	asyncio.run(run())


def test_given_tui_when_search_filters_applied_then_search_becomes_stale(tmp_path: Path):
	# given
	app = _build_app(argv=["hello", str(tmp_path)])

	async def run():
		async with app.run_test(size=(120, 40)) as pilot:
			await pilot.pause()
			button = app.query_one("#search-button")
			await pilot.click("#search-filters-button")
			await pilot.pause()
			assert isinstance(app.screen, SearchFiltersModal)
			app.screen.query_one("#sf-size-text").value = "200"
			await pilot.click("#search-filters-apply")
			await pilot.pause()
			assert app.search_filters.size_limits.text_mib == "200"
			assert button.has_class("-stale")

	asyncio.run(run())


def test_given_cli_size_flags_when_opening_filters_dialog_then_shows_applied_limits(tmp_path: Path):
	# given
	app = _build_app(
		argv=[
			"hello",
			str(tmp_path),
			"--max-file-size",
			"0",
			"--max-ocr-file-size",
			str(100 * 1024 * 1024),
			"--max-transcribe-file-size",
			str(250 * 1024 * 1024),
		]
	)

	async def run():
		async with app.run_test(size=(120, 40)) as pilot:
			await pilot.pause()
			await pilot.click("#search-filters-button")
			await pilot.pause()
			assert isinstance(app.screen, SearchFiltersModal)
			assert app.screen.query_one("#sf-size-text").value == "0"
			assert app.screen.query_one("#sf-size-ocr").value == "100"
			assert app.screen.query_one("#sf-size-transcribe").value == "250"

	asyncio.run(run())


def test_given_tui_when_search_filters_cancelled_then_values_unchanged(tmp_path: Path):
	# given
	app = _build_app(argv=["hello", str(tmp_path)])
	original = app.search_filters

	async def run():
		async with app.run_test(size=(120, 40)) as pilot:
			await pilot.pause()
			await pilot.click("#search-filters-button")
			await pilot.pause()
			app.screen.query_one("#sf-size-text").value = "999"
			await pilot.click("#search-filters-cancel")
			await pilot.pause()
			assert app.search_filters == original

	asyncio.run(run())
