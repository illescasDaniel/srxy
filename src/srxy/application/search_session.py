"""Progressive search session shared by TUI and GUI."""

from __future__ import annotations

import argparse
import os
import time
from collections.abc import Callable
from dataclasses import dataclass

from srxy.adapters.outbound.worker.search_worker import search_uses_subprocess
from srxy.application.search_control import (
	MAX_PROGRESSIVE_RESULT_EVENTS,
	PROGRESS_EMIT_INTERVAL_S,
	SearchCancelled,
)
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


@dataclass(frozen=True, slots=True)
class SearchFinishedEvent:
	results: list[FileSearchResult]
	skipped_files: list[SkippedFile]


@dataclass(frozen=True, slots=True)
class SearchErrorEvent:
	message: str


SearchEvent = SearchProgressEvent | SearchActivityEvent | SearchResultEvent | SearchFinishedEvent | SearchErrorEvent

EventCallback = Callable[[SearchEvent], None]


def _bootstrap_worker_env():
	os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
	os.environ.setdefault("OMP_NUM_THREADS", "1")
	os.environ.setdefault("TQDM_DISABLE", "1")
	os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
	os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
	os.environ.setdefault("JOBLIB_MULTIPROCESSING", "0")


class SearchSession:
	"""Run a search and deliver progressive events via callbacks.

	``run_blocking`` is safe to call from a worker thread. Heavy modes that need
	process isolation should use ``search_uses_subprocess`` + the worker adapter
	instead of this method.

	Progress and early result events are paced so GUI/TUI frontends stay
	responsive on huge trees; ``SearchFinishedEvent`` always carries the full
	(limit-trimmed) result list.
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
	):
		_bootstrap_worker_env()
		skipped_files: list[SkippedFile] = []
		last_progress_at = 0.0
		progressive_results = 0

		def _raise_if_cancelled():
			if cancel_check is not None and cancel_check():
				raise SearchCancelled()

		def on_progress(current: int, total: int):
			nonlocal last_progress_at
			_raise_if_cancelled()
			now = time.monotonic()
			if current >= total or (now - last_progress_at) >= PROGRESS_EMIT_INTERVAL_S:
				last_progress_at = now
				on_event(SearchProgressEvent(current, total))

		def on_activity(update: ActivityUpdate | None):
			# Do not raise here — listing/encoding may not be interruptible yet.
			if cancel_check is not None and cancel_check():
				return
			on_event(SearchActivityEvent(update))

		def on_result(result: FileSearchResult):
			nonlocal progressive_results
			_raise_if_cancelled()
			if progressive_results < MAX_PROGRESSIVE_RESULT_EVENTS:
				on_event(SearchResultEvent(result))
				progressive_results += 1

		try:
			results, skipped_files = self._file_search.execute(
				args,
				skipped_files=skipped_files,
				on_progress=on_progress,
				on_activity=on_activity,
				on_result=on_result,
			)
		except SearchCancelled:
			# Ports that do not swallow cancel still surface it here.
			on_event(SearchFinishedEvent(results=[], skipped_files=skipped_files))
			return
		except Exception as error:
			on_event(SearchErrorEvent(str(error)))
			return

		on_event(SearchFinishedEvent(results=results, skipped_files=skipped_files))
