from __future__ import annotations

import argparse
import json
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from srxy.adapters.inbound.cli.cli import build_parser
from srxy.adapters.outbound.worker.search_worker import (
	args_to_payload,
	run_worker_main,
)
from srxy.application.search_control import MAX_PROGRESSIVE_RESULT_EVENTS, SearchCancelled
from srxy.domain.models import FileSearchResult


pytestmark = pytest.mark.unit


def _build_args(argv: list[str]) -> argparse.Namespace:
	return build_parser().parse_args(argv)


def test_given_many_worker_results_when_run_worker_main_then_caps_progressive_events(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	args = _build_args(["token", str(tmp_path), "--cli"])
	results = [
		FileSearchResult(path=tmp_path / f"f{i}.txt", score=1.0, breakdown={}, lines=[])
		for i in range(MAX_PROGRESSIVE_RESULT_EVENTS + 10)
	]
	stdout = StringIO()
	monkeypatch.setattr("sys.stdin", StringIO(json.dumps(args_to_payload(args)) + "\n"))
	monkeypatch.setattr("sys.stdout", stdout)

	mock_file_search = MagicMock()

	def _execute(
		_args: argparse.Namespace,
		*,
		skipped_files: list[Any] | None = None,
		on_progress: Any = None,
		on_activity: Any = None,
		on_result: Any = None,
		cancel_check: Any = None,
		allow_process_pool: bool = False,
	):
		_ = (on_progress, on_activity, cancel_check, allow_process_pool)
		if on_result is not None:
			for item in results:
				on_result(item)
		return results, skipped_files or []

	mock_file_search.execute.side_effect = _execute
	mock_services = MagicMock(file_search=mock_file_search)
	monkeypatch.setattr(
		"srxy.bootstrap.build_worker_services",
		lambda: mock_services,
	)

	run_worker_main()

	events = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
	result_events = [event for event in events if event.get("type") == "result"]
	finished = next(event for event in events if event.get("type") == "finished")

	assert len(result_events) == MAX_PROGRESSIVE_RESULT_EVENTS
	assert "results" in finished
	assert len(finished["results"]) == len(results)


def test_given_cancelled_worker_search_when_run_worker_main_then_marks_finished_cancelled(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
):
	args = _build_args(["token", str(tmp_path), "--cli"])
	stdout = StringIO()
	monkeypatch.setattr("sys.stdin", StringIO(json.dumps(args_to_payload(args)) + "\n"))
	monkeypatch.setattr("sys.stdout", stdout)

	def _raise_cancel(*_args: object, **_kwargs: object):
		raise SearchCancelled()

	monkeypatch.setattr(
		"srxy.application.search_runner.FileSearchService.execute",
		MagicMock(side_effect=_raise_cancel),
	)

	run_worker_main()

	finished = next(
		event
		for event in (json.loads(line) for line in stdout.getvalue().splitlines() if line.strip())
		if event.get("type") == "finished"
	)
	assert finished["cancelled"] is True
