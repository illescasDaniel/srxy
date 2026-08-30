"""Progressive search session shared by TUI and GUI."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass

from srxy.adapters.outbound.worker.search_worker import search_uses_subprocess
from srxy.application.search_control import (
	ProgressiveEmitState,
	SearchCancelled,
	emit_progress_if_due,
	emit_result_if_under_cap,
	finished_results_payload,
)
from srxy.application.search_formatting import match_labels
from srxy.application.worker_env import bootstrap_worker_env
from srxy.domain.models import FileSearchResult, SkippedFile
from srxy.domain.progress import ActivityUpdate
from srxy.ports.inbound.file_search import FileSearchPort


@dataclass(frozen=True, slots=True)
class SearchProgressEvent:
	current: int
	total: int


@dataclass(frozen=True, slots=True)
class SearchActivityEvent:
	update: ActivityUpdate | None


@dataclass(frozen=True, slots=True)
class SearchResultEvent:
	result: FileSearchResult
	labels: str = ""


@dataclass(frozen=True, slots=True)
class SearchFinishedEvent:
	results: list[FileSearchResult]
	skipped_files: list[SkippedFile]
	cancelled: bool = False


@dataclass(frozen=True, slots=True)
class SearchErrorEvent:
	message: str


SearchEvent = SearchProgressEvent | SearchActivityEvent | SearchResultEvent | SearchFinishedEvent | SearchErrorEvent

EventCallback = Callable[[SearchEvent], None]


class SearchSession:
	"""Run a search and deliver progressive events via callbacks.

	``run_blocking`` is safe to call from a worker thread. Heavy modes that need
	process isolation should use ``search_uses_subprocess`` + the worker adapter
	instead of this method.

	Progress and early result events are paced so GUI/TUI frontends stay
	responsive on huge trees; ``SearchFinishedEvent`` carries the full
	(limit-trimmed) result list unless every hit was already streamed progressively.
	"""

	def __init__(self, file_search: FileSearchPort):
		self._file_search = file_search

	def uses_subprocess(self, args: argparse.Namespace) -> bool:
		return search_uses_subprocess(args)

	def run_blocking(
		self,
		args: argparse.Namespace,
		*,
		on_event: EventCallback,
		cancel_check: Callable[[], bool] | None = None,
		allow_process_pool: bool = False,
	):
		bootstrap_worker_env()
		skipped_files: list[SkippedFile] = []
		emit_state = ProgressiveEmitState()

		def on_progress(current: int, total: int):
			emit_progress_if_due(
				current,
				total,
				emit_state,
				lambda c, t: on_event(SearchProgressEvent(c, t)),
				cancel_check=cancel_check,
			)

		def on_activity(update: ActivityUpdate | None):
			# Do not raise here — listing/encoding may not be interruptible yet.
			if cancel_check is not None and cancel_check():
				return
			on_event(SearchActivityEvent(update))

		def on_result(result: FileSearchResult):
			labels = match_labels(
				result,
				threshold=args.threshold,
				semantic_image_threshold=args.semantic_image_threshold,
				transcribe_threshold=args.transcribe_threshold,
			)
			emit_result_if_under_cap(
				emit_state,
				lambda: on_event(SearchResultEvent(result, labels=labels)),
				cancel_check=cancel_check,
			)

		try:
			results, skipped_files = self._file_search.execute(
				args,
				skipped_files=skipped_files,
				on_progress=on_progress,
				on_activity=on_activity,
				on_result=on_result,
				cancel_check=cancel_check,
				allow_process_pool=allow_process_pool,
			)
		except SearchCancelled as error:
			results = error.results
			if error.skipped_files:
				skipped_files = error.skipped_files
			finished_results = finished_results_payload(results, emit_state)
			on_event(
				SearchFinishedEvent(
					results=[] if finished_results is None else finished_results,
					skipped_files=skipped_files,
					cancelled=True,
				)
			)
			return
		except Exception as error:
			on_event(SearchErrorEvent(str(error)))
			return

		finished_results = finished_results_payload(results, emit_state)
		on_event(
			SearchFinishedEvent(
				results=[] if finished_results is None else finished_results,
				skipped_files=skipped_files,
			)
		)
