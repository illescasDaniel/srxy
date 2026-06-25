from __future__ import annotations

from pathlib import Path

import pytest
from tests.helpers import write_docx_with_text, write_pdf_with_text, write_pptx_with_text, write_xlsx_with_text

from srxy import magic_file_search
from srxy.models import FileSearchResult, SkippedFile


pytestmark = pytest.mark.unit


def test_given_directory_with_matching_filename_when_searching_names_then_returns_file(tmp_path: Path):
	# given
	(tmp_path / "notes.txt").write_text("unrelated", encoding="utf-8")
	(tmp_path / "budget-2024.md").write_text("figures", encoding="utf-8")
	query = "budget"

	# when
	results = magic_file_search(tmp_path, query, search_contents=False, threshold=0.5)

	# then
	assert len(results) == 1
	assert results[0].path.name == "budget-2024.md"
	assert results[0].score >= 0.5
	assert "name" in results[0].breakdown


def test_given_directory_with_matching_content_when_searching_contents_then_returns_file(tmp_path: Path):
	# given
	(tmp_path / "notes.txt").write_text("quarterly revenue projections", encoding="utf-8")
	(tmp_path / "other.txt").write_text("hello world", encoding="utf-8")
	query = "revenue"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path.name == "notes.txt"
	assert results[0].breakdown["content"] >= 0.25
	assert len(results[0].lines) == 1
	assert results[0].lines[0].line_number == 1
	assert "revenue" in results[0].lines[0].text


def test_given_multiline_file_when_searching_contents_then_returns_matching_line_numbers(tmp_path: Path):
	# given
	(tmp_path / "notes.txt").write_text("alpha\nquarterly revenue projections\nomega\n", encoding="utf-8")
	query = "revenue"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert len(results[0].lines) == 1
	assert results[0].lines[0].line_number == 2
	assert "revenue" in results[0].lines[0].text


def test_given_weak_lines_when_searching_contents_then_excludes_lines_below_threshold(tmp_path: Path):
	# given
	(tmp_path / "notes.txt").write_text("alpha\nbeta\n", encoding="utf-8")
	query = "zzzzzzzz"

	# when
	results = magic_file_search(tmp_path, query, search_names=False, threshold=0.9)

	# then
	assert results == []


def test_given_many_matching_lines_when_searching_contents_then_respects_max_line_matches(tmp_path: Path):
	# given
	lines = "\n".join(f"token line {index}" for index in range(100))
	(tmp_path / "many.txt").write_text(lines, encoding="utf-8")
	query = "token"

	# when
	results = magic_file_search(tmp_path, query, search_names=False, max_line_matches=3, threshold=0.25)

	# then
	assert len(results) == 1
	assert len(results[0].lines) == 3


def test_given_single_file_path_when_searching_then_returns_that_file(tmp_path: Path):
	# given
	file_path = tmp_path / "alpha.py"
	file_path.write_text("def alpha_handler(): pass", encoding="utf-8")
	query = "alpha"

	# when
	results = magic_file_search(file_path, query)

	# then
	assert len(results) == 1
	assert results[0].path == file_path.resolve()


def test_given_hidden_directory_when_searching_then_skips_hidden_entries(tmp_path: Path):
	# given
	hidden_dir = tmp_path / ".git"
	hidden_dir.mkdir()
	(hidden_dir / "config").write_text("secret token", encoding="utf-8")
	(tmp_path / "visible.txt").write_text("token", encoding="utf-8")
	query = "token"

	# when
	results = magic_file_search(tmp_path, query, skip_hidden_folders=True)

	# then
	assert len(results) == 1
	assert results[0].path.name == "visible.txt"


def test_given_hidden_directory_when_skip_hidden_folders_disabled_then_includes_hidden_entries(tmp_path: Path):
	# given
	hidden_dir = tmp_path / ".git"
	hidden_dir.mkdir()
	(hidden_dir / "config").write_text("secret token", encoding="utf-8")
	(tmp_path / "visible.txt").write_text("token", encoding="utf-8")
	query = "token"

	# when
	results = magic_file_search(tmp_path, query, skip_hidden_folders=False)

	# then
	assert len(results) == 2
	path_names = {result.path.name for result in results}
	assert path_names == {"config", "visible.txt"}


def test_given_noise_directory_when_searching_then_skips_noise_entries(tmp_path: Path):
	# given
	noise_dir = tmp_path / "__pycache__"
	noise_dir.mkdir()
	(noise_dir / "module.cpython-312.pyc").write_bytes(b"needle bytecode")
	(tmp_path / "visible.txt").write_text("needle", encoding="utf-8")
	query = "needle"

	# when
	results = magic_file_search(tmp_path, query, skip_noise_folders=True)

	# then
	assert len(results) == 1
	assert results[0].path.name == "visible.txt"


def test_given_noise_directory_when_skip_noise_folders_disabled_then_includes_noise_entries(tmp_path: Path):
	# given
	noise_dir = tmp_path / "node_modules"
	noise_dir.mkdir()
	(noise_dir / "package.txt").write_text("needle dependency", encoding="utf-8")
	(tmp_path / "visible.txt").write_text("needle", encoding="utf-8")
	query = "needle"

	# when
	results = magic_file_search(tmp_path, query, skip_noise_folders=False)

	# then
	assert len(results) == 2
	path_names = {result.path.name for result in results}
	assert path_names == {"package.txt", "visible.txt"}


def test_given_hidden_and_noise_directories_when_both_skip_flags_disabled_then_includes_all_entries(
	tmp_path: Path,
):
	# given
	hidden_dir = tmp_path / ".git"
	hidden_dir.mkdir()
	(hidden_dir / "config").write_text("secret token", encoding="utf-8")
	noise_dir = tmp_path / "__pycache__"
	noise_dir.mkdir()
	(noise_dir / "cache.txt").write_text("token cache", encoding="utf-8")
	(tmp_path / "visible.txt").write_text("token", encoding="utf-8")
	query = "token"

	# when
	results = magic_file_search(tmp_path, query, skip_hidden_folders=False, skip_noise_folders=False)

	# then
	assert len(results) == 3
	path_names = {result.path.name for result in results}
	assert path_names == {"cache.txt", "config", "visible.txt"}


def test_given_binary_file_when_searching_contents_then_skips_binary(tmp_path: Path):
	# given
	(tmp_path / "data.bin").write_bytes(b"\x00\x01secret\xff")
	(tmp_path / "plain.txt").write_text("secret sauce", encoding="utf-8")
	query = "secret"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path.name == "plain.txt"


def test_given_oversized_file_when_searching_contents_then_skips_content_match(tmp_path: Path):
	# given
	large_file = tmp_path / "large.txt"
	large_file.write_text("needle " + ("x" * 2_000_000), encoding="utf-8")
	query = "needle"

	# when
	results = magic_file_search(tmp_path, query, search_names=False, max_file_size=1024)

	# then
	assert results == []


def test_given_high_threshold_when_searching_weak_match_then_returns_empty(tmp_path: Path):
	# given
	(tmp_path / "item.txt").write_text("hello", encoding="utf-8")
	query = "helo"

	# when
	results = magic_file_search(tmp_path, query, threshold=0.99)

	# then
	assert results == []


def test_given_empty_query_when_searching_files_then_returns_empty_list(tmp_path: Path):
	# given
	(tmp_path / "item.txt").write_text("hello", encoding="utf-8")

	# when
	results = magic_file_search(tmp_path, "   ")

	# then
	assert results == []


def test_given_missing_path_when_searching_then_raises_file_not_found(tmp_path: Path):
	# given
	missing = tmp_path / "missing"

	# when
	with pytest.raises(FileNotFoundError, match="does not exist"):
		magic_file_search(missing, "test")

	# then
	assert True


def test_given_no_search_modes_when_searching_then_raises_value_error(tmp_path: Path):
	# given
	(tmp_path / "item.txt").write_text("hello", encoding="utf-8")

	# when
	with pytest.raises(ValueError, match="search_names or search_contents"):
		magic_file_search(tmp_path, "hello", search_names=False, search_contents=False)

	# then
	assert True


def test_given_pdf_with_matching_content_when_searching_contents_then_returns_file(tmp_path: Path):
	# given
	write_pdf_with_text(tmp_path / "report.pdf", "quarterly revenue projections")
	(tmp_path / "other.txt").write_text("hello world", encoding="utf-8")
	query = "revenue"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path.name == "report.pdf"
	assert results[0].breakdown["content"] >= 0.25
	assert len(results[0].lines) == 1
	assert results[0].lines[0].line_number == 1
	assert "revenue" in results[0].lines[0].text


def test_given_docx_with_matching_content_when_searching_contents_then_returns_file(tmp_path: Path):
	# given
	write_docx_with_text(tmp_path / "memo.docx", "quarterly revenue projections")
	query = "revenue"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path.name == "memo.docx"
	assert results[0].lines[0].line_number == 1
	assert "revenue" in results[0].lines[0].text


def test_given_xlsx_with_matching_content_when_searching_contents_then_returns_file(tmp_path: Path):
	# given
	write_xlsx_with_text(tmp_path / "budget.xlsx", "quarterly revenue")
	query = "revenue"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path.name == "budget.xlsx"
	assert results[0].lines[0].line_number == 1
	assert "revenue" in results[0].lines[0].text
	assert "[Summary]" in results[0].lines[0].text


def test_given_pptx_with_matching_content_when_searching_contents_then_returns_file(tmp_path: Path):
	# given
	write_pptx_with_text(tmp_path / "deck.pptx", "quarterly revenue projections")
	query = "revenue"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path.name == "deck.pptx"
	assert results[0].lines[0].line_number == 1
	assert "revenue" in results[0].lines[0].text


def test_given_corrupt_pdf_when_searching_contents_then_skips_gracefully(tmp_path: Path):
	# given
	(tmp_path / "broken.pdf").write_bytes(b"\x00not-a-real-pdf\xff")
	(tmp_path / "plain.txt").write_text("secret sauce", encoding="utf-8")
	query = "secret"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path.name == "plain.txt"


def test_given_oversized_file_when_collecting_skipped_then_reports_file(tmp_path: Path):
	# given
	large_file = tmp_path / "large.txt"
	large_file.write_text("needle " + ("x" * 2_000_000), encoding="utf-8")
	skipped: list[SkippedFile] = []
	query = "needle"

	# when
	results = magic_file_search(tmp_path, query, search_names=False, max_file_size=1024, skipped_files=skipped)

	# then
	assert results == []
	assert len(skipped) == 1
	assert skipped[0].path == large_file
	assert skipped[0].size_bytes > 1024


def test_given_directory_when_searching_with_callbacks_then_streams_progress_and_results(tmp_path: Path):
	# given
	(tmp_path / "alpha.txt").write_text("hello", encoding="utf-8")
	(tmp_path / "beta.txt").write_text("revenue report", encoding="utf-8")
	(tmp_path / "gamma.txt").write_text("goodbye", encoding="utf-8")
	progress_calls: list[tuple[int, int]] = []
	streamed_paths: list[str] = []

	def on_progress(current: int, total: int) -> None:
		progress_calls.append((current, total))

	def on_result(result: FileSearchResult):
		streamed_paths.append(result.path.name)

	# when
	results = magic_file_search(
		tmp_path,
		"revenue",
		search_names=False,
		on_progress=on_progress,
		on_result=on_result,
	)

	# then
	assert progress_calls == [(1, 3), (2, 3), (3, 3)]
	assert streamed_paths == ["beta.txt"]
	assert len(results) == 1
	assert results[0].path.name == "beta.txt"
