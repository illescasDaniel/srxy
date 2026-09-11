"""Shared search control primitives (cancel, UI pacing)."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from srxy.domain.models import FileSearchResult, SkippedFile


class SearchCancelled(Exception):
	"""Raised from progress/result callbacks to abort an in-flight search."""

	def __init__(
		self,
		*,
		results: list[FileSearchResult] | None = None,
		skipped_files: list[SkippedFile] | None = None,
	):
		self.results = results or []
		self.skipped_files = skipped_files or []


# Cap progressive UI events so the Qt main thread stays responsive on huge trees
# (e.g. names-only query "l" under "."). Final SearchFinishedEvent still carries
# the full (limit-trimmed) result set when not every hit was streamed progressively.
PROGRESS_EMIT_INTERVAL_S = 0.05
MAX_PROGRESSIVE_RESULT_EVENTS = 250


@dataclass
class ProgressiveEmitState:
	last_progress_at: float = field(default_factory=time.monotonic)
	progressive_results: int = 0


def raise_if_cancelled(cancel_check: Callable[[], bool] | None):
	if cancel_check is not None and cancel_check():
		raise SearchCancelled()


def emit_progress_if_due(
	current: int,
	total: int,
	state: ProgressiveEmitState,
	emit: Callable[[int, int], None],
	*,
	cancel_check: Callable[[], bool] | None = None,
):
	raise_if_cancelled(cancel_check)
	now = time.monotonic()
	# Listing catch-up (0/N) must always reach the UI so file counts appear while
	# slow OCR workers run — do not throttle this milestone.
	if current == 0 and total > 0:
		state.last_progress_at = now
		emit(current, total)
		return
	if current >= total or (now - state.last_progress_at) >= PROGRESS_EMIT_INTERVAL_S:
		state.last_progress_at = now
		emit(current, total)


def emit_result_if_under_cap(
	state: ProgressiveEmitState,
	emit: Callable[[], None],
	*,
	cancel_check: Callable[[], bool] | None = None,
) -> bool:
	raise_if_cancelled(cancel_check)
	if state.progressive_results >= MAX_PROGRESSIVE_RESULT_EVENTS:
		return False
	emit()
	state.progressive_results += 1
	return True


def finished_results_payload(
	results: list[FileSearchResult],
	state: ProgressiveEmitState,
) -> list[FileSearchResult] | None:
	"""Omit full results from a terminal event when every hit was already streamed."""
	if state.progressive_results >= len(results) and state.progressive_results > 0:
		return None
	return results


__all__ = [
	"MAX_PROGRESSIVE_RESULT_EVENTS",
	"PROGRESS_EMIT_INTERVAL_S",
	"ProgressiveEmitState",
	"SearchCancelled",
	"emit_progress_if_due",
	"emit_result_if_under_cap",
	"finished_results_payload",
	"raise_if_cancelled",
]
