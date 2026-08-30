from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

import pytest

from srxy.application.search_runner import FileSearchService
from srxy.application.search_session import (
	SearchErrorEvent,
	SearchFinishedEvent,
	SearchProgressEvent,
	SearchResultEvent,
	SearchSession,
)
from srxy.domain.models import FileSearchResult, SkippedFile
from srxy.domain.progress import ActivityCallback
from srxy.ports.inbound.file_search import FileSearchPort


pytestmark = pytest.mark.unit


def _args(path: Path, query: str) -> argparse.Namespace:
	from srxy.adapters.inbound.cli.cli import build_parser

	return build_parser().parse_args([query, str(path), "--cli"])


class _FakeFileSearch:
	def __init__(self, results: list[FileSearchResult] | None = None, *, error: Exception | None = None):
		self.results = results or []
		self.error = error
		self.calls = 0

	def execute(
		self,
		args: argparse.Namespace,
		*,
		skipped_files: list[SkippedFile] | None = None,
		on_progress: Callable[[int, int], None] | None = None,
		on_activity: ActivityCallback | None = None,
		on_result: Callable[[FileSearchResult], None] | None = None,
		cancel_check: Callable[[], bool] | None = None,
		allow_process_pool: bool = False,
	) -> tuple[list[FileSearchResult], list[SkippedFile]]:
		self.calls += 1
		_ = (args, cancel_check, allow_process_pool)
		if self.error is not None:
			raise self.error
		if on_progress is not None:
			on_progress(1, 1)
		for result in self.results:
			if on_result is not None:
				on_result(result)
		effective = skipped_files if skipped_files is not None else []
		return self.results, effective


def test_given_fixture_tree_when_search_session_runs_then_emits_progress_and_results(tmp_path: Path):
	(tmp_path / "hello.txt").write_text("hello world\n", encoding="utf-8")
	events: list[object] = []
	session = SearchSession(FileSearchService())

	session.run_blocking(_args(tmp_path, "hello"), on_event=events.append)

	assert any(isinstance(event, SearchProgressEvent) for event in events) or any(
		isinstance(event, SearchResultEvent) for event in events
	)
	finished = [event for event in events if isinstance(event, SearchFinishedEvent)]
	assert len(finished) == 1
	all_results = finished[0].results or [event.result for event in events if isinstance(event, SearchResultEvent)]
	assert all_results
	assert all(isinstance(item, FileSearchResult) for item in all_results)


def test_given_fake_file_search_when_session_runs_then_uses_injected_port(tmp_path: Path):
	result = FileSearchResult(path=tmp_path / "a.txt", score=0.9, breakdown={"content": 0.9}, lines=[])
	fake: FileSearchPort = _FakeFileSearch([result])
	events: list[object] = []

	SearchSession(fake).run_blocking(_args(tmp_path, "a"), on_event=events.append)

	assert fake.calls == 1  # type: ignore[attr-defined]
	assert any(isinstance(event, SearchResultEvent) and event.result is result for event in events)
	progressive = [event for event in events if isinstance(event, SearchResultEvent)]
	assert progressive
	assert progressive[0].labels  # computed off the GUI thread before emit
	finished = [event for event in events if isinstance(event, SearchFinishedEvent)]
	assert len(finished) == 1
	finished_results = finished[0].results or [event.result for event in events if isinstance(event, SearchResultEvent)]
	assert finished_results == [result]


def test_given_file_search_raises_when_session_runs_then_emits_error(tmp_path: Path):
	fake = _FakeFileSearch(error=RuntimeError("boom"))
	events: list[object] = []

	SearchSession(fake).run_blocking(_args(tmp_path, "a"), on_event=events.append)

	assert any(isinstance(event, SearchErrorEvent) and event.message == "boom" for event in events)
	assert not any(isinstance(event, SearchFinishedEvent) for event in events)


def test_given_many_results_when_session_runs_then_caps_progressive_result_events(tmp_path: Path):
	from srxy.application.search_control import MAX_PROGRESSIVE_RESULT_EVENTS

	results = [
		FileSearchResult(path=tmp_path / f"f{i}.txt", score=1.0, breakdown={"name": 1.0}, lines=[])
		for i in range(MAX_PROGRESSIVE_RESULT_EVENTS + 40)
	]
	fake: FileSearchPort = _FakeFileSearch(results)
	events: list[object] = []

	SearchSession(fake).run_blocking(_args(tmp_path, "f"), on_event=events.append)

	progressive = [event for event in events if isinstance(event, SearchResultEvent)]
	finished = [event for event in events if isinstance(event, SearchFinishedEvent)]
	assert len(progressive) == MAX_PROGRESSIVE_RESULT_EVENTS
	assert len(finished) == 1
	assert len(finished[0].results) == len(results)


def test_given_subprocess_result_payload_when_decoding_then_labels_round_trip(tmp_path: Path):
	from srxy.application.subprocess_events import subprocess_event_to_search_event

	path = tmp_path / "note.txt"
	event = subprocess_event_to_search_event(
		{
			"type": "result",
			"result": {
				"path": str(path),
				"score": 0.9,
				"breakdown": {"content": 0.9},
				"lines": [],
			},
			"labels": "name, content",
		}
	)
	assert isinstance(event, SearchResultEvent)
	assert event.labels == "name, content"
	assert event.result.path == path


def test_given_cancel_during_progress_when_session_runs_then_returns_partial_finished(tmp_path: Path):
	class _CancellingSearch:
		def execute(
			self,
			args: argparse.Namespace,
			*,
			skipped_files: list[SkippedFile] | None = None,
			on_progress: Callable[[int, int], None] | None = None,
			on_activity: ActivityCallback | None = None,
			on_result: Callable[[FileSearchResult], None] | None = None,
			cancel_check: Callable[[], bool] | None = None,
			allow_process_pool: bool = False,
		) -> tuple[list[FileSearchResult], list[SkippedFile]]:
			_ = (args, on_activity, cancel_check, allow_process_pool)
			effective = skipped_files if skipped_files is not None else []
			if on_progress is not None:
				on_progress(1, 10)
				on_progress(2, 10)
			return [], effective

	cancelled = {"n": 0}

	def cancel_check():
		cancelled["n"] += 1
		return cancelled["n"] > 1

	events: list[object] = []
	SearchSession(_CancellingSearch()).run_blocking(
		_args(tmp_path, "a"),
		on_event=events.append,
		cancel_check=cancel_check,
	)

	finished = [event for event in events if isinstance(event, SearchFinishedEvent)]
	assert len(finished) == 1
	assert finished[0].cancelled is True
	assert not any(isinstance(event, SearchErrorEvent) for event in events)
