from __future__ import annotations

from pathlib import Path

import pytest

from srxy.application.search_control import (
	MAX_PROGRESSIVE_RESULT_EVENTS,
	ProgressiveEmitState,
	SearchCancelled,
	emit_progress_if_due,
	emit_result_if_under_cap,
	finished_results_payload,
	raise_if_cancelled,
)
from srxy.domain.models import FileSearchResult


pytestmark = pytest.mark.unit


def test_given_cancel_check_true_when_raise_if_cancelled_then_raises():
	with pytest.raises(SearchCancelled):
		raise_if_cancelled(lambda: True)


def test_given_state_under_cap_when_emit_result_if_under_cap_then_emits_once():
	state = ProgressiveEmitState()
	emitted: list[int] = []

	assert emit_result_if_under_cap(state, lambda: emitted.append(1)) is True

	assert emitted == [1]
	assert state.progressive_results == 1


def test_given_many_results_when_finished_results_payload_then_omits_when_fully_streamed(
	tmp_path: Path,
):
	results = [FileSearchResult(path=tmp_path / f"f{i}.txt", score=1.0, breakdown={}, lines=[]) for i in range(3)]
	state = ProgressiveEmitState(progressive_results=3)

	assert finished_results_payload(results, state) is None


def test_given_partial_stream_when_finished_results_payload_then_includes_authoritative_list(
	tmp_path: Path,
):
	results = [
		FileSearchResult(path=tmp_path / f"f{i}.txt", score=1.0, breakdown={}, lines=[])
		for i in range(MAX_PROGRESSIVE_RESULT_EVENTS + 5)
	]
	state = ProgressiveEmitState(progressive_results=MAX_PROGRESSIVE_RESULT_EVENTS)

	payload = finished_results_payload(results, state)

	assert payload == results


def test_given_progress_burst_when_emit_progress_if_due_then_paces_emits():
	state = ProgressiveEmitState(last_progress_at=0.0)
	emitted: list[tuple[int, int]] = []

	emit_progress_if_due(1, 10, state, lambda c, t: emitted.append((c, t)))
	emit_progress_if_due(2, 10, state, lambda c, t: emitted.append((c, t)))

	assert len(emitted) == 1
