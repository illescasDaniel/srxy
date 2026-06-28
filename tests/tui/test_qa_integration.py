"""Release QA TUI integration tests (headless SVG + pilot)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from tests.helpers import qa_corpus_docs, require_qa_corpus
from tests.tui.helpers import assert_labels_visible
from textual.widgets import Checkbox, DataTable

from srxy.cli import build_parser
from srxy.models import FileSearchResult, LineMatch
from srxy.tui.app import SrxyApp


pytestmark = [pytest.mark.integration, pytest.mark.tui, pytest.mark.qa]


def _build_app(*, argv: list[str], theme: str = "textual-light", auto_start: bool = False) -> SrxyApp:
	args = build_parser().parse_args(argv)
	app = SrxyApp(args, auto_start=auto_start)
	app.theme = theme
	return app


def test_given_tui_when_option_chips_toggled_then_search_becomes_stale(tmp_path: Path):
	# given
	app = _build_app(argv=["hello", str(tmp_path)])

	async def run():
		async with app.run_test(size=(100, 30)) as pilot:
			await pilot.pause()
			button = app.query_one("#search-button")
			ocr = app.query_one("#opt-ocr", Checkbox)
			assert not ocr.value
			await pilot.click("#opt-ocr")
			await pilot.pause()
			assert ocr.value
			assert button.has_class("-stale")
			svg = app.export_screenshot(title="srxy-tui-ocr-toggle")
			assert_labels_visible(svg, ("OCR", "Search"))

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
			patch("srxy.tui.app.run_tui_preflight", new=AsyncMock(return_value=None)),
			patch("srxy.tui.app.execute_search", return_value=([result], [])),
		):
			async with app.run_test(size=(100, 30)) as pilot:
				button = app.query_one("#search-button")
				for _ in range(30):
					await pilot.pause(delay=0.05)
					if not button.has_class("-stale"):
						break
				await pilot.click("#opt-content")
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
		lines=[LineMatch(line_number=1, text="qa_ocr_token found", score=0.9, location_kind="ocr")],
	)
	args = build_parser().parse_args(["qa_ocr", str(tmp_path), "--ocr", "--content-only"])
	app = SrxyApp(args, auto_start=True)

	async def run():
		with (
			patch("srxy.tui.app.run_tui_preflight", new=AsyncMock(return_value=None)),
			patch("srxy.tui.app.execute_search", return_value=([result], [])),
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
	file_path = tmp_path / "song.flac"
	file_path.write_text("audio", encoding="utf-8")
	result = FileSearchResult(
		path=file_path,
		score=0.8,
		breakdown={"transcript": 0.8},
		lines=[LineMatch(line_number=1, text="all i know is", score=0.8, location_kind="transcript")],
	)
	args = build_parser().parse_args(["all i know", str(tmp_path), "--transcribe", "--content-only"])
	app = SrxyApp(args, auto_start=True)

	async def run():
		with (
			patch("srxy.tui.app.run_tui_preflight", new=AsyncMock(return_value=None)),
			patch("srxy.tui.app.execute_search", return_value=([result], [])),
		):
			async with app.run_test(size=(100, 30)) as pilot:
				for _ in range(30):
					await pilot.pause(delay=0.05)
					if app.query_one("#results-table", DataTable).row_count == 1:
						break
				svg = app.export_screenshot(title="srxy-tui-transcript-preview")
				visible = svg.lower()
				assert "transcript" in visible or "all i know" in visible

	asyncio.run(run())


@pytest.mark.qa_full
@pytest.mark.semantic
def test_given_semantic_image_flag_when_search_completes_then_results_table_populated():
	# given
	require_qa_corpus()
	docs = qa_corpus_docs()
	file_path = docs / "IMG_20260223_184931.jpg"
	result = FileSearchResult(
		path=file_path,
		score=0.75,
		breakdown={"semantic_image": 0.75},
		lines=[LineMatch(line_number=1, text="person", score=0.75, location_kind="semantic_image")],
	)
	args = build_parser().parse_args(["person", str(docs), "--semantic-image", "--content-only"])
	app = SrxyApp(args, auto_start=True)

	async def run():
		with (
			patch("srxy.tui.app.run_tui_preflight", new=AsyncMock(return_value=None)),
			patch("srxy.tui.app.search_uses_subprocess", return_value=False),
			patch("srxy.tui.app.execute_search", return_value=([result], [])),
		):
			async with app.run_test(size=(120, 40)) as pilot:
				for _ in range(30):
					await pilot.pause(delay=0.05)
					if app.query_one("#results-table", DataTable).row_count >= 1:
						break
				assert app.query_one("#results-table", DataTable).row_count >= 1
				svg = app.export_screenshot(title="srxy-tui-semantic-image")
				assert_labels_visible(svg, ("Search", "Image semantic"))

	asyncio.run(run())


def test_given_semantic_transcribe_ocr_flags_when_launched_then_option_chips_reflect_args():
	# given
	app = _build_app(argv=["test", ".", "--semantic-all"])

	async def run():
		async with app.run_test(size=(100, 30)) as pilot:
			await pilot.pause()
			assert app.query_one("#opt-semantic", Checkbox).value
			assert app.query_one("#opt-semantic-image", Checkbox).value
			assert app.query_one("#opt-ocr", Checkbox).value
			assert app.query_one("#opt-transcribe", Checkbox).value
			svg = app.export_screenshot(title="srxy-tui-semantic-all")
			assert_labels_visible(svg, ("Semantic", "Transcribe", "OCR"))

	asyncio.run(run())
