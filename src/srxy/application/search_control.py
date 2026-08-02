"""Shared search control primitives (cancel, UI pacing)."""

from __future__ import annotations


class SearchCancelled(Exception):
	"""Raised from progress/result callbacks to abort an in-flight search."""


# Cap progressive UI events so the Qt main thread stays responsive on huge trees
# (e.g. names-only query "l" under "."). Final SearchFinishedEvent still carries
# the full (limit-trimmed) result set.
PROGRESS_EMIT_INTERVAL_S = 0.05
MAX_PROGRESSIVE_RESULT_EVENTS = 250


__all__ = [
	"MAX_PROGRESSIVE_RESULT_EVENTS",
	"PROGRESS_EMIT_INTERVAL_S",
	"SearchCancelled",
]
