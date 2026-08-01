from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from srxy.application.search_runner import FileSearchService
from srxy.application.search_runner_adapter import AdaptiveSearchRunner
from srxy.application.search_session import SearchFinishedEvent, SearchSession
from srxy.bootstrap import build_app_services, build_worker_services
from srxy.domain.models import FileSearchResult


pytestmark = pytest.mark.unit


def test_given_app_services_when_built_then_includes_adaptive_runner():
	services = build_app_services()
	assert isinstance(services.search_runner, AdaptiveSearchRunner)
	assert isinstance(services.file_search, FileSearchService)


def test_given_worker_services_when_built_then_exposes_file_search_port():
	services = build_worker_services()
	assert isinstance(services.file_search, FileSearchService)


def test_given_adaptive_runner_when_run_blocking_then_delegates_to_session(tmp_path: Path):
	result = FileSearchResult(path=tmp_path / "a.txt", score=0.5, breakdown={}, lines=[])
	fake = MagicMock()
	fake.execute.return_value = ([result], [])
	runner = AdaptiveSearchRunner(SearchSession(fake))
	events: list[object] = []
	args = argparse.Namespace(query="a", path=str(tmp_path))

	runner.run_blocking(args, on_event=events.append)

	fake.execute.assert_called_once()
	assert any(isinstance(event, SearchFinishedEvent) for event in events)
