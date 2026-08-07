from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from srxy.adapters.inbound.cli.cli import build_parser
from srxy.adapters.outbound.worker.search_worker import (
	args_to_payload,
	build_worker_env,
	file_result_from_dict,
	file_result_to_dict,
	run_worker_main,
	search_uses_subprocess,
	stderr_error_message,
)
from srxy.domain.models import FileSearchResult, LineMatch, SkippedFile


pytestmark = pytest.mark.unit


def _build_args(argv: list[str]) -> argparse.Namespace:
	return build_parser().parse_args(argv)


def test_given_semantic_image_flag_when_search_uses_subprocess_then_returns_true():
	# given
	args = _build_args(["person", ".", "--semantic-image"])

	# when / then
	assert search_uses_subprocess(args) is True


def test_given_ocr_flag_when_search_uses_subprocess_then_returns_true():
	# given
	args = _build_args(["transform", ".", "--ocr"])

	# when / then
	assert search_uses_subprocess(args) is True


def test_given_name_only_search_when_search_uses_subprocess_then_returns_false():
	# given
	args = _build_args(["person", "."])

	# when / then
	assert search_uses_subprocess(args) is False


def test_given_file_search_result_when_round_trip_dict_then_preserves_fields(tmp_path: Path):
	# given
	result = FileSearchResult(
		path=tmp_path / "photo.png",
		score=0.86,
		breakdown={"ocr": 0.86},
		lines=[LineMatch(line_number=1, text="revenue", score=0.9, location_kind="ocr")],
	)

	# when
	restored = file_result_from_dict(file_result_to_dict(result))

	# then
	assert restored == result


def test_given_worker_args_when_run_worker_main_then_emits_json_events(monkeypatch: pytest.MonkeyPatch):
	# given
	args = _build_args(["transform", ".", "--ocr", "--cli"])
	result = FileSearchResult(path=Path("doc.png"), score=0.5, lines=[])
	skipped = [SkippedFile(path=Path("big.png"), size_bytes=99)]
	stdout = StringIO()
	monkeypatch.setattr("sys.stdin", StringIO(json.dumps(args_to_payload(args)) + "\n"))
	monkeypatch.setattr("sys.stdout", stdout)
	monkeypatch.setattr(
		"srxy.application.search_runner.FileSearchService.execute",
		MagicMock(return_value=([result], skipped)),
	)

	# when
	run_worker_main()

	# then
	events = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
	finished = next(event for event in events if event.get("type") == "finished")
	assert finished["cancelled"] is False
	assert finished["results"] == [file_result_to_dict(result)]
	assert finished["skipped_files"] == [{"path": "big.png", "size_bytes": 99, "reason": "oversized"}]
	assert events[-1] == {"type": "done"}


def test_given_parent_env_when_build_worker_env_then_inherits_platform_paths(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_SEMANTIC", "1")
	monkeypatch.setenv("CUSTOM_PARENT_ONLY", "keep-me")

	# when
	env = build_worker_env()

	# then
	assert env["SRXY_SEMANTIC"] == "1"
	assert env["CUSTOM_PARENT_ONLY"] == "keep-me"
	assert env["PATH"] == os.environ["PATH"]
	if os.name == "nt":
		system_root = env.get("SYSTEMROOT") or env.get("SystemRoot")
		assert system_root == os.environ.get("SYSTEMROOT") or os.environ.get("SystemRoot")


def test_given_worker_args_when_run_worker_main_then_sets_worker_env(
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	args = _build_args(["transform", ".", "--ocr", "--cli"])
	stdout = StringIO()
	for key in ("TQDM_DISABLE", "JOBLIB_MULTIPROCESSING"):
		monkeypatch.delenv(key, raising=False)
	monkeypatch.setattr("sys.stdin", StringIO(json.dumps(args_to_payload(args)) + "\n"))
	monkeypatch.setattr("sys.stdout", stdout)
	monkeypatch.setattr(
		"srxy.application.search_runner.FileSearchService.execute",
		MagicMock(return_value=([], [])),
	)

	# when
	run_worker_main()

	# then
	assert os.environ["TQDM_DISABLE"] == "1"
	assert os.environ["JOBLIB_MULTIPROCESSING"] == "0"


def test_given_warning_only_stderr_when_stderr_error_message_then_returns_none():
	# given
	stderr = b"warning: transcription produced no speech segments for cached content abc\n"

	# when / then
	assert stderr_error_message(stderr) is None


def test_given_fatal_stderr_line_when_stderr_error_message_then_returns_fatal_line():
	# given
	stderr = (
		b"warning: transcription produced no speech segments for cached content abc\nRuntimeError: worker crashed\n"
	)

	# when / then
	assert stderr_error_message(stderr) == "RuntimeError: worker crashed"


class _MockStdin:
	def write(self, data: bytes):
		pass

	async def drain(self):
		pass

	def close(self):
		pass


class _MockStdout:
	def __init__(self, lines: list[bytes] | None = None):
		self._lines = list(lines or [])

	async def readline(self) -> bytes:
		if self._lines:
			return self._lines.pop(0)
		return b""


class _MockProcess:
	def __init__(self, stdout_lines: list[bytes] | None = None):
		self.stdin = _MockStdin()
		self.stdout = _MockStdout(stdout_lines)
		self.stderr = None
		self.returncode: int | None = None

	def kill(self):
		self.returncode = -9

	async def wait(self) -> int | None:
		return self.returncode


async def _collect_subprocess_events(
	args: argparse.Namespace,
	monkeypatch: pytest.MonkeyPatch,
	*,
	cancel_check: Callable[[], bool],
	stdout_lines: list[bytes] | None = None,
) -> list[dict[str, object]]:
	import asyncio

	from srxy.adapters.outbound.worker.search_worker import iter_subprocess_search_events

	events: list[dict[str, object]] = []

	async def fake_exec(*_args: object, **_kwargs: object) -> _MockProcess:
		return _MockProcess(stdout_lines)

	monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
	async for event in iter_subprocess_search_events(args, cancel_check=cancel_check):
		events.append(event)
	return events


def test_given_cancel_check_when_iter_subprocess_before_read_then_yields_cancelled_finished(
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	import asyncio

	args = _build_args(["person", "."])

	# when
	events = asyncio.run(_collect_subprocess_events(args, monkeypatch, cancel_check=lambda: True))

	# then
	assert events == [{"type": "finished", "cancelled": True, "skipped_files": []}]


def test_given_cancel_check_when_stdout_eof_then_yields_cancelled_finished_not_error(
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	import asyncio

	args = _build_args(["person", "."])
	calls = {"count": 0}

	def cancel_check() -> bool:
		calls["count"] += 1
		return calls["count"] >= 2

	# when
	events = asyncio.run(_collect_subprocess_events(args, monkeypatch, cancel_check=cancel_check))

	# then
	assert events == [{"type": "finished", "cancelled": True, "skipped_files": []}]


def test_given_no_cancel_when_stdout_eof_then_yields_worker_error(monkeypatch: pytest.MonkeyPatch):
	# given
	import asyncio

	args = _build_args(["person", "."])

	# when
	events = asyncio.run(_collect_subprocess_events(args, monkeypatch, cancel_check=lambda: False))

	# then
	assert events == [{"type": "error", "message": "search worker exited unexpectedly"}]
