from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from srxy.adapters.inbound.cli.cli import build_parser, main
from srxy.i18n import tr


pytestmark = pytest.mark.unit


@pytest.fixture
def search_spy(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
	"""Replace the app services so any attempt to search is recorded."""
	services = MagicMock()
	services.file_search.execute.return_value = ([], [])
	factory = MagicMock(return_value=services)
	monkeypatch.setattr("srxy.bootstrap.build_app_services", factory)
	return services.file_search.execute


def _stderr_last_line(captured_err: str) -> str:
	return captured_err.strip().splitlines()[-1]


def _json_names(stdout: str) -> set[str]:
	payload = json.loads(stdout)
	assert isinstance(payload, list)
	return {Path(item["path"]).name for item in payload}


def _make_log_tree(root: Path):
	(root / "debug.log").write_text("needle in log", encoding="utf-8")
	(root / "keep.log").write_text("needle in keep", encoding="utf-8")
	(root / "notes.txt").write_text("needle in notes", encoding="utf-8")


def test_given_unclosed_bracket_when_running_cli_then_exits_two_with_localised_error_and_no_search(
	tmp_path: Path, capsys: pytest.CaptureFixture[str], search_spy: MagicMock
):
	# given
	argv = ["needle", str(tmp_path), "--ignore", "[oops", "--language", "en", "--no-progress"]

	# when
	with pytest.raises(SystemExit) as exc_info:
		main(argv)

	# then
	captured = capsys.readouterr()
	last_line = _stderr_last_line(captured.err)
	reason = tr("ignore.reason.unclosed_bracket")
	assert exc_info.value.code == 2
	assert last_line.endswith("srxy: error: --ignore '[oops': unclosed \u201c[\u201d in pattern")
	assert reason != "ignore.reason.unclosed_bracket"
	search_spy.assert_not_called()


def test_given_trailing_backslash_when_running_cli_then_exits_two_with_reason(
	tmp_path: Path, capsys: pytest.CaptureFixture[str], search_spy: MagicMock
):
	# given
	argv = ["needle", str(tmp_path), "--ignore", "dir\\", "--language", "en"]

	# when
	with pytest.raises(SystemExit) as exc_info:
		main(argv)

	# then
	last_line = _stderr_last_line(capsys.readouterr().err)
	assert exc_info.value.code == 2
	assert "srxy: error: --ignore 'dir\\\\'" in last_line
	assert tr("ignore.reason.trailing_backslash") in last_line
	search_spy.assert_not_called()


def test_given_1001_ignore_values_when_running_cli_then_exits_two_and_no_search(
	tmp_path: Path, capsys: pytest.CaptureFixture[str], search_spy: MagicMock
):
	# given
	argv = ["needle", str(tmp_path), "--language", "en"]
	for index in range(1001):
		argv += ["--ignore", f"pattern{index}"]

	# when
	with pytest.raises(SystemExit) as exc_info:
		main(argv)

	# then
	last_line = _stderr_last_line(capsys.readouterr().err)
	assert exc_info.value.code == 2
	assert "srxy: error: --ignore" in last_line
	assert tr("ignore.reason.too_many_lines") in last_line
	search_spy.assert_not_called()


def test_given_1000_ignore_values_when_running_cli_then_accepted(tmp_path: Path, search_spy: MagicMock):
	# given
	(tmp_path / "notes.txt").write_text("needle", encoding="utf-8")
	argv = ["needle", str(tmp_path), "--no-progress", "--json"]
	for index in range(1000):
		argv += ["--ignore", f"pattern{index}"]

	# when
	main(argv)

	# then
	search_spy.assert_called_once()


def test_given_value_over_1024_chars_when_running_cli_then_exits_two_and_no_search(
	tmp_path: Path, capsys: pytest.CaptureFixture[str], search_spy: MagicMock
):
	# given
	argv = ["needle", str(tmp_path), "--ignore", "a" * 1025, "--language", "en"]

	# when
	with pytest.raises(SystemExit) as exc_info:
		main(argv)

	# then
	last_line = _stderr_last_line(capsys.readouterr().err)
	assert exc_info.value.code == 2
	assert "srxy: error: --ignore" in last_line
	assert tr("ignore.reason.line_too_long") in last_line
	search_spy.assert_not_called()


def test_given_value_of_1024_chars_when_running_cli_then_accepted(tmp_path: Path, search_spy: MagicMock):
	# given
	(tmp_path / "notes.txt").write_text("needle", encoding="utf-8")
	argv = ["needle", str(tmp_path), "--ignore", "a" * 1024, "--no-progress", "--json"]

	# when
	main(argv)

	# then
	search_spy.assert_called_once()


def test_given_value_with_newline_when_running_cli_then_exits_two_and_no_search(
	tmp_path: Path, capsys: pytest.CaptureFixture[str], search_spy: MagicMock
):
	# given
	argv = ["needle", str(tmp_path), "--ignore", "a\nb", "--language", "en"]

	# when
	with pytest.raises(SystemExit) as exc_info:
		main(argv)

	# then
	captured = capsys.readouterr()
	assert exc_info.value.code == 2
	assert tr("ignore.reason.multiline") in captured.err
	search_spy.assert_not_called()


def test_given_repeated_ignore_flags_when_parsing_then_args_ignore_keeps_order():
	# given
	parser = build_parser()

	# when
	args = parser.parse_args(["q", ".", "--ignore", "*.log", "--ignore", "build/", "--ignore", "!keep.log"])

	# then
	assert args.ignore == ["*.log", "build/", "!keep.log"]


def test_given_no_ignore_flag_when_parsing_then_args_ignore_is_empty():
	# given
	parser = build_parser()

	# when
	args = parser.parse_args(["q", "."])

	# then
	assert not args.ignore
	assert args.respect_gitignore is False


def test_given_respect_gitignore_flag_when_parsing_then_args_respect_gitignore_is_true():
	# given
	parser = build_parser()

	# when
	args = parser.parse_args(["q", ".", "--respect-gitignore"])

	# then
	assert args.respect_gitignore is True


def test_given_ignore_glob_and_json_when_running_cli_then_top_level_array_excludes_ignored_file(
	tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
	# given
	_make_log_tree(tmp_path)

	# when
	exit_code = main(["needle", str(tmp_path), "--content-only", "--ignore", "*.log", "--json", "--no-progress"])

	# then
	captured = capsys.readouterr()
	assert exit_code == 0
	assert _json_names(captured.out) == {"notes.txt"}


def test_given_reinclude_pattern_when_running_cli_then_only_kept_log_survives(
	tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
	# given
	_make_log_tree(tmp_path)

	# when
	exit_code = main(
		[
			"needle",
			str(tmp_path),
			"--content-only",
			"--ignore",
			"*.log",
			"--ignore",
			"!keep.log",
			"--json",
			"--no-progress",
		]
	)

	# then
	captured = capsys.readouterr()
	assert exit_code == 0
	assert _json_names(captured.out) == {"keep.log", "notes.txt"}


def test_given_ignored_folder_when_running_cli_then_nothing_beneath_it_is_searched(
	tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
	# given
	(tmp_path / "build").mkdir()
	(tmp_path / "build" / "out.txt").write_text("needle", encoding="utf-8")
	(tmp_path / "src.txt").write_text("needle", encoding="utf-8")

	# when
	exit_code = main(["needle", str(tmp_path), "--content-only", "--ignore", "build/", "--json", "--no-progress"])

	# then
	captured = capsys.readouterr()
	assert exit_code == 0
	assert _json_names(captured.out) == {"src.txt"}


def test_given_gitignore_and_flag_when_running_cli_then_gitignored_file_is_skipped(
	tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
	# given
	_make_log_tree(tmp_path)
	(tmp_path / ".gitignore").write_text("*.log\n", encoding="utf-8")

	# when
	exit_code = main(["needle", str(tmp_path), "--content-only", "--respect-gitignore", "--json", "--no-progress"])

	# then
	captured = capsys.readouterr()
	assert exit_code == 0
	assert _json_names(captured.out) == {"notes.txt"}


def test_given_gitignore_without_flag_when_running_cli_then_gitignored_file_is_searched(
	tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
	# given
	_make_log_tree(tmp_path)
	(tmp_path / ".gitignore").write_text("*.log\n", encoding="utf-8")

	# when
	exit_code = main(["needle", str(tmp_path), "--content-only", "--json", "--no-progress"])

	# then
	captured = capsys.readouterr()
	assert exit_code == 0
	assert _json_names(captured.out) == {"debug.log", "keep.log", "notes.txt"}


def test_given_cli_list_and_gitignore_when_running_cli_then_cli_list_overrides_gitignore(
	tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
	# given
	_make_log_tree(tmp_path)
	(tmp_path / ".gitignore").write_text("*.log\n", encoding="utf-8")

	# when
	exit_code = main(
		[
			"needle",
			str(tmp_path),
			"--content-only",
			"--respect-gitignore",
			"--ignore",
			"!keep.log",
			"--json",
			"--no-progress",
		]
	)

	# then
	captured = capsys.readouterr()
	assert exit_code == 0
	assert _json_names(captured.out) == {"keep.log", "notes.txt"}


def test_given_escaped_slash_when_running_cli_then_exits_two_with_reason(
	tmp_path: Path, capsys: pytest.CaptureFixture[str], search_spy: MagicMock
):
	# given
	argv = ["needle", str(tmp_path), "--ignore", "foo\\/", "--language", "en"]

	# when
	with pytest.raises(SystemExit) as exc_info:
		main(argv)

	# then
	last_line = _stderr_last_line(capsys.readouterr().err)
	assert exc_info.value.code == 2
	assert "srxy: error: --ignore" in last_line
	assert tr("ignore.reason.trailing_backslash") in last_line
	search_spy.assert_not_called()
