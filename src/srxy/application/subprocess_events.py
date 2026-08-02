"""Decode JSON lines from the search worker subprocess into SearchEvent objects."""

from __future__ import annotations

from typing import Any

from srxy.adapters.outbound.worker.search_worker import file_result_from_dict, skipped_file_from_dict
from srxy.application.search_session import (
	SearchActivityEvent,
	SearchErrorEvent,
	SearchEvent,
	SearchFinishedEvent,
	SearchProgressEvent,
	SearchResultEvent,
)
from srxy.domain.progress import ActivityUpdate


def subprocess_event_to_search_event(event: dict[str, Any]) -> SearchEvent | None:
	kind = event.get("type")
	if kind == "progress":
		current = event.get("current")
		total = event.get("total")
		if isinstance(current, int) and isinstance(total, int):
			return SearchProgressEvent(current, total)
		return None
	if kind == "activity":
		message = event.get("message")
		if message is None:
			return SearchActivityEvent(None)
		if isinstance(message, str):
			current = event.get("current")
			total = event.get("total")
			return SearchActivityEvent(
				ActivityUpdate(
					label=message,
					current=current if isinstance(current, int) else None,
					total=total if isinstance(total, int) else None,
				)
			)
		return None
	if kind == "result":
		data = event.get("result")
		if isinstance(data, dict):
			return SearchResultEvent(file_result_from_dict(data))
		return None
	if kind == "error":
		return SearchErrorEvent(str(event.get("message")))
	if kind == "finished":
		results_data = event.get("results")
		skipped_data = event.get("skipped_files")
		cancelled = bool(event.get("cancelled"))
		results = [file_result_from_dict(item) for item in results_data] if isinstance(results_data, list) else []
		skipped = [skipped_file_from_dict(item) for item in skipped_data] if isinstance(skipped_data, list) else []
		return SearchFinishedEvent(results=results, skipped_files=skipped, cancelled=cancelled)
	return None


__all__ = ["subprocess_event_to_search_event"]
