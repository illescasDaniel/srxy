from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from srxy.application.search_session import (
	SearchFinishedEvent,
	SearchProgressEvent,
	SearchResultEvent,
	SearchSession,
)
from srxy.domain.models import FileSearchResult


pytestmark = pytest.mark.unit


def _args(path: Path, query: str) -> argparse.Namespace:
	from srxy.adapters.inbound.cli.cli import build_parser

	return build_parser().parse_args([query, str(path), "--cli"])


def test_given_fixture_tree_when_search_session_runs_then_emits_progress_and_results(tmp_path: Path):
	(tmp_path / "hello.txt").write_text("hello world\n", encoding="utf-8")
	events: list[object] = []
	session = SearchSession()

	session.run_blocking(_args(tmp_path, "hello"), on_event=events.append)

	assert any(isinstance(event, SearchProgressEvent) for event in events) or any(
		isinstance(event, SearchResultEvent) for event in events
	)
	finished = [event for event in events if isinstance(event, SearchFinishedEvent)]
	assert len(finished) == 1
	assert finished[0].results
	assert all(isinstance(item, FileSearchResult) for item in finished[0].results)
