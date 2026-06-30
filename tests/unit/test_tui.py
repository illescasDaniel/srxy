from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.text import Text
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Footer

from srxy.cli import build_parser, should_use_tui
from srxy.models import FileSearchResult, LineMatch
from srxy.tui.app import SrxyApp
from srxy.tui.modals import SearchOptionsModal
from srxy.tui.theme import detect_app_theme


pytestmark = pytest.mark.unit


def _build_args(argv: list[str]) -> argparse.Namespace:
	return build_parser().parse_args(argv)


def test_given_tty_and_grouped_format_when_should_use_tui_then_returns_true(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setattr("srxy.cli.sys.stdout", MagicMock(isatty=MagicMock(return_value=True)))
	monkeypatch.setattr("srxy.cli.sys.stderr", MagicMock(isatty=MagicMock(return_value=True)))
	args = _build_args(["registry", "."])

	# when / then
	assert should_use_tui(args) is True


def test_given_no_tui_flag_when_should_use_tui_then_returns_false(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setattr("srxy.cli.sys.stdout", MagicMock(isatty=MagicMock(return_value=True)))
	monkeypatch.setattr("srxy.cli.sys.stderr", MagicMock(isatty=MagicMock(return_value=True)))
	args = _build_args(["registry", ".", "--no-tui"])

	# when / then
	assert should_use_tui(args) is False


def test_given_json_flag_when_should_use_tui_then_returns_false(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setattr("srxy.cli.sys.stdout", MagicMock(isatty=MagicMock(return_value=True)))
	monkeypatch.setattr("srxy.cli.sys.stderr", MagicMock(isatty=MagicMock(return_value=True)))
	args = _build_args(["registry", ".", "--json"])

	# when / then
	assert should_use_tui(args) is False


def test_given_flat_format_when_should_use_tui_then_returns_false(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setattr("srxy.cli.sys.stdout", MagicMock(isatty=MagicMock(return_value=True)))
	monkeypatch.setattr("srxy.cli.sys.stderr", MagicMock(isatty=MagicMock(return_value=True)))
	args = _build_args(["registry", ".", "--format", "flat"])

	# when / then
	assert should_use_tui(args) is False


def test_given_output_file_when_should_use_tui_then_returns_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setattr("srxy.cli.sys.stdout", MagicMock(isatty=MagicMock(return_value=True)))
	monkeypatch.setattr("srxy.cli.sys.stderr", MagicMock(isatty=MagicMock(return_value=True)))
	output_path = tmp_path / "out.txt"
	args = _build_args(["registry", ".", "-o", str(output_path)])

	# when / then
	assert should_use_tui(args) is False


def test_given_ci_env_when_should_use_tui_then_returns_false(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setattr("srxy.cli.sys.stdout", MagicMock(isatty=MagicMock(return_value=True)))
	monkeypatch.setattr("srxy.cli.sys.stderr", MagicMock(isatty=MagicMock(return_value=True)))
	monkeypatch.setenv("CI", "true")
	args = _build_args(["registry", "."])

	# when / then
	assert should_use_tui(args) is False


def test_given_no_query_when_should_use_tui_on_tty_then_returns_true(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setattr("srxy.cli.sys.stdout", MagicMock(isatty=MagicMock(return_value=True)))
	monkeypatch.setattr("srxy.cli.sys.stderr", MagicMock(isatty=MagicMock(return_value=True)))
	args = _build_args([])

	# when / then
	assert should_use_tui(args) is True


def test_given_light_colorfgbg_when_detecting_theme_then_uses_textual_light(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("COLORFGBG", "0;15")

	# when / then
	assert detect_app_theme() == "textual-light"


def test_given_dark_colorfgbg_when_detecting_theme_then_uses_textual_dark(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("COLORFGBG", "15;0")

	# when / then
	assert detect_app_theme() == "textual-dark"


def test_given_matches_when_tui_search_completes_then_lists_results(tmp_path: Path):
	# given
	file_path = tmp_path / "notes.txt"
	result = FileSearchResult(
		path=file_path,
		score=0.85,
		breakdown={"content": 0.85},
		lines=[LineMatch(line_number=1, text="hello world", score=0.85)],
	)
	args = _build_args(["hello", str(tmp_path), "--content-only"])

	async def run_app():
		app = SrxyApp(args, auto_start=True)
		with (
			patch("srxy.tui.app.run_tui_preflight", new=AsyncMock(return_value=None)),
			patch(
				"srxy.tui.app.execute_search",
				return_value=([result], []),
			),
		):
			async with app.run_test() as pilot:
				table = app.query_one("#results-table", DataTable)
				for _ in range(30):
					await pilot.pause(delay=0.05)
					table = app.query_one("#results-table", DataTable)
					if table.row_count == 1:
						break
				assert table.row_count == 1
				assert app.exit_code == 0
				assert str(table.get_row_at(0)[0]) == "85%"

	# when / then
	asyncio.run(run_app())


def test_given_app_when_composed_then_footer_hides_command_palette():
	# given
	args = _build_args([])

	async def run_app():
		app = SrxyApp(args, auto_start=False)
		async with app.run_test():
			footer = app.query_one(Footer)
			assert footer.show_command_palette is False
			bindings = [binding.description for binding in app.BINDINGS if binding.show]
			assert "Help" in bindings
			assert "Open" in bindings
			assert "Quit" in bindings

	# when / then
	asyncio.run(run_app())


def test_given_matches_when_search_callbacks_fire_then_updates_table_live(tmp_path: Path):
	# given
	file_path = tmp_path / "notes.txt"
	result = FileSearchResult(
		path=file_path,
		score=0.85,
		breakdown={"content": 0.85},
		lines=[LineMatch(line_number=1, text="hello world", score=0.85)],
	)
	args = _build_args(["hello", str(tmp_path), "--content-only"])

	def fake_execute_search(
		args: argparse.Namespace,
		*,
		skipped_files: list[Any],
		on_progress: Any,
		on_activity: Any,
		on_result: Any,
	):
		on_progress(1, 2)
		on_result(result)
		return [result], skipped_files

	async def run_app():
		app = SrxyApp(args, auto_start=True)
		with (
			patch("srxy.tui.app.run_tui_preflight", new=AsyncMock(return_value=None)),
			patch("srxy.tui.app.execute_search", side_effect=fake_execute_search),
		):
			async with app.run_test() as pilot:
				table = app.query_one("#results-table", DataTable)
				for _ in range(30):
					await pilot.pause(delay=0.05)
					table = app.query_one("#results-table", DataTable)
					if table.row_count == 1:
						break
				assert table.row_count == 1

	# when / then
	asyncio.run(run_app())


def test_given_no_matches_when_tui_search_completes_then_sets_exit_code(tmp_path: Path):
	# given
	args = _build_args(["missing", str(tmp_path), "--content-only"])

	async def run_app():
		app = SrxyApp(args, auto_start=True)
		with (
			patch("srxy.tui.app.run_tui_preflight", new=AsyncMock(return_value=None)),
			patch(
				"srxy.tui.app.execute_search",
				return_value=([], []),
			),
		):
			async with app.run_test() as pilot:
				for _ in range(30):
					await pilot.pause(delay=0.05)
					if app.exit_code == 1:
						break
				assert app.exit_code == 1

	# when / then
	asyncio.run(run_app())


def test_given_result_with_many_lines_when_preview_updated_then_scrolls_to_top(tmp_path: Path):
	# given
	file_path = tmp_path / "notes.txt"
	file_path.write_text("\n".join(f"match line {index}" for index in range(30)), encoding="utf-8")
	lines = [LineMatch(line_number=index, text=f"match line {index}", score=0.9 - index * 0.01) for index in range(30)]
	result = FileSearchResult(
		path=file_path,
		score=0.9,
		breakdown={"content": 0.9},
		lines=lines,
	)
	args = _build_args(["match", str(tmp_path), "--content-only"])

	async def run_app():
		app = SrxyApp(args, auto_start=False)
		with (
			patch("srxy.tui.app.run_tui_preflight", new=AsyncMock(return_value=None)),
			patch("srxy.tui.app.execute_search", return_value=([result], [])),
		):
			async with app.run_test(size=(100, 30)) as pilot:
				await pilot.pause()
				app.action_start_search()
				table = app.query_one("#results-table", DataTable)
				for _ in range(60):
					await pilot.pause(delay=0.05)
					if table.row_count == 1:
						break
				preview = app.query_one("#preview-matches", DataTable)
				assert preview.row_count > 0
				assert preview.scroll_y == 0

	# when / then
	asyncio.run(run_app())


def test_given_completed_search_when_option_changes_then_search_button_becomes_stale(tmp_path: Path):
	# given
	file_path = tmp_path / "notes.txt"
	result = FileSearchResult(
		path=file_path,
		score=0.85,
		breakdown={"content": 0.85},
		lines=[LineMatch(line_number=1, text="hello world", score=0.85)],
	)
	args = _build_args(["hello", str(tmp_path), "--content-only"])

	async def run_app():
		app = SrxyApp(args, auto_start=True)
		with (
			patch("srxy.tui.app.run_tui_preflight", new=AsyncMock(return_value=None)),
			patch("srxy.tui.app.execute_search", return_value=([result], [])),
		):
			async with app.run_test() as pilot:
				button = app.query_one("#search-button")
				assert button.has_class("-stale")
				for _ in range(30):
					await pilot.pause(delay=0.05)
					if not button.has_class("-stale"):
						break
				assert not button.has_class("-stale")
				await pilot.click("#search-options-button")
				await pilot.pause()
				assert isinstance(app.screen, SearchOptionsModal)
				await pilot.click("#so-names")
				await pilot.pause()
				await pilot.click("#search-options-apply")
				await pilot.pause()
				assert button.has_class("-stale")

	# when / then
	asyncio.run(run_app())


def test_given_file_limit_when_results_stream_in_then_table_respects_top_n(tmp_path: Path):
	# given
	results = [
		FileSearchResult(
			path=tmp_path / f"file{index}.txt",
			score=0.9 - index * 0.1,
			breakdown={"content": 0.9 - index * 0.1},
			lines=[LineMatch(line_number=1, text="token", score=0.9 - index * 0.1)],
		)
		for index in range(3)
	]
	for result in results:
		result.path.write_text("token", encoding="utf-8")
	args = _build_args(["token", str(tmp_path), "--content-only"])

	def fake_execute_search(
		args: argparse.Namespace,
		*,
		skipped_files: list[Any],
		on_progress: Any,
		on_activity: Any,
		on_result: Any,
	):
		for result in results:
			on_result(result)
		return results[:2], skipped_files

	async def run_app():
		app = SrxyApp(args, auto_start=False)
		async with app.run_test() as pilot:
			await pilot.pause()
			app.search_filters = replace(app.search_filters, top_files="2")
			app.query_one("#query-term-0").value = "token"
			await pilot.click("#search-button")
			table = app.query_one("#results-table", DataTable)
			for _ in range(40):
				await pilot.pause(delay=0.05)
				if table.row_count == 2:
					break
			assert table.row_count == 2

	# when / then
	with (
		patch("srxy.tui.app.run_tui_preflight", new=AsyncMock(return_value=None)),
		patch("srxy.tui.app.execute_search", side_effect=fake_execute_search),
	):
		asyncio.run(run_app())


def test_given_selected_result_when_copy_path_then_puts_path_on_clipboard(tmp_path: Path):
	# given
	file_path = tmp_path / "notes.txt"
	file_path.write_text("transform model", encoding="utf-8")
	result = FileSearchResult(
		path=file_path,
		score=0.85,
		breakdown={"content": 0.85},
		lines=[LineMatch(line_number=1, text="transform model", score=0.85)],
	)
	args = _build_args(["transform", str(tmp_path), "--content-only"])

	async def run_app():
		app = SrxyApp(args, auto_start=True)
		with (
			patch("srxy.tui.app.run_tui_preflight", new=AsyncMock(return_value=None)),
			patch("srxy.tui.app.execute_search", return_value=([result], [])),
			patch.object(SrxyApp, "copy_to_clipboard") as copy_mock,
		):
			async with app.run_test() as pilot:
				for _ in range(30):
					await pilot.pause(delay=0.05)
					if app.query_one("#results-table", DataTable).row_count == 1:
						break
				app.action_copy_path()
				copy_mock.assert_called_once_with(file_path.as_posix())

	# when / then
	asyncio.run(run_app())


def test_given_preview_match_when_copy_match_button_pressed_then_copies_location_and_text(tmp_path: Path):
	# given
	file_path = tmp_path / "notes.txt"
	file_path.write_text("transform model", encoding="utf-8")
	result = FileSearchResult(
		path=file_path,
		score=0.85,
		breakdown={"content": 0.85},
		lines=[LineMatch(line_number=1, text="transform model", score=0.85)],
	)
	args = _build_args(["transform", str(tmp_path), "--content-only"])

	async def run_app():
		app = SrxyApp(args, auto_start=True)
		with (
			patch("srxy.tui.app.run_tui_preflight", new=AsyncMock(return_value=None)),
			patch("srxy.tui.app.execute_search", return_value=([result], [])),
			patch.object(SrxyApp, "copy_to_clipboard") as copy_mock,
		):
			async with app.run_test(size=(120, 30)) as pilot:
				for _ in range(30):
					await pilot.pause(delay=0.05)
					if app.query_one("#preview-matches", DataTable).row_count == 1:
						break
				app.action_copy_match()
				copy_mock.assert_called_once_with("line 1\ttransform model")

	# when / then
	asyncio.run(run_app())


def test_given_darwin_when_copy_to_clipboard_then_uses_pbcopy():
	# given
	app = SrxyApp(_build_args(["query", "."]))

	# when
	with (
		patch("srxy.tui.app.platform.system", return_value="Darwin"),
		patch("srxy.tui.app.shutil.which", return_value="/usr/bin/pbcopy"),
		patch("srxy.tui.app.subprocess.run") as run_mock,
	):
		app.copy_to_clipboard("hello there")

	# then
	run_mock.assert_called_once()
	assert run_mock.call_args.args[0] == ["/usr/bin/pbcopy"]
	assert run_mock.call_args.kwargs["input"] == b"hello there"


def test_given_darwin_when_pbcopy_fails_then_falls_back_to_textual_clipboard():
	# given
	app = SrxyApp(_build_args(["query", "."]))

	# when
	with (
		patch("srxy.tui.app.platform.system", return_value="Darwin"),
		patch("srxy.tui.app.shutil.which", return_value="/usr/bin/pbcopy"),
		patch("srxy.tui.app.subprocess.run", side_effect=OSError("pbcopy failed")),
		patch.object(SrxyApp.__bases__[0], "copy_to_clipboard") as super_mock,
	):
		app.copy_to_clipboard("fallback text")

	# then
	super_mock.assert_called_once_with("fallback text")


def test_given_preview_match_when_rendered_then_uses_bold_text_for_query_hit(tmp_path: Path):
	# given
	file_path = tmp_path / "notes.txt"
	file_path.write_text("transform model", encoding="utf-8")
	result = FileSearchResult(
		path=file_path,
		score=0.85,
		breakdown={"content": 0.85},
		lines=[LineMatch(line_number=1, text="transform model", score=0.85)],
	)
	args = _build_args(["transform", str(tmp_path), "--content-only"])

	async def run_app():
		app = SrxyApp(args, auto_start=True)
		with (
			patch("srxy.tui.app.run_tui_preflight", new=AsyncMock(return_value=None)),
			patch("srxy.tui.app.execute_search", return_value=([result], [])),
		):
			async with app.run_test() as pilot:
				for _ in range(30):
					await pilot.pause(delay=0.05)
					if app.query_one("#preview-matches", DataTable).row_count == 1:
						break
				preview = app.query_one("#preview-matches", DataTable)
				cell = preview.get_cell_at(Coordinate(0, 2))
				assert isinstance(cell, Text)
				assert cell.plain == "transform model"
				assert any(span.style == "bold" for span in cell.spans)

	# when / then
	asyncio.run(run_app())


def test_given_long_location_preview_when_switching_to_short_preview_then_location_column_stays_capped(
	tmp_path: Path,
):
	# given
	long_path = tmp_path / "long.txt"
	short_path = tmp_path / "short.txt"
	long_term = "x" * 80
	long_result = FileSearchResult(
		path=long_path,
		score=0.9,
		breakdown={"content": 0.9},
		lines=[
			LineMatch(
				line_number=1,
				text="hello",
				score=0.9,
				matched_term=long_term,
			)
		],
	)
	short_result = FileSearchResult(
		path=short_path,
		score=0.85,
		breakdown={"content": 0.85},
		lines=[LineMatch(line_number=104, text="thank you", score=0.85)],
	)
	args = _build_args(["test", str(tmp_path), "--content-only"])
	app = SrxyApp(args, auto_start=True)

	async def run_app():
		with (
			patch("srxy.tui.app.run_tui_preflight", new=AsyncMock(return_value=None)),
			patch("srxy.tui.app.execute_search", return_value=([long_result, short_result], [])),
			patch.object(SrxyApp, "copy_to_clipboard") as copy_mock,
		):
			async with app.run_test(size=(120, 30)) as pilot:
				for _ in range(30):
					await pilot.pause(delay=0.05)
					if app.query_one("#results-table", DataTable).row_count >= 2:
						break
				preview = app.query_one("#preview-matches", DataTable)
				column_widths = [column.width for column in preview.columns.values()]
				assert column_widths[1] == 32
				displayed = str(preview.get_cell_at(Coordinate(0, 1)))
				assert displayed.endswith("…")

				app.action_copy_match()
				copied = copy_mock.call_args.args[0]
				assert long_term in copied
				assert displayed not in copied

				app.query_one("#results-table", DataTable).move_cursor(row=1)
				await pilot.pause()
				column_widths = [column.width for column in preview.columns.values()]
				assert column_widths[1] == 32
				assert preview.get_cell_at(Coordinate(0, 1)) == "line 104"

	# when / then
	asyncio.run(run_app())
