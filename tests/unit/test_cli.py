from __future__ import annotations

import json
from pathlib import Path

import pytest

from srxy.cli import build_parser, format_flat, format_grouped, format_json, main, resolve_search_modes
from srxy.models import FileSearchResult, LineMatch


pytestmark = pytest.mark.unit


def test_given_content_match_when_formatting_grouped_then_shows_file_and_line(tmp_path: Path):
	# given
	file_path = tmp_path / "alpha.py"
	result = FileSearchResult(
		path=file_path,
		score=0.85,
		breakdown={"content": 0.85},
		lines=[LineMatch(line_number=42, text="def magic_file_search(", score=0.85)],
	)

	# when
	output = format_grouped([result], query="magic")

	# then
	assert f"{file_path.as_posix()}  score=0.85  (content)" not in output
	assert f"── {file_path.as_posix()} ──" in output
	assert "score 0.85  ·  matched: content" in output
	assert "line 42  ·  score 0.85" in output
	assert "│ «magic»" in output or "│ def «magic»" in output


def test_given_name_only_match_when_formatting_flat_then_uses_line_zero_sentinel(tmp_path: Path):
	# given
	file_path = tmp_path / "budget-2024.md"
	result = FileSearchResult(
		path=file_path,
		score=0.92,
		breakdown={"name": 0.92},
		lines=[],
	)

	# when
	output = format_flat([result])

	# then
	assert output == f"{file_path.as_posix()}:name:0:0.92:budget-2024.md"


def test_given_results_when_formatting_json_then_emits_serializable_payload(tmp_path: Path):
	# given
	file_path = tmp_path / "notes.txt"
	result = FileSearchResult(
		path=file_path,
		score=0.8,
		breakdown={"content": 0.8},
		lines=[LineMatch(line_number=12, text="hello", score=0.8)],
	)

	# when
	payload = json.loads(format_json([result], query="hello"))

	# then
	assert payload[0]["path"] == file_path.as_posix()
	assert payload[0]["lines"][0]["line_number"] == 12
	assert payload[0]["lines"][0]["location_kind"] == "line"
	assert payload[0]["lines"][0]["location_label"] == "line 12"
	assert payload[0]["lines"][0]["preview"] == "«hello»"


def test_given_names_only_flag_when_resolving_modes_then_disables_content_search():
	# given
	parser = build_parser()
	args = parser.parse_args(["token", ".", "--names-only"])

	# when
	search_names, search_contents = resolve_search_modes(args)

	# then
	assert search_names is True
	assert search_contents is False


def test_given_content_only_flag_when_resolving_modes_then_disables_name_search():
	# given
	parser = build_parser()
	args = parser.parse_args(["token", ".", "--content-only"])

	# when
	search_names, search_contents = resolve_search_modes(args)

	# then
	assert search_names is False
	assert search_contents is True


def test_given_matching_directory_when_running_cli_then_prints_results(
	tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
	# given
	(tmp_path / "budget.md").write_text("figures", encoding="utf-8")
	(tmp_path / "notes.txt").write_text("quarterly revenue projections", encoding="utf-8")

	# when
	exit_code = main(["revenue", str(tmp_path), "--content-only", "--format", "flat"])

	# then
	captured = capsys.readouterr()
	assert exit_code == 0
	assert "notes.txt:line:1:" in captured.out
	assert "revenue" in captured.out


def test_given_no_matches_when_running_cli_then_returns_exit_code_one(
	tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
	# given
	(tmp_path / "notes.txt").write_text("hello", encoding="utf-8")

	# when
	exit_code = main(["zzzzzzzz", str(tmp_path), "--threshold", "0.99"])

	# then
	captured = capsys.readouterr()
	assert exit_code == 1
	assert captured.out == ""


def test_given_missing_path_when_running_cli_then_returns_exit_code_two(
	tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
	# given
	missing = tmp_path / "missing"

	# when
	exit_code = main(["test", str(missing)])

	# then
	captured = capsys.readouterr()
	assert exit_code == 2
	assert "does not exist" in captured.err


def test_given_hidden_directory_when_running_cli_with_include_hidden_then_searches_hidden_entries(
	tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
	# given
	hidden_dir = tmp_path / ".git"
	hidden_dir.mkdir()
	(hidden_dir / "config").write_text("secret token", encoding="utf-8")
	(tmp_path / "visible.txt").write_text("token", encoding="utf-8")

	# when
	exit_code = main(["token", str(tmp_path), "--content-only", "--format", "flat", "--include-hidden"])

	# then
	captured = capsys.readouterr()
	assert exit_code == 0
	assert ".git/config:line:1:" in captured.out
	assert "visible.txt:line:1:" in captured.out


def test_given_noise_directory_when_running_cli_with_include_noise_then_searches_noise_entries(
	tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
	# given
	noise_dir = tmp_path / "__pycache__"
	noise_dir.mkdir()
	(noise_dir / "cache.txt").write_text("needle cache", encoding="utf-8")
	(tmp_path / "visible.txt").write_text("needle", encoding="utf-8")

	# when
	exit_code = main(["needle", str(tmp_path), "--content-only", "--format", "flat", "--include-noise"])

	# then
	captured = capsys.readouterr()
	assert exit_code == 0
	assert "__pycache__/cache.txt:line:1:" in captured.out
	assert "visible.txt:line:1:" in captured.out


def test_given_oversized_file_when_running_cli_then_warns_on_stderr(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
	# given
	large_file = tmp_path / "large.txt"
	large_file.write_text("needle " + ("x" * 2_000_000), encoding="utf-8")

	# when
	exit_code = main(["needle", str(large_file), "--content-only", "--max-file-size", "1024"])

	# then
	captured = capsys.readouterr()
	assert exit_code == 1
	assert "warning: skipped content search" in captured.err
	assert "--max-file-size" in captured.err
	assert large_file.as_posix() in captured.err


def test_given_pdf_match_when_formatting_grouped_then_shows_page_label(tmp_path: Path):
	# given
	from tests.helpers import write_pdf_with_text

	file_path = tmp_path / "report.pdf"
	write_pdf_with_text(file_path, "quarterly revenue projections")
	result = FileSearchResult(
		path=file_path,
		score=0.47,
		breakdown={"content": 0.47},
		lines=[LineMatch(line_number=1, text="quarterly revenue projections", score=0.47, location_kind="page")],
	)

	# when
	output = format_grouped([result], query="revenue")

	# then
	assert 'for "revenue"' in output
	assert "page 1  ·  score 0.47" in output
	assert "│ quarterly «revenue» projections" in output
