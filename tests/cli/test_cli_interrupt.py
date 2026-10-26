from __future__ import annotations

import io
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from srxy.adapters.inbound.cli import cli
from srxy.domain.models import FileSearchResult
from srxy.domain.progress import ActivityUpdate


pytestmark = pytest.mark.unit


@pytest.mark.parametrize("options", [["--progress"], ["--no-progress"], ["--no-progress", "--json"]])
def test_given_running_search_when_interrupted_then_cleans_up_and_exits_130(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], options: list[str]
):
	# given
	class Terminal(io.StringIO):
		def isatty(self) -> bool:
			return True

	stderr = Terminal()
	progress = cli.ProgressBar(stderr)
	spinners: list[threading.Thread] = []
	closed_writers: list[cli.StreamingResultWriter] = []
	original_close = cli.StreamingResultWriter.close

	def close(writer: cli.StreamingResultWriter):
		original_close(writer)
		closed_writers.append(writer)

	def interrupt(_args, **callbacks):
		callbacks["on_progress"](1, 10)
		callbacks["on_activity"](ActivityUpdate(label="Reading file"))
		if progress._spinner_thread is not None:
			spinners.append(progress._spinner_thread)
		raise KeyboardInterrupt

	monkeypatch.setattr(cli.sys, "stderr", stderr)
	monkeypatch.setattr(cli, "ProgressBar", lambda: progress)
	monkeypatch.setattr(
		"srxy.bootstrap.build_app_services", lambda: SimpleNamespace(file_search=Mock(execute=interrupt))
	)
	monkeypatch.setattr(cli.StreamingResultWriter, "close", close)
	output_path = tmp_path / "results.txt"

	# when
	try:
		exit_code = cli.main(["--cli", "README", str(tmp_path), "--output", str(output_path), *options])
	except KeyboardInterrupt:
		pytest.fail("KeyboardInterrupt escaped the CLI boundary")

	# then
	assert exit_code == 130
	assert stderr.getvalue().endswith("Search cancelled.\n")
	assert "Traceback" not in stderr.getvalue()
	assert capsys.readouterr().out == ""
	assert len(closed_writers) == 1
	assert closed_writers[0]._output_handle is not None
	assert closed_writers[0]._output_handle.closed
	assert not any(thread.is_alive() for thread in spinners)
	if "--progress" in options:
		assert spinners
		assert "\x1b[2K\n\x1b[2K\x1b[1A" in stderr.getvalue()


def test_given_preflight_when_interrupted_then_exits_130(capsys: pytest.CaptureFixture[str]):
	# given
	with patch.object(cli, "run_preflight", side_effect=KeyboardInterrupt):
		# when
		try:
			exit_code = cli.main(["--cli", "README", "--no-progress"])
		except KeyboardInterrupt:
			pytest.fail("KeyboardInterrupt escaped preflight")

	# then
	assert exit_code == 130
	captured = capsys.readouterr()
	assert captured.out == ""
	assert captured.err == "Search cancelled.\n"


@pytest.mark.parametrize("stage", ["write_result", "finalize"])
def test_given_result_output_when_interrupted_then_closes_file_and_exits_130(
	tmp_path: Path, capsys: pytest.CaptureFixture[str], stage: str
):
	# given
	result = FileSearchResult(path=tmp_path / "README", score=1.0, breakdown={"name": 1.0})
	services = SimpleNamespace(file_search=Mock(execute=Mock(return_value=([result], []))))
	closed_writers: list[cli.StreamingResultWriter] = []
	original_close = cli.StreamingResultWriter.close

	def close(writer: cli.StreamingResultWriter):
		original_close(writer)
		closed_writers.append(writer)

	with (
		patch("srxy.bootstrap.build_app_services", return_value=services),
		patch.object(cli.StreamingResultWriter, stage, side_effect=KeyboardInterrupt),
		patch.object(cli.StreamingResultWriter, "close", close),
	):
		# when
		try:
			exit_code = cli.main(["--cli", "README", "--no-progress", "--output", str(tmp_path / "results.txt")])
		except KeyboardInterrupt:
			pytest.fail("KeyboardInterrupt escaped result output")

	# then
	assert exit_code == 130
	assert capsys.readouterr().err == "Search cancelled.\n"
	assert len(closed_writers) == 1
	assert closed_writers[0]._output_handle is not None
	assert closed_writers[0]._output_handle.closed
