from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from tests.helpers import copy_media_fixture

from srxy.cli import (
	ProgressBar,
	build_parser,
	format_flat,
	format_grouped,
	format_grouped_result,
	format_json,
	format_json_result,
	format_skipped_file_warning,
	main,
	render_progress,
	resolve_search_modes,
)
from srxy.models import FileSearchResult, LineMatch, SkippedFile


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


def test_given_default_args_when_parsing_then_max_file_size_is_unlimited():
	# when
	args = build_parser().parse_args(["token"])

	# then
	assert args.max_file_size is None


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
	assert 'No matches for "zzzzzzzz"' in captured.err
	assert 'No matches for "zzzzzzzz"' in captured.err


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
	exit_code = main(["needle", str(large_file), "--content-only", "--max-file-size", "1024", "--no-progress"])

	# then
	captured = capsys.readouterr()
	assert exit_code == 1
	assert "warning: skipped content search" in captured.err
	assert "--max-file-size" in captured.err
	assert large_file.as_posix() in captured.err


def test_given_match_and_skipped_file_when_running_cli_then_warnings_follow_summary(
	tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
	# given
	match_file = tmp_path / "match.txt"
	match_file.write_text("needle here", encoding="utf-8")
	large_file = tmp_path / "large.txt"
	large_file.write_text("needle " + ("x" * 2_000_000), encoding="utf-8")

	# when
	exit_code = main(["needle", str(tmp_path), "--content-only", "--max-file-size", "1024", "--no-progress"])

	# then
	captured = capsys.readouterr()
	assert exit_code == 0
	summary = '1 file matched for "needle"'
	assert summary in captured.out
	assert captured.out.index(summary) < len(captured.out)
	assert "warning: skipped content search" in captured.err
	assert large_file.as_posix() in captured.err


def test_given_ocr_skip_when_formatting_warning_then_shows_ocr_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_OCR_MAX_FILE_SIZE", "20971520")
	skipped = SkippedFile(path=tmp_path / "large.png", size_bytes=25_000_000, reason="ocr_too_large")

	# when
	warning = format_skipped_file_warning(skipped, max_file_size=1_048_576)

	# then
	assert "skipped OCR" in warning
	assert "--max-ocr-file-size" in warning


def test_given_ocr_flag_when_parsing_args_then_accepts_flag():
	# when
	args = build_parser().parse_args(["invoice", ".", "--ocr"])

	# then
	assert args.ocr is True


def test_given_semantic_image_flag_when_parsing_args_then_accepts_flag():
	# when
	args = build_parser().parse_args(["sunset", ".", "--semantic-image"])

	# then
	assert args.semantic_image is True


def test_given_semantic_all_flag_when_parsing_args_then_accepts_flag():
	# when
	args = build_parser().parse_args(["invoice", ".", "--semantic-all"])

	# then
	assert args.semantic_all is True


def test_given_semantic_all_without_ffmpeg_when_running_cli_then_exits_two_with_message(
	tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
	# given
	(tmp_path / "notes.txt").write_text("quarterly earnings", encoding="utf-8")
	monkeypatch.delenv("SRXY_TRANSCRIBE", raising=False)

	with (
		patch("srxy.cli.is_ocr_available", return_value=True),
		patch("srxy.cli.transcribe_deps_installed", return_value=True),
		patch("srxy.cli.ffmpeg_available", return_value=False),
	):
		# when
		exit_code = main(["earnings", str(tmp_path), "--semantic-all", "--content-only", "--no-progress"])

	# then
	captured = capsys.readouterr()
	assert exit_code == 2
	assert "ffmpeg" in captured.err


def test_given_semantic_image_threshold_flag_when_parsing_args_then_accepts_value():
	# when
	args = build_parser().parse_args(["sunset", ".", "--semantic-image-threshold", "0.25"])

	# then
	assert args.semantic_image_threshold == 0.25


def test_given_semantic_image_flag_without_dependency_when_running_cli_then_exits_two(
	tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
	# given
	(tmp_path / "photo.png").write_bytes(b"png")
	monkeypatch.delenv("SRXY_SEMANTIC_IMAGE", raising=False)

	with patch("srxy.cli.is_semantic_image_available", return_value=False):
		# when
		exit_code = main(["sunset", str(tmp_path), "--semantic-image", "--content-only", "--no-progress"])

	# then
	captured = capsys.readouterr()
	assert exit_code == 2
	assert "Image semantic search is disabled" in captured.err


def test_given_semantic_flag_without_cached_model_when_user_declines_then_exits_two(
	tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
	# given
	(tmp_path / "notes.txt").write_text("hello", encoding="utf-8")
	monkeypatch.setenv("SRXY_CACHE_DIR", str(tmp_path))

	with (
		patch("srxy.cli.sentence_transformers_installed", return_value=True),
		patch("srxy.cli.ensure_semantic_text_model", return_value=False),
	):
		# when
		exit_code = main(["hello", str(tmp_path), "--semantic", "--content-only", "--no-progress"])

	# then
	captured = capsys.readouterr()
	assert exit_code == 2
	assert "Semantic text model is not cached" in captured.err


def test_given_max_ocr_file_size_flag_when_parsing_args_then_accepts_value():
	# when
	args = build_parser().parse_args(["invoice", ".", "--ocr", "--max-ocr-file-size", "5000000"])

	# then
	assert args.max_ocr_file_size == 5_000_000


def test_given_ocr_flag_without_tesseract_when_running_cli_then_exits_two_with_message(
	tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
	# given
	(tmp_path / "notes.txt").write_text("invoice total", encoding="utf-8")
	monkeypatch.delenv("SRXY_OCR", raising=False)

	with patch("srxy.cli.is_ocr_available", return_value=False):
		# when
		exit_code = main(["invoice", str(tmp_path), "--ocr", "--content-only", "--no-progress"])

	# then
	captured = capsys.readouterr()
	assert exit_code == 2
	assert "Tesseract OCR is not available" in captured.err
	assert "tesseract binary on PATH" in captured.err
	assert captured.out == ""


def test_given_ocr_env_without_tesseract_when_running_cli_then_exits_two_with_message(
	tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
	# given
	(tmp_path / "notes.txt").write_text("invoice total", encoding="utf-8")
	monkeypatch.setenv("SRXY_OCR", "1")

	with patch("srxy.cli.is_ocr_available", return_value=False):
		# when
		exit_code = main(["invoice", str(tmp_path), "--content-only", "--no-progress"])

	# then
	captured = capsys.readouterr()
	assert exit_code == 2
	assert "Tesseract OCR is not available" in captured.err
	assert captured.out == ""


def test_given_transcribe_flag_without_deps_when_running_cli_then_exits_two_with_message(
	tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
	# given
	(tmp_path / "notes.txt").write_text("quarterly earnings", encoding="utf-8")
	monkeypatch.delenv("SRXY_TRANSCRIBE", raising=False)

	with patch("srxy.cli.transcribe_deps_installed", return_value=False):
		# when
		exit_code = main(["earnings", str(tmp_path), "--transcribe", "--content-only", "--no-progress"])

	# then
	captured = capsys.readouterr()
	assert exit_code == 2
	assert "srxy[semantic]" in captured.err
	assert captured.out == ""


def test_given_transcribe_flag_without_ffmpeg_when_running_cli_then_exits_two_with_message(
	tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
	# given
	(tmp_path / "notes.txt").write_text("quarterly earnings", encoding="utf-8")
	monkeypatch.delenv("SRXY_TRANSCRIBE", raising=False)

	with (
		patch("srxy.cli.transcribe_deps_installed", return_value=True),
		patch("srxy.cli.ffmpeg_available", return_value=False),
	):
		# when
		exit_code = main(["earnings", str(tmp_path), "--transcribe", "--content-only", "--no-progress"])

	# then
	captured = capsys.readouterr()
	assert exit_code == 2
	assert "ffmpeg" in captured.err
	assert captured.out == ""


def test_given_transcribe_flag_when_parsing_args_then_accepts_flag():
	# when
	args = build_parser().parse_args(["earnings", ".", "--transcribe"])

	# then
	assert args.transcribe is True


def test_given_transcript_match_when_formatting_grouped_then_shows_timestamp_in_header(tmp_path: Path):
	# given
	result = FileSearchResult(
		path=tmp_path / "song.flac",
		score=0.34,
		breakdown={"content": 0.34},
		lines=[
			LineMatch(
				line_number=160,
				text="And all the other boys",
				score=0.34,
				location_kind="transcript",
			)
		],
	)

	# when
	output = format_grouped([result], query="other boys")

	# then
	assert "transcript at 02:40  ·  score 0.34" in output
	assert "│ And all the «other boys»" in output
	assert "[02:40]" not in output


def test_given_transcript_match_when_formatting_json_then_uses_timestamp_label(tmp_path: Path):
	# given
	result = FileSearchResult(
		path=tmp_path / "song.flac",
		score=0.34,
		breakdown={"content": 0.34},
		lines=[
			LineMatch(
				line_number=160,
				text="And all the other boys",
				score=0.34,
				location_kind="transcript",
			)
		],
	)

	# when
	payload = format_json_result(result, query="other boys")
	lines = payload["lines"]
	assert isinstance(lines, list)

	# then
	first_line = lines[0]
	assert isinstance(first_line, dict)
	assert first_line["location_label"] == "transcript at 02:40"
	assert first_line["line_number"] == 160
	assert "[02:40]" not in first_line["text"]


def test_given_mp4_tag_match_when_formatting_grouped_then_shows_tag_label(tmp_path: Path):
	# given
	copy_media_fixture("minimal.mp4", tmp_path / "clip.mp4")
	file_path = tmp_path / "clip.mp4"
	result = FileSearchResult(
		path=file_path,
		score=0.47,
		breakdown={"content": 0.47},
		lines=[LineMatch(line_number=1, text="[Title] Quarterly revenue recap", score=0.47, location_kind="tag")],
	)

	# when
	output = format_grouped([result], query="revenue")

	# then
	assert 'for "revenue"' in output
	assert "tag 1  ·  score 0.47" in output
	assert "│ [Title] Quarterly «revenue» recap" in output


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


def test_given_grouped_result_when_formatting_single_block_then_omits_summary_header(tmp_path: Path):
	# given
	file_path = tmp_path / "notes.txt"
	result = FileSearchResult(
		path=file_path,
		score=0.8,
		breakdown={"content": 0.8},
		lines=[LineMatch(line_number=1, text="hello", score=0.8)],
	)

	# when
	output = format_grouped_result(result, query="hello")

	# then
	assert "files matched" not in output
	assert f"── {file_path.as_posix()} ──" in output


def test_given_repeated_line_previews_when_formatting_grouped_then_collapses_identical_matches(tmp_path: Path):
	# given
	file_path = tmp_path / "script.sh"
	line_numbers = [15, 25, 34, 39, 42, 45]
	result = FileSearchResult(
		path=file_path,
		score=0.31,
		breakdown={"content": 0.31},
		lines=[LineMatch(line_number=number, text="fi", score=0.31) for number in line_numbers],
	)

	# when
	output = format_grouped_result(result, query="fi")

	# then
	assert output.count("│ «fi»") == 1
	assert "lines 15, 25, 34, 39, 42, 45  ·  score 0.31" in output
	assert "line 15  ·  score 0.31" not in output


def test_given_consecutive_line_previews_when_formatting_grouped_then_uses_ranges(tmp_path: Path):
	# given
	file_path = tmp_path / "notes.txt"
	result = FileSearchResult(
		path=file_path,
		score=0.5,
		breakdown={"content": 0.5},
		lines=[
			LineMatch(line_number=10, text="fi", score=0.5),
			LineMatch(line_number=11, text="fi", score=0.5),
			LineMatch(line_number=12, text="fi", score=0.5),
			LineMatch(line_number=20, text="fi", score=0.5),
		],
	)

	# when
	output = format_grouped_result(result, query="fi")

	# then
	assert "lines 10-12, 20  ·  score 0.50" in output
	assert output.count("│ «fi»") == 1


def test_given_mixed_line_previews_when_formatting_grouped_then_keeps_distinct_groups(tmp_path: Path):
	# given
	file_path = tmp_path / "notes.txt"
	result = FileSearchResult(
		path=file_path,
		score=0.8,
		breakdown={"content": 0.8},
		lines=[
			LineMatch(line_number=1, text="alpha fi beta", score=0.8),
			LineMatch(line_number=2, text="fi", score=0.8),
			LineMatch(line_number=3, text="fi", score=0.8),
		],
	)

	# when
	output = format_grouped_result(result, query="fi")

	# then
	assert output.count("│") == 2
	assert "lines 2-3  ·  score 0.80" in output
	assert "line 1  ·  score 0.80" in output


def test_given_grouped_stream_when_running_cli_then_prints_summary_after_matches(
	tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
	# given
	(tmp_path / "notes.txt").write_text("quarterly revenue projections", encoding="utf-8")

	# when
	exit_code = main(["revenue", str(tmp_path), "--content-only", "--no-progress"])

	# then
	captured = capsys.readouterr()
	assert exit_code == 0
	assert captured.out.index("1 file matched") > captured.out.index("──")
	assert 'for "revenue"' in captured.out


def test_given_multiple_matches_when_running_cli_then_prints_highest_score_first(
	tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
	# given
	(tmp_path / "weak.txt").write_text("rev", encoding="utf-8")
	(tmp_path / "strong.txt").write_text("quarterly revenue projections", encoding="utf-8")

	# when
	exit_code = main(["revenue", str(tmp_path), "--content-only", "--no-progress"])

	# then
	captured = capsys.readouterr()
	assert exit_code == 0
	weak_index = captured.out.index("weak.txt")
	strong_index = captured.out.index("strong.txt")
	assert strong_index < weak_index


def test_given_limit_flag_when_running_cli_then_returns_top_matches_only(
	tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
	# given
	(tmp_path / "a.txt").write_text("revenue alpha", encoding="utf-8")
	(tmp_path / "b.txt").write_text("revenue beta", encoding="utf-8")
	(tmp_path / "c.txt").write_text("revenue gamma", encoding="utf-8")

	# when
	exit_code = main(["revenue", str(tmp_path), "--content-only", "--no-progress", "--limit", "2"])

	# then
	captured = capsys.readouterr()
	assert exit_code == 0
	assert "2 files matched" in captured.out
	assert captured.out.count(".txt ──") == 2


def test_given_match_found_when_flashing_progress_then_shows_match_found_in_bar():
	# given
	stream = MagicMock()
	stream.isatty.return_value = True
	bar = ProgressBar(stream=stream)
	bar.update(2, 5)

	# when
	bar.flash_match()
	bar.refresh()

	# then
	written = "".join(call.args[0] for call in stream.write.call_args_list)
	assert "match found" in written
	assert "2/5 files" in written


def test_given_results_when_running_cli_with_output_flag_then_writes_saved_file(
	tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
	# given
	(tmp_path / "notes.txt").write_text("quarterly revenue projections", encoding="utf-8")
	output_path = tmp_path / "results.txt"

	# when
	exit_code = main(
		[
			"revenue",
			str(tmp_path),
			"--content-only",
			"--format",
			"flat",
			"--output",
			str(output_path),
			"--no-progress",
		]
	)

	# then
	captured = capsys.readouterr()
	assert exit_code == 0
	assert "notes.txt:line:1:" in captured.out
	saved = output_path.read_text(encoding="utf-8")
	assert "notes.txt:line:1:" in saved


def test_given_no_matches_when_running_cli_with_json_then_prints_empty_array(
	tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
	# given
	(tmp_path / "notes.txt").write_text("hello", encoding="utf-8")

	# when
	exit_code = main(["zzzzzzzz", str(tmp_path), "--json", "--no-progress"])

	# then
	captured = capsys.readouterr()
	assert exit_code == 1
	assert captured.out.strip() == "[]"
	assert 'No matches for "zzzzzzzz"' in captured.err


def test_given_progress_bar_when_updating_on_tty_then_redraws_same_line(monkeypatch: pytest.MonkeyPatch):
	# given
	written: list[str] = []

	class FakeTTY:
		def fileno(self) -> int:
			return 2

		def isatty(self) -> bool:
			return True

		def write(self, text: str) -> None:
			written.append(text)

		def flush(self) -> None:
			pass

	monkeypatch.setattr("srxy.cli._terminal_size", lambda _stream: (80, 24))
	progress = ProgressBar(FakeTTY())  # type: ignore[arg-type]

	# when
	progress.update(3, 10)
	progress.update(10, 10)
	progress.finish()

	# then
	output = "".join(written)
	assert "\033[1;23r" not in output
	assert "\033[r" not in output
	assert "3/10 files" in output
	assert "10/10 files" in output
	assert output.count("\r\x1b[2K") >= 2


def test_given_progress_bar_when_writing_above_then_prints_to_stdout(capsys: pytest.CaptureFixture[str]):
	# given
	written: list[str] = []

	class FakeTTY:
		def fileno(self) -> int:
			return 2

		def isatty(self) -> bool:
			return True

		def write(self, text: str) -> None:
			written.append(text)

		def flush(self) -> None:
			pass

	progress = ProgressBar(FakeTTY())  # type: ignore[arg-type]
	progress.update(1, 10)

	# when
	progress.write_above("match line", sys.stdout)

	# then
	captured = capsys.readouterr()
	assert captured.out == "match line\n"
	assert "".join(written).startswith("\r\x1b[2K")


def test_given_render_progress_when_completing_on_tty_then_finishes_bar(monkeypatch: pytest.MonkeyPatch):
	# given
	written: list[str] = []

	class FakeTTY:
		def fileno(self) -> int:
			return 2

		def isatty(self) -> bool:
			return True

		def write(self, text: str) -> None:
			written.append(text)

		def flush(self) -> None:
			pass

	monkeypatch.setattr("srxy.cli._terminal_size", lambda _stream: (80, 24))

	# when
	render_progress(10, 10, stream=FakeTTY())  # type: ignore[arg-type]

	# then
	output = "".join(written)
	assert "10/10 files" in output
	assert output.endswith("\n")


def test_given_progress_bar_when_setting_activity_then_renders_spinner(monkeypatch: pytest.MonkeyPatch):
	# given
	written: list[str] = []

	class FakeTTY:
		def fileno(self) -> int:
			return 2

		def isatty(self) -> bool:
			return True

		def write(self, text: str) -> None:
			written.append(text)

		def flush(self) -> None:
			pass

	monkeypatch.setattr("srxy.cli._terminal_size", lambda _stream: (80, 24))
	progress = ProgressBar(FakeTTY())  # type: ignore[arg-type]

	# when
	progress.set_activity("Encoding image query…")
	time.sleep(0.15)
	progress.set_activity(None)
	progress.finish()

	# then
	output = "".join(written)
	assert "Encoding image query" in output
