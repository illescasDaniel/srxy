"""QObject bridge between QML and search session."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

from PySide6.QtCore import Property, QObject, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication

from srxy.adapters.inbound.cli.cli import apply_args_to_env, format_score_percent
from srxy.adapters.inbound.gui.capabilities import (
	Capabilities,
	capabilities_to_dict,
	probe_capabilities,
	unavailable_reason,
)
from srxy.adapters.inbound.gui.help_text import help_text as lookup_help_text
from srxy.adapters.inbound.gui.models import MatchesModel, ResultsModel
from srxy.adapters.inbound.gui.preview import format_preview_html, format_preview_message
from srxy.adapters.outbound.os.desktop import open_path
from srxy.adapters.outbound.worker.search_worker import (
	file_result_from_dict,
	iter_subprocess_search_events,
	skipped_file_from_dict,
)
from srxy.application.model_preflight import (
	PendingModelDownload,
	download_fn_for_kind,
	list_pending_model_downloads,
)
from srxy.application.search_filters import (
	SearchFilters,
	apply_search_filters_to_args,
	format_search_filters_summary,
	search_filters_from_args,
	validate_search_filters,
)
from srxy.application.search_options import (
	SearchOptions,
	apply_search_options_to_args,
	format_search_options_summary,
	search_options_from_args,
)
from srxy.application.search_session import (
	SearchActivityEvent,
	SearchErrorEvent,
	SearchFinishedEvent,
	SearchProgressEvent,
	SearchResultEvent,
	SearchSession,
)
from srxy.domain.file_query import (
	FileQ,
	FileQueryParseError,
	build_file_query_from_rows,
	file_q_to_dict,
	format_file_query,
	parse_file_query,
	sanitize_literal_term,
)
from srxy.domain.models import FileSearchResult
from srxy.domain.progress import format_activity_status


_PREVIEW_MAX_BYTES = 512_000


class _SearchWorker(QObject):
	event_ready = Signal(object)
	finished = Signal()

	def __init__(self, args: argparse.Namespace):
		super().__init__()
		self._args = args
		self._cancel = False

	@Slot()
	def run(self):
		session = SearchSession()
		if session.uses_subprocess(self._args):
			self._run_subprocess()
		else:
			session.run_blocking(self._args, on_event=self.event_ready.emit, cancel_check=lambda: self._cancel)
		self.finished.emit()

	def request_cancel(self):
		self._cancel = True

	def _run_subprocess(self):
		import asyncio

		async def _consume():
			async for event in iter_subprocess_search_events(
				self._args,
				cancel_check=lambda: self._cancel,
			):
				kind = event.get("type")
				if kind == "progress":
					current = event.get("current")
					total = event.get("total")
					if isinstance(current, int) and isinstance(total, int):
						self.event_ready.emit(SearchProgressEvent(current, total))
				elif kind == "activity":
					message = event.get("message")
					from srxy.domain.progress import ActivityUpdate

					if message is None:
						self.event_ready.emit(SearchActivityEvent(None))
					elif isinstance(message, str):
						current = event.get("current")
						total = event.get("total")
						self.event_ready.emit(
							SearchActivityEvent(
								ActivityUpdate(
									label=message,
									current=current if isinstance(current, int) else None,
									total=total if isinstance(total, int) else None,
								)
							)
						)
				elif kind == "result":
					data = event.get("result")
					if isinstance(data, dict):
						self.event_ready.emit(SearchResultEvent(file_result_from_dict(data)))
				elif kind == "error":
					self.event_ready.emit(SearchErrorEvent(str(event.get("message"))))
				elif kind == "finished":
					results_data = event.get("results")
					skipped_data = event.get("skipped_files")
					results = (
						[file_result_from_dict(item) for item in results_data] if isinstance(results_data, list) else []
					)
					skipped = (
						[skipped_file_from_dict(item) for item in skipped_data]
						if isinstance(skipped_data, list)
						else []
					)
					self.event_ready.emit(SearchFinishedEvent(results=results, skipped_files=skipped))

		asyncio.run(_consume())


class _DownloadWorker(QObject):
	progress = Signal(int, int, str)
	finished = Signal(bool, str)

	def __init__(self, kind: str):
		super().__init__()
		self._kind = kind
		self._cancel = False

	def request_cancel(self):
		self._cancel = True

	@Slot()
	def run(self):
		try:
			download_fn = download_fn_for_kind(self._kind)

			def on_progress(current: int, total: int, message: str):
				if self._cancel:
					raise RuntimeError("Download cancelled")
				self.progress.emit(current, total, message)

			download_fn(on_progress=on_progress)
			self.finished.emit(True, "")
		except Exception as error:  # noqa: BLE001 — surface any download failure to UI
			self.finished.emit(False, str(error))


class SearchController(QObject):
	statusChanged = Signal()
	progressChanged = Signal()
	staleChanged = Signal()
	searchingChanged = Signal()
	hasSearchedChanged = Signal()
	queryPreviewChanged = Signal()
	pathChanged = Signal()
	pathIssueChanged = Signal()
	canSearchChanged = Signal()
	previewChanged = Signal()
	optionsSummaryChanged = Signal()
	filtersSummaryChanged = Signal()
	selectedResultChanged = Signal()
	capabilitiesChanged = Signal()
	downloadConfirmChanged = Signal()
	downloadProgressUiChanged = Signal()
	errorOccurred = Signal(str)

	def __init__(self, args: argparse.Namespace, parent: QObject | None = None):
		super().__init__(parent)
		self._args = argparse.Namespace(**vars(args))
		self._query_mode = "simple"
		self._simple_query = (args.query or "").strip()
		self._advanced_query = self._simple_query
		self._term_rows_json = "[]"
		if self._simple_query:
			self._term_rows_json = json.dumps([{"term": self._simple_query, "join": None}])
		self._path = str(getattr(args, "path", ".") or ".")
		self._status = "Ready"
		self._progress = 0.0
		self._stale = True
		self._searching = False
		self._has_searched = False
		self._preview_text = ""
		self._preview_header = ""
		self._selected_row = -1
		self._last_snapshot: str | None = None
		self._options = search_options_from_args(self._args)
		self._filters = search_filters_from_args(self._args)
		self._capabilities = probe_capabilities()
		self._clamp_options_to_capabilities()
		apply_search_options_to_args(self._args, self._options)
		apply_search_filters_to_args(self._args, self._filters)
		self._results_model = ResultsModel(self)
		self._matches_model = MatchesModel(self)
		self._results_model.set_thresholds(
			threshold=self._args.threshold,
			semantic_image_threshold=self._args.semantic_image_threshold,
			transcribe_threshold=self._args.transcribe_threshold,
		)
		self._thread: QThread | None = None
		self._worker: _SearchWorker | None = None
		self._download_thread: QThread | None = None
		self._download_worker: _DownloadWorker | None = None
		self._download_queue: list[PendingModelDownload] = []
		self._pending_search_args: argparse.Namespace | None = None
		self._download_confirm_open = False
		self._download_confirm_message = ""
		self._download_progress_open = False
		self._download_progress = 0.0
		self._download_status = ""
		self._exit_code = 0
		self._refresh_stale()
		self.pathIssueChanged.emit()
		self.canSearchChanged.emit()

	def _clamp_options_to_capabilities(self):
		caps = self._capabilities
		self._options = replace(
			self._options,
			semantic=self._options.semantic and caps.semantic_enabled,
			semantic_image=self._options.semantic_image and caps.semantic_image_enabled,
			ocr=self._options.ocr and caps.ocr_enabled,
			transcribe=self._options.transcribe and caps.transcribe_enabled,
		)

	def _get_results_model(self) -> ResultsModel:
		return self._results_model

	resultsModel = Property(QObject, _get_results_model, constant=True)

	def _get_matches_model(self) -> MatchesModel:
		return self._matches_model

	matchesModel = Property(QObject, _get_matches_model, constant=True)

	def results_model(self) -> ResultsModel:
		return self._results_model

	def matches_model(self) -> MatchesModel:
		return self._matches_model

	def _get_status(self) -> str:
		return self._status

	status = Property(str, _get_status, notify=statusChanged)

	def _get_progress(self) -> float:
		return self._progress

	progress = Property(float, _get_progress, notify=progressChanged)

	def _get_stale(self) -> bool:
		return self._stale

	stale = Property(bool, _get_stale, notify=staleChanged)

	def _get_searching(self) -> bool:
		return self._searching

	searching = Property(bool, _get_searching, notify=searchingChanged)

	def _get_has_searched(self) -> bool:
		return self._has_searched

	hasSearched = Property(bool, _get_has_searched, notify=hasSearchedChanged)

	def _get_query_mode(self) -> str:
		return self._query_mode

	def _set_query_mode(self, value: str):
		if value not in {"simple", "multi", "advanced"}:
			return
		if self._query_mode != value:
			self._query_mode = value
			self.queryPreviewChanged.emit()
			self.canSearchChanged.emit()
			self._refresh_stale()

	queryMode = Property(str, _get_query_mode, _set_query_mode, notify=queryPreviewChanged)

	def _get_simple_query(self) -> str:
		return self._simple_query

	def _set_simple_query(self, value: str):
		if self._simple_query != value:
			self._simple_query = value
			self.queryPreviewChanged.emit()
			self.canSearchChanged.emit()
			self._refresh_stale()

	simpleQuery = Property(str, _get_simple_query, _set_simple_query, notify=queryPreviewChanged)

	def _get_advanced_query(self) -> str:
		return self._advanced_query

	def _set_advanced_query(self, value: str):
		if self._advanced_query != value:
			self._advanced_query = value
			self.queryPreviewChanged.emit()
			self.canSearchChanged.emit()
			self._refresh_stale()

	advancedQuery = Property(str, _get_advanced_query, _set_advanced_query, notify=queryPreviewChanged)

	def _get_term_rows_json(self) -> str:
		return self._term_rows_json

	def _set_term_rows_json(self, value: str):
		if self._term_rows_json != value:
			self._term_rows_json = value
			self.queryPreviewChanged.emit()
			self.canSearchChanged.emit()
			self._refresh_stale()

	termRowsJson = Property(str, _get_term_rows_json, _set_term_rows_json, notify=queryPreviewChanged)

	def _get_path(self) -> str:
		return self._path

	def _set_path(self, value: str):
		if self._path != value:
			self._path = value
			self.pathChanged.emit()
			self.pathIssueChanged.emit()
			self.canSearchChanged.emit()
			self._refresh_stale()

	path = Property(str, _get_path, _set_path, notify=pathChanged)

	def _compute_path_issue(self) -> str:
		raw = (self._path or "").strip()
		if not raw:
			return "Enter a search path"
		candidate = Path(raw).expanduser()
		if not candidate.exists():
			return "Path does not exist"
		if not candidate.is_dir():
			return "Not a directory"
		return ""

	def _get_path_issue(self) -> str:
		return self._compute_path_issue()

	pathIssue = Property(str, _get_path_issue, notify=pathIssueChanged)

	def _compute_query_issue(self) -> str:
		try:
			if self._query_mode == "advanced":
				raw = self._advanced_query.strip()
				if not raw:
					return ""
				parse_file_query(raw)
				return ""
			if self._query_mode == "multi":
				rows = self._parse_term_rows()
				if not any(term.strip() for term, _join in rows):
					return ""
				build_file_query_from_rows(rows)
				return ""
			return ""
		except (FileQueryParseError, ValueError) as error:
			return str(error)

	def _get_query_issue(self) -> str:
		return self._compute_query_issue()

	queryIssue = Property(str, _get_query_issue, notify=queryPreviewChanged)

	def _has_usable_query(self) -> bool:
		if self._compute_query_issue():
			return False
		if self._query_mode == "advanced":
			return bool(self._advanced_query.strip())
		if self._query_mode == "multi":
			return any(term.strip() for term, _join in self._parse_term_rows())
		return bool(sanitize_literal_term(self._simple_query.strip()))

	def _get_can_search(self) -> bool:
		if self._searching or self._download_confirm_open or self._download_progress_open:
			return False
		if self._compute_path_issue():
			return False
		return self._has_usable_query()

	canSearch = Property(bool, _get_can_search, notify=canSearchChanged)

	def _get_query_preview(self) -> str:
		if self._query_mode == "simple":
			return ""
		try:
			return self._formatted_query()
		except (FileQueryParseError, ValueError) as error:
			return f"invalid: {error}"

	queryPreview = Property(str, _get_query_preview, notify=queryPreviewChanged)

	def _get_preview_text(self) -> str:
		return self._preview_text

	previewText = Property(str, _get_preview_text, notify=previewChanged)

	def _get_preview_header(self) -> str:
		return self._preview_header

	previewHeader = Property(str, _get_preview_header, notify=previewChanged)

	def _get_options_summary(self) -> str:
		return format_search_options_summary(self._options)

	optionsSummary = Property(str, _get_options_summary, notify=optionsSummaryChanged)

	def _get_filters_summary(self) -> str:
		return format_search_filters_summary(self._filters)

	filtersSummary = Property(str, _get_filters_summary, notify=filtersSummaryChanged)

	def _get_capabilities_json(self) -> str:
		return json.dumps(capabilities_to_dict(self._capabilities))

	capabilitiesJson = Property(str, _get_capabilities_json, notify=capabilitiesChanged)

	def _get_download_confirm_open(self) -> bool:
		return self._download_confirm_open

	downloadConfirmOpen = Property(bool, _get_download_confirm_open, notify=downloadConfirmChanged)

	def _get_download_confirm_message(self) -> str:
		return self._download_confirm_message

	downloadConfirmMessage = Property(str, _get_download_confirm_message, notify=downloadConfirmChanged)

	def _get_download_progress_open(self) -> bool:
		return self._download_progress_open

	downloadProgressOpen = Property(bool, _get_download_progress_open, notify=downloadProgressUiChanged)

	def _get_download_progress(self) -> float:
		return self._download_progress

	downloadProgress = Property(float, _get_download_progress, notify=downloadProgressUiChanged)

	def _get_download_status(self) -> str:
		return self._download_status

	downloadStatus = Property(str, _get_download_status, notify=downloadProgressUiChanged)

	def _snapshot(self) -> str:
		return json.dumps(
			{
				"mode": self._query_mode,
				"simple": self._simple_query,
				"advanced": self._advanced_query,
				"rows": self._term_rows_json,
				"path": self._path,
				"options": asdict(self._options),
				"filters": asdict(self._filters),
			},
			sort_keys=True,
		)

	def _refresh_stale(self):
		stale = self._last_snapshot is None or self._snapshot() != self._last_snapshot
		if stale != self._stale:
			self._stale = stale
			self.staleChanged.emit()

	def _formatted_query(self) -> str:
		if self._query_mode == "advanced":
			raw = self._advanced_query.strip()
			if not raw:
				return ""
			return format_file_query(parse_file_query(raw))
		if self._query_mode == "multi":
			rows = self._parse_term_rows()
			if not any(term.strip() for term, _join in rows):
				return ""
			return format_file_query(build_file_query_from_rows(rows))
		text = sanitize_literal_term(self._simple_query.strip())
		if not text:
			return ""
		return format_file_query(FileQ.leaf(text))

	def _parse_term_rows(self) -> list[tuple[str, str | None]]:
		try:
			raw_rows = json.loads(self._term_rows_json)
		except json.JSONDecodeError:
			return []
		rows: list[tuple[str, str | None]] = []
		for index, item in enumerate(raw_rows):
			if not isinstance(item, dict):
				continue
			term = sanitize_literal_term(str(item.get("term", "")))
			join = item.get("join")
			if index == 0:
				join = None
			else:
				normalized = str(join or "or").strip().lower()
				if normalized not in {"and", "or"}:
					normalized = "or"
				join = normalized
			rows.append((term, join if isinstance(join, str) else None))
		return rows

	def _sync_args(self) -> argparse.Namespace:
		validate_search_filters(self._filters)
		args = argparse.Namespace(**vars(self._args))
		if self._query_mode == "advanced":
			expr = parse_file_query(self._advanced_query)
			args.query = format_file_query(expr)
			args.query_expr = file_q_to_dict(expr)
		elif self._query_mode == "multi":
			expr = build_file_query_from_rows(self._parse_term_rows())
			args.query = format_file_query(expr)
			args.query_expr = file_q_to_dict(expr)
		else:
			text = sanitize_literal_term(self._simple_query.strip())
			expr = FileQ.leaf(text)
			args.query = format_file_query(expr)
			args.query_expr = file_q_to_dict(expr)
		args.path = self._path or "."
		apply_search_filters_to_args(args, self._filters)
		apply_search_options_to_args(args, self._options)
		return args

	def _set_status(self, message: str):
		if self._status != message:
			self._status = message
			self.statusChanged.emit()

	def _set_searching(self, value: bool):
		if self._searching != value:
			self._searching = value
			self.searchingChanged.emit()
			self.canSearchChanged.emit()

	def _set_download_confirm(self, open_: bool, message: str = ""):
		self._download_confirm_open = open_
		self._download_confirm_message = message
		self.downloadConfirmChanged.emit()
		self.canSearchChanged.emit()

	def _set_download_progress_ui(self, open_: bool, progress: float = 0.0, status: str = ""):
		self._download_progress_open = open_
		self._download_progress = progress
		self._download_status = status
		self.downloadProgressUiChanged.emit()
		self.canSearchChanged.emit()

	@Slot()
	def refreshCapabilities(self):  # noqa: N802
		self._capabilities = probe_capabilities()
		self._clamp_options_to_capabilities()
		apply_search_options_to_args(self._args, self._options)
		self.capabilitiesChanged.emit()
		self.optionsSummaryChanged.emit()
		self._refresh_stale()

	@Slot(str, result=str)
	def helpText(self, key: str) -> str:  # noqa: N802
		reason = unavailable_reason(key, self._capabilities)
		base = lookup_help_text(key)
		if reason:
			return f"{base}\n\nCurrently unavailable:\n{reason}"
		return base

	@Slot(str, result=bool)
	def isFeatureEnabled(self, key: str) -> bool:  # noqa: N802
		caps = self._capabilities
		mapping = {
			"semantic": caps.semantic_enabled,
			"semantic_image": caps.semantic_image_enabled,
			"ocr": caps.ocr_enabled,
			"transcribe": caps.transcribe_enabled,
		}
		return mapping.get(key, True)

	@Slot()
	def startSearch(self):  # noqa: N802
		if self._searching or self._download_confirm_open or self._download_progress_open:
			return
		self.refreshCapabilities()
		try:
			args = self._sync_args()
		except (ValueError, FileQueryParseError) as error:
			self.errorOccurred.emit(str(error))
			return
		if not (args.query or "").strip():
			self.errorOccurred.emit("Enter a search query")
			return

		# Hard deps only — models are handled via download dialogs.
		error = _deps_only_preflight(args)
		if error is not None:
			self.errorOccurred.emit(error)
			self._exit_code = 2
			return

		apply_args_to_env(args)
		pending = list_pending_model_downloads(args)
		if pending:
			self._pending_search_args = args
			self._download_queue = list(pending)
			self._prompt_next_download()
			return

		self._begin_search(args)

	def _prompt_next_download(self):
		if not self._download_queue:
			args = self._pending_search_args
			self._pending_search_args = None
			if args is not None:
				self._begin_search(args)
			return
		item = self._download_queue[0]
		self._set_download_confirm(True, item.prompt)

	@Slot()
	def acceptDownloadConfirm(self):  # noqa: N802
		if not self._download_queue:
			self._set_download_confirm(False)
			return
		item = self._download_queue[0]
		self._set_download_confirm(False)
		self._set_download_progress_ui(True, 0.0, f"Downloading {item.label}…")
		self._download_thread = QThread(self)
		self._download_worker = _DownloadWorker(item.kind)
		self._download_worker.moveToThread(self._download_thread)
		self._download_thread.started.connect(self._download_worker.run)
		self._download_worker.progress.connect(self._on_download_progress)
		self._download_worker.finished.connect(self._on_download_finished)
		self._download_worker.finished.connect(self._download_thread.quit)
		self._download_thread.start()

	@Slot()
	def rejectDownloadConfirm(self):  # noqa: N802
		self._download_queue = []
		self._pending_search_args = None
		self._set_download_confirm(False)
		self._set_status("Download cancelled — search not started")
		self._exit_code = 2

	@Slot()
	def cancelDownload(self):  # noqa: N802
		if self._download_worker is not None:
			self._download_worker.request_cancel()
		self._set_download_status_message("Cancelling download…")

	def _set_download_status_message(self, message: str):
		self._download_status = message
		self.downloadProgressUiChanged.emit()

	def _on_download_progress(self, current: int, total: int, message: str):
		percent = 0.0 if total <= 0 else min(100.0, 100.0 * current / total)
		self._download_progress = percent
		self._download_status = message or self._download_status
		self.downloadProgressUiChanged.emit()

	def _on_download_finished(self, ok: bool, error_message: str):
		self._set_download_progress_ui(False)
		self._download_worker = None
		self._download_thread = None
		if not ok:
			self._download_queue = []
			self._pending_search_args = None
			self.errorOccurred.emit(error_message or "Download failed")
			self._exit_code = 2
			self._set_status("Download failed")
			return
		if self._download_queue:
			self._download_queue.pop(0)
		self._prompt_next_download()

	def _begin_search(self, args: argparse.Namespace):
		if not self._has_searched:
			self._has_searched = True
			self.hasSearchedChanged.emit()
		self._results_model.set_limit(args.limit)
		self._results_model.set_thresholds(
			threshold=args.threshold,
			semantic_image_threshold=args.semantic_image_threshold,
			transcribe_threshold=args.transcribe_threshold,
		)
		self._results_model.clear()
		self._matches_model.clear()
		self._preview_text = ""
		self._preview_header = ""
		self.previewChanged.emit()
		self._progress = 0.0
		self.progressChanged.emit()
		self._set_status("Starting search…")
		self._set_searching(True)
		self._args = args

		self._thread = QThread(self)
		self._worker = _SearchWorker(args)
		self._worker.moveToThread(self._thread)
		self._thread.started.connect(self._worker.run)
		self._worker.event_ready.connect(self._on_search_event)
		self._worker.finished.connect(self._on_worker_finished)
		self._worker.finished.connect(self._thread.quit)
		self._thread.start()

	@Slot()
	def cancelSearch(self):  # noqa: N802
		if self._worker is not None:
			self._worker.request_cancel()
		self._set_status("Cancelling…")

	def _on_search_event(self, event: object):
		if isinstance(event, SearchProgressEvent):
			total = max(event.total, 1)
			self._progress = min(100.0, 100.0 * event.current / total)
			self.progressChanged.emit()
			self._set_status(f"Scanning {event.current}/{event.total}")
		elif isinstance(event, SearchActivityEvent):
			if event.update is None:
				return
			self._set_status(format_activity_status(event.update) or self._status)
		elif isinstance(event, SearchResultEvent):
			self._results_model.insert_result(event.result)
			self._set_status(f"{self._results_model.rowCount()} matches…")
		elif isinstance(event, SearchErrorEvent):
			self.errorOccurred.emit(event.message)
			self._exit_code = 2
			self._set_status(event.message)
		elif isinstance(event, SearchFinishedEvent):
			self._results_model.replace_results(event.results)
			count = self._results_model.rowCount()
			self._exit_code = 0 if count else 1
			self._progress = 100.0
			self.progressChanged.emit()
			self._set_status(f"{count} file matched" if count == 1 else f"{count} files matched")
			if count:
				self.selectResult(0)

	def _on_worker_finished(self):
		self._set_searching(False)
		self._last_snapshot = self._snapshot()
		self._refresh_stale()
		self._worker = None
		self._thread = None

	@Slot(int)
	def selectResult(self, row: int):  # noqa: N802
		result = self._results_model.result_at(row)
		self._selected_row = row
		self._matches_model.load_from_result(result, query=self._args.query or "")
		if result is None:
			self._preview_header = ""
			self._preview_text = ""
		else:
			labels = self._results_model.data(
				self._results_model.index(row, 0),
				ResultsModel.LabelsRole,
			)
			self._preview_header = (
				f"{result.path.as_posix()}  ·  {format_score_percent(result.score)}  ·  matched: {labels}"
			)
			self._preview_text = _load_preview_text(result)
		self.previewChanged.emit()
		self.selectedResultChanged.emit()

	@Slot(int)
	def openResult(self, row: int):  # noqa: N802
		result = self._results_model.result_at(row)
		if result is None:
			return
		try:
			open_path(result.path)
		except OSError as error:
			self.errorOccurred.emit(str(error))

	@Slot(int)
	def copyResultPath(self, row: int):  # noqa: N802
		result = self._results_model.result_at(row)
		if result is None:
			return
		QGuiApplication.clipboard().setText(result.path.as_posix())

	@Slot(int)
	def copyAllMatches(self, row: int):  # noqa: N802
		self.selectResult(row)
		text = "\n".join(self._matches_model.all_plain_lines())
		if text:
			QGuiApplication.clipboard().setText(text)

	@Slot(int)
	def copyMatchLine(self, row: int):  # noqa: N802
		_location, plain = self._matches_model.row_plain(row)
		if plain:
			QGuiApplication.clipboard().setText(plain)

	@Slot(int)
	def copyMatchLocation(self, row: int):  # noqa: N802
		location, _plain = self._matches_model.row_plain(row)
		if location:
			QGuiApplication.clipboard().setText(location)

	@Slot(str)
	def applyOptionsJson(self, payload: str):  # noqa: N802
		data = json.loads(payload)
		self._options = SearchOptions(**data)
		self._clamp_options_to_capabilities()
		apply_search_options_to_args(self._args, self._options)
		self.optionsSummaryChanged.emit()
		self._refresh_stale()

	@Slot(str)
	def applyFiltersJson(self, payload: str):  # noqa: N802
		from srxy.application.size_limits import SizeLimits

		data = json.loads(payload)
		size = data.pop("size_limits")
		self._filters = SearchFilters(size_limits=SizeLimits(**size), **data)
		validate_search_filters(self._filters)
		apply_search_filters_to_args(self._args, self._filters)
		self.filtersSummaryChanged.emit()
		self._refresh_stale()

	@Slot(result=str)
	def optionsJson(self) -> str:  # noqa: N802
		return json.dumps(asdict(self._options))

	@Slot(result=str)
	def filtersJson(self) -> str:  # noqa: N802
		return json.dumps(asdict(self._filters))

	@Slot()
	def browsePath(self):  # noqa: N802
		QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self._path).expanduser().resolve())))

	def exit_code(self) -> int:
		return self._exit_code

	def sync_args_for_tests(self) -> argparse.Namespace:
		"""Test helper — mirrors startSearch arg sync without running a search."""
		return self._sync_args()

	def handle_search_event_for_tests(self, event: object):
		"""Test helper — deliver a search event on the UI thread."""
		self._on_search_event(event)

	def capabilities_for_tests(self) -> Capabilities:
		return self._capabilities

	def set_capabilities_for_tests(self, caps: Capabilities):
		self._capabilities = caps
		self._clamp_options_to_capabilities()
		self.capabilitiesChanged.emit()


def _deps_only_preflight(args: argparse.Namespace) -> str | None:
	from srxy.adapters.outbound.ocr.ocr_text import is_ocr_available, ocr_unavailable_message
	from srxy.adapters.outbound.semantic.semantic_image import (
		is_semantic_image_available,
		semantic_image_unavailable_message,
	)
	from srxy.adapters.outbound.transcribe.transcribe_text import (
		ffmpeg_available,
		ffmpeg_unavailable_message,
		transcribe_deps_installed,
		transcribe_unavailable_message,
	)
	from srxy.application.matching.semantic import (
		semantic_deps_unavailable_message,
		sentence_transformers_installed,
	)

	apply_args_to_env(args)
	if bool(args.ocr or args.semantic_all) and not is_ocr_available():
		return ocr_unavailable_message()
	if bool(args.transcribe or args.semantic_all) and not transcribe_deps_installed():
		return transcribe_unavailable_message()
	if bool(args.transcribe or args.semantic_all) and not ffmpeg_available():
		return ffmpeg_unavailable_message()
	if bool(args.semantic or args.semantic_all) and not sentence_transformers_installed():
		return semantic_deps_unavailable_message()
	if bool(args.semantic_image or args.semantic_all) and not is_semantic_image_available():
		return semantic_image_unavailable_message()
	return None


def _load_preview_text(result: FileSearchResult) -> str:
	path = result.path
	try:
		if not path.is_file():
			if result.lines:
				joined = "\n".join(line.text for line in result.lines[:50])
				return format_preview_html(path, joined)
			return format_preview_message("(No file preview available)")
		data = path.read_bytes()[:_PREVIEW_MAX_BYTES]
		if b"\x00" in data[:4096]:
			if result.lines:
				joined = "\n".join(line.text for line in result.lines[:50])
				return format_preview_html(path, joined)
			return format_preview_message("(Binary file — showing matches only)")
		text = data.decode("utf-8", errors="replace")
		return format_preview_html(path, text)
	except OSError:
		if result.lines:
			joined = "\n".join(line.text for line in result.lines[:50])
			return format_preview_html(path, joined)
		return format_preview_message("(Could not read file)")
