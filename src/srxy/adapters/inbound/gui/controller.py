"""QObject bridge between QML and search session."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from dataclasses import asdict, replace
from pathlib import Path

from PySide6.QtCore import Property, QObject, Qt, QThread, Signal, Slot

from srxy.adapters.inbound.cli.cli import apply_args_to_env
from srxy.adapters.inbound.gui.capabilities import (
	Capabilities,
	capabilities_to_dict,
	probe_capabilities,
	unavailable_reason,
)
from srxy.adapters.inbound.gui.help_text import help_text as lookup_help_text
from srxy.adapters.inbound.gui.models import MatchesModel, ResultsModel
from srxy.adapters.inbound.gui.preview import (
	PREVIEW_MAX_BYTES,
	format_preview_for_file,
	format_preview_message,
)
from srxy.adapters.outbound.worker.search_worker import iter_subprocess_search_events
from srxy.application.deps_preflight import deps_only_preflight
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
from srxy.application.search_formatting import format_score_percent
from srxy.application.search_options import (
	SearchOptions,
	apply_search_options_to_args,
	format_search_options_summary,
	has_search_source,
	search_options_from_args,
	search_source_required_message,
)
from srxy.application.search_session import (
	SearchActivityEvent,
	SearchErrorEvent,
	SearchFinishedEvent,
	SearchProgressEvent,
	SearchResultEvent,
)
from srxy.application.subprocess_events import subprocess_event_to_search_event
from srxy.bootstrap import build_app_services
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
from srxy.ports.inbound.search_runner import SearchRunnerPort
from srxy.ports.outbound.desktop import DesktopPort


def resolve_gui_search_path(raw: str | None) -> str:
	"""Default GUI search root is the user's home (CLI default ``.`` maps here)."""
	text = (raw or "").strip()
	if not text or text == ".":
		return str(Path.home())
	return text


class _SearchWorker(QObject):
	event_ready = Signal(object)
	finished = Signal()

	def __init__(
		self,
		args: argparse.Namespace,
		search_runner: SearchRunnerPort,
		*,
		on_subprocess: Callable[[object], None] | None = None,
	):
		super().__init__()
		self._args = args
		self._search_runner = search_runner
		self._on_subprocess = on_subprocess
		self._cancel = False

	@Slot()
	def run(self):
		runner = self._search_runner
		if runner.uses_subprocess(self._args):
			self._run_subprocess()
		else:
			runner.run_blocking(
				self._args,
				on_event=self.event_ready.emit,
				cancel_check=lambda: self._cancel,
				# Never fork from a QThread — ProcessPoolExecutor + Qt SIGSEGVs.
				allow_process_pool=False,
			)
		self.finished.emit()

	def request_cancel(self):
		self._cancel = True

	def _run_subprocess(self):
		import asyncio

		async def _consume():
			async for event in iter_subprocess_search_events(
				self._args,
				cancel_check=lambda: self._cancel,
				on_process=self._on_subprocess,
			):
				parsed = subprocess_event_to_search_event(event)
				if parsed is not None:
					self.event_ready.emit(parsed)

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


class _UpdateWorker(QObject):
	finished = Signal(object)
	failed = Signal(str)
	status = Signal(str)

	def __init__(self, action: str):
		super().__init__()
		self._action = action  # check | apply

	@Slot()
	def run(self):
		try:
			if self._action == "check":
				from srxy.application.updates import check_for_update

				self.finished.emit(check_for_update())
				return
			from srxy.application.updates import apply_update

			apply_update(status=lambda message: self.status.emit(message))
			self.finished.emit(True)
		except Exception as exc:  # noqa: BLE001
			self.failed.emit(str(exc))


class SearchController(QObject):
	statusChanged = Signal()
	progressChanged = Signal()
	staleChanged = Signal()
	searchingChanged = Signal()
	hasSearchedChanged = Signal()
	resultsEmptyHintChanged = Signal()
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
	updateUiChanged = Signal()
	aboutUiChanged = Signal()
	languageChanged = Signal()

	def __init__(
		self,
		args: argparse.Namespace,
		parent: QObject | None = None,
		*,
		search_runner: SearchRunnerPort | None = None,
		desktop: DesktopPort | None = None,
	):
		super().__init__(parent)
		self._args = argparse.Namespace(**vars(args))
		if search_runner is None:
			services = build_app_services()
			search_runner = services.search_runner
		if desktop is None:
			from srxy.adapters.inbound.gui.desktop import QtDesktopAdapter

			desktop = QtDesktopAdapter()
		self._search_runner = search_runner
		self._desktop = desktop
		self._query_mode = "simple"
		self._simple_query = (args.query or "").strip()
		self._advanced_query = self._simple_query
		self._term_rows_json = "[]"
		if self._simple_query:
			self._term_rows_json = json.dumps([{"term": self._simple_query, "join": None}])
		self._path = resolve_gui_search_path(getattr(args, "path", None))
		self._status = ""
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
		self._capabilities_probing = False
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
		self._search_subprocess: object | None = None
		self._default_result_limit_applied = False
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
		self._update_dialog_open = False
		self._update_dialog_mode = "prompt"  # prompt | info | progress
		self._update_message = ""
		self._update_can_apply = False
		self._update_busy = False
		self._update_silent = False
		self._about_open = False
		self._update_thread: QThread | None = None
		self._update_worker: _UpdateWorker | None = None
		from srxy.i18n import get_language, resolve_language

		lang = getattr(args, "language", None)
		if lang:
			from srxy.i18n import set_language

			set_language(str(lang))
		else:
			resolve_language()
		self._language = get_language()
		from srxy.i18n import tr as translate

		self._status = translate("status.ready")
		self._refresh_stale()
		self.pathIssueChanged.emit()
		self.canSearchChanged.emit()
		import os

		if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("SRXY_SKIP_UPDATE_CHECK"):
			return
		from PySide6.QtCore import QTimer

		QTimer.singleShot(800, lambda: self.checkForUpdates(silent=True))

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

	def _get_results_empty_hint(self) -> str:
		from srxy.i18n import tr

		if self._results_model.rowCount() > 0:
			return ""
		if not self._has_searched:
			return tr("results.empty.before")
		if self._searching:
			return tr("results.empty.searching")
		return tr("results.empty.none")

	resultsEmptyHint = Property(str, _get_results_empty_hint, notify=resultsEmptyHintChanged)

	def _notify_results_empty_hint(self):
		self.resultsEmptyHintChanged.emit()

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
		from srxy.i18n import tr

		raw = (self._path or "").strip()
		if not raw:
			return tr("error.enter_search_path")
		candidate = Path(raw).expanduser()
		if not candidate.exists():
			return tr("error.path_not_exist")
		if not candidate.is_dir():
			return tr("error.not_directory")
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

	def _get_selected_result(self) -> int:
		return self._selected_row

	def _set_selected_result(self, row: int):
		if row == self._selected_row:
			return
		self.selectResult(row)

	selectedResult = Property(int, _get_selected_result, _set_selected_result, notify=selectedResultChanged)

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
		args.path = resolve_gui_search_path(self._path)
		apply_search_filters_to_args(args, self._filters)
		apply_search_options_to_args(args, self._options)
		return args

	def _set_status(self, message: str):
		if self._status != message:
			self._status = message
			self.statusChanged.emit()

	def _set_status_tr(self, key: str, **kwargs: object):
		from srxy.i18n import tr as translate

		self._set_status(translate(key, **kwargs))

	def _set_searching(self, value: bool):
		if self._searching != value:
			self._searching = value
			self.searchingChanged.emit()
			self._notify_results_empty_hint()
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
		# Safe on the GUI thread: probe uses filesystem checks only (no torch/fork).
		probe_capabilities.cache_clear()
		self._capabilities = probe_capabilities()
		self._capabilities_probing = False
		self._clamp_options_to_capabilities()
		apply_search_options_to_args(self._args, self._options)
		self.capabilitiesChanged.emit()
		self.optionsSummaryChanged.emit()
		self._refresh_stale()

	@Slot(str, result=str)
	def helpText(self, key: str) -> str:  # noqa: N802
		return lookup_help_text(key)

	@Slot(str, result=str)
	def unavailableReason(self, key: str) -> str:  # noqa: N802
		if self._capabilities_probing and key in {"semantic", "semantic_image", "transcribe"}:
			from srxy.i18n import tr

			return tr("capabilities.detecting")
		return unavailable_reason(key, self._capabilities)

	@Slot(str, result=bool)
	def isFeatureEnabled(self, key: str) -> bool:  # noqa: N802
		if self._capabilities_probing and key in {"semantic", "semantic_image", "transcribe"}:
			return False
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
		try:
			args = self._sync_args()
		except (ValueError, FileQueryParseError) as error:
			self.errorOccurred.emit(str(error))
			return
		if not (args.query or "").strip():
			from srxy.i18n import tr

			self.errorOccurred.emit(tr("error.enter_search_query"))
			return

		# Hard deps only — models are handled via download dialogs.
		error = deps_only_preflight(args)
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
		self._set_download_progress_ui(True, 0.0, "")
		from srxy.i18n import tr as translate

		self._set_download_status_message(translate("status.downloading", label=item.label))
		self._start_download_worker(item.kind)

	@Slot()
	def rejectDownloadConfirm(self):  # noqa: N802
		self._download_queue = []
		self._pending_search_args = None
		self._set_download_confirm(False)
		self._set_status_tr("status.download_cancelled")
		self._exit_code = 2

	@Slot()
	def cancelDownload(self):  # noqa: N802
		if self._download_worker is not None:
			self._download_worker.request_cancel()
		from srxy.i18n import tr as translate

		self._set_download_status_message(translate("status.cancelling_download"))

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
		if not ok:
			self._download_queue = []
			self._pending_search_args = None
			self.errorOccurred.emit(error_message or "Download failed")
			self._exit_code = 2
			self._set_status_tr("status.download_failed")
			return
		if self._download_queue:
			self._download_queue.pop(0)
		self._prompt_next_download()

	def _begin_search(self, args: argparse.Namespace):
		if not self._has_searched:
			self._has_searched = True
			self.hasSearchedChanged.emit()
		from srxy.application.search_filters import GUI_DEFAULT_RESULT_LIMIT

		self._default_result_limit_applied = args.limit is None
		if args.limit is None:
			args.limit = GUI_DEFAULT_RESULT_LIMIT
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
		self._notify_results_empty_hint()
		self._set_status_tr("status.starting")
		self._set_searching(True)
		self._args = args
		self._start_search_worker(args)

	@staticmethod
	def _release_worker_on_main_thread(worker: QObject | None):
		"""Drop a finished QThread worker without ``deleteLater`` on a dead thread.

		``thread.finished → worker.deleteLater`` SIGBUS'd under Wayland + PySide6
		(Shiboken UAF while DeferredDelete ran on the finishing QThread). After the
		thread stops, ``moveToThread(gui)`` also fails from the GUI thread, so we
		only clear Python ownership and let Shiboken destroy the C++ object.
		"""
		if worker is None:
			return
		try:
			from shiboken6 import isValid

			if not isValid(worker):
				return
			worker.setParent(None)
		except RuntimeError:
			return

	def _start_search_worker(self, args: argparse.Namespace):
		# A prior search may still be tearing down even though UI is idle.
		self._dispose_search_worker(wait_ms=3000)
		thread = QThread(self)
		worker = _SearchWorker(
			args,
			self._search_runner,
			on_subprocess=self._register_search_subprocess,
		)
		worker.moveToThread(thread)
		thread.started.connect(worker.run)
		worker.event_ready.connect(self._on_search_event)
		worker.finished.connect(self._on_worker_finished)
		worker.finished.connect(thread.quit)
		# Parent owns the QThread — do not deleteLater it (Shiboken UAF risk).
		# Queue finished onto the GUI thread so worker teardown is not on the
		# dying QThread (deleteLater there SIGBUS'd under Wayland + PySide6).
		thread.finished.connect(self._on_search_thread_finished, Qt.ConnectionType.QueuedConnection)
		self._thread = thread
		self._worker = worker
		thread.start()

	def _start_download_worker(self, kind: str):
		self._dispose_download_worker(wait_ms=3000)
		thread = QThread(self)
		worker = _DownloadWorker(kind)
		worker.moveToThread(thread)
		thread.started.connect(worker.run)
		worker.progress.connect(self._on_download_progress)
		worker.finished.connect(self._on_download_finished)
		worker.finished.connect(thread.quit)
		thread.finished.connect(self._on_download_thread_finished, Qt.ConnectionType.QueuedConnection)
		self._download_thread = thread
		self._download_worker = worker
		thread.start()

	def _register_search_subprocess(self, process: object):
		self._search_subprocess = process

	def _kill_search_subprocess_sync(self):
		process = self._search_subprocess
		self._search_subprocess = None
		if process is None or getattr(process, "returncode", None) is not None:
			return
		try:
			process.kill()  # type: ignore[union-attr]
		except ProcessLookupError:
			return

	def _dispose_search_worker(self, *, wait_ms: int):
		thread = self._thread
		worker = self._worker
		self._thread = None
		self._worker = None
		self._kill_search_subprocess_sync()
		if worker is not None:
			worker.request_cancel()
		self._stop_qthread(thread, wait_ms=wait_ms)
		self._release_worker_on_main_thread(worker)

	def _dispose_download_worker(self, *, wait_ms: int):
		thread = self._download_thread
		worker = self._download_worker
		self._download_thread = None
		self._download_worker = None
		if worker is not None:
			worker.request_cancel()
		self._stop_qthread(thread, wait_ms=wait_ms)
		self._release_worker_on_main_thread(worker)

	def _dispose_update_worker(self, *, wait_ms: int):
		thread = self._update_thread
		worker = self._update_worker
		self._update_thread = None
		self._update_worker = None
		self._stop_qthread(thread, wait_ms=wait_ms)
		self._release_worker_on_main_thread(worker)

	@Slot()
	def _on_search_thread_finished(self):
		finished = self.sender()
		if self._thread is not None and finished is not self._thread:
			# Stale finished from a previous search thread — ignore.
			return
		self._search_subprocess = None
		worker = self._worker
		self._worker = None
		self._thread = None
		self._release_worker_on_main_thread(worker)
		self._set_searching(False)
		self._last_snapshot = self._snapshot()
		self._refresh_stale()

	@Slot()
	def _on_download_thread_finished(self):
		finished = self.sender()
		if self._download_thread is not None and finished is not self._download_thread:
			return
		worker = self._download_worker
		self._download_worker = None
		self._download_thread = None
		self._release_worker_on_main_thread(worker)

	@Slot()
	def cancelSearch(self):  # noqa: N802
		if self._worker is not None:
			self._worker.request_cancel()
		self._kill_search_subprocess_sync()
		self._set_status_tr("status.cancelling")

	def _on_search_event(self, event: object):
		if isinstance(event, SearchProgressEvent):
			total = max(event.total, 1)
			self._progress = min(100.0, 100.0 * event.current / total)
			self.progressChanged.emit()
			self._set_status_tr("status.scanning", current=event.current, total=event.total)
		elif isinstance(event, SearchActivityEvent):
			if event.update is None:
				return
			self._set_status(format_activity_status(event.update) or self._status)
		elif isinstance(event, SearchResultEvent):
			self._results_model.insert_result(event.result)
			self._notify_results_empty_hint()
			self._set_status_tr("status.matches_progress", count=self._results_model.rowCount())
		elif isinstance(event, SearchErrorEvent):
			self.errorOccurred.emit(event.message)
			self._exit_code = 2
			self._set_status(event.message)
		elif isinstance(event, SearchFinishedEvent):
			if event.results:
				self._results_model.replace_results(event.results)
			count = self._results_model.rowCount()
			self._notify_results_empty_hint()
			if event.cancelled:
				self._exit_code = 2
				self._progress = 100.0
				self.progressChanged.emit()
				self._set_status_tr("status.search_cancelled")
				return
			self._exit_code = 0 if count else 1
			self._progress = 100.0
			self.progressChanged.emit()
			if self._default_result_limit_applied and count >= self._args.limit:
				self._set_status_tr("status.default_result_limit", count=count, limit=self._args.limit)
			elif count == 1:
				self._set_status_tr("status.file_matched")
			else:
				self._set_status_tr("status.files_matched", count=count)
			if count:
				self.selectResult(0)

	def _on_worker_finished(self):
		# Keep searching=True until the QThread fully stops (_on_search_thread_finished)
		# so a new search cannot overwrite workers mid-teardown.
		self._kill_search_subprocess_sync()

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
			self._desktop.open_path(result.path)
		except OSError as error:
			self.errorOccurred.emit(str(error))

	@Slot(int)
	def copyResultPath(self, row: int):  # noqa: N802
		result = self._results_model.result_at(row)
		if result is None:
			return
		try:
			self._desktop.copy_text(result.path.as_posix())
		except OSError as error:
			self.errorOccurred.emit(str(error))

	@Slot(int)
	def copyAllMatches(self, row: int):  # noqa: N802
		self.selectResult(row)
		text = "\n".join(self._matches_model.all_plain_lines())
		if text:
			try:
				self._desktop.copy_text(text)
			except OSError as error:
				self.errorOccurred.emit(str(error))

	@Slot(int)
	def copyMatchLine(self, row: int):  # noqa: N802
		_location, plain = self._matches_model.row_plain(row)
		if plain:
			try:
				self._desktop.copy_text(plain)
			except OSError as error:
				self.errorOccurred.emit(str(error))

	@Slot(int)
	def copyMatchLocation(self, row: int):  # noqa: N802
		location, _plain = self._matches_model.row_plain(row)
		if location:
			try:
				self._desktop.copy_text(location)
			except OSError as error:
				self.errorOccurred.emit(str(error))

	@Slot(str, result=str)
	def applyOptionsJson(self, payload: str) -> str:  # noqa: N802
		data = json.loads(payload)
		options = SearchOptions(**data)
		if not has_search_source(options):
			return search_source_required_message()
		self._options = options
		self._clamp_options_to_capabilities()
		apply_search_options_to_args(self._args, self._options)
		self.optionsSummaryChanged.emit()
		self._refresh_stale()
		return ""

	@Slot(str, result=str)
	def applyFiltersJson(self, payload: str) -> str:  # noqa: N802
		from srxy.application.size_limits import SizeLimits

		try:
			data = json.loads(payload)
			size = data.pop("size_limits")
			draft = SearchFilters(size_limits=SizeLimits(**size), **data)
			validate_search_filters(draft)
		except (ValueError, json.JSONDecodeError, TypeError, KeyError) as error:
			return str(error)
		self._filters = draft
		apply_search_filters_to_args(self._args, self._filters)
		self.filtersSummaryChanged.emit()
		self._refresh_stale()
		return ""

	@Slot(result=str)
	def optionsJson(self) -> str:  # noqa: N802
		return json.dumps(asdict(self._options))

	@Slot(result=str)
	def filtersJson(self) -> str:  # noqa: N802
		return json.dumps(asdict(self._filters))

	@Slot(str, result=str)
	def i18nTr(self, key: str) -> str:  # noqa: N802
		from srxy.i18n import tr as translate

		return translate(key)

	@Property(str, notify=languageChanged)
	def language(self) -> str:
		return self._language

	@Slot(str)
	def setLanguage(self, language: str):  # noqa: N802
		from PySide6.QtCore import QCoreApplication, QLocale

		from srxy.application.settings import set_language_setting
		from srxy.i18n import get_language, set_language
		from srxy.i18n.qt import install_qt_translator

		set_language(language)
		set_language_setting(language)
		self._language = get_language()
		QLocale.setDefault(QLocale(self._language))
		app = QCoreApplication.instance()
		if app is not None:
			install_qt_translator(app, self._language)
		self.languageChanged.emit()
		self.updateUiChanged.emit()
		self.aboutUiChanged.emit()
		self.optionsSummaryChanged.emit()
		self.filtersSummaryChanged.emit()
		self.resultsEmptyHintChanged.emit()
		if not self._searching:
			self._set_status_tr("status.ready")

	@Property(str, constant=True)
	def appVersion(self) -> str:  # noqa: N802
		from srxy.application.updates import installed_version

		return installed_version()

	@Property(str, notify=languageChanged)
	def aboutPrivacyHtml(self) -> str:  # noqa: N802
		from srxy.adapters.inbound.installer.privacy import privacy_disclaimer_html

		return privacy_disclaimer_html(for_app=True)

	@Property(str, constant=True)
	def pypiUrl(self) -> str:  # noqa: N802
		from srxy.application.branding import PYPI_URL

		return PYPI_URL

	@Property(str, constant=True)
	def githubUrl(self) -> str:  # noqa: N802
		from srxy.application.branding import GITHUB_URL

		return GITHUB_URL

	@Property(str, constant=True)
	def websiteUrl(self) -> str:  # noqa: N802
		from srxy.application.branding import WEBSITE_URL

		return WEBSITE_URL

	@Property(bool, notify=aboutUiChanged)
	def aboutOpen(self) -> bool:  # noqa: N802
		return self._about_open

	@Slot()
	def openAbout(self):  # noqa: N802
		self._about_open = True
		self.aboutUiChanged.emit()

	@Slot()
	def closeAbout(self):  # noqa: N802
		self._about_open = False
		self.aboutUiChanged.emit()

	@Property(bool, notify=updateUiChanged)
	def updateDialogOpen(self) -> bool:  # noqa: N802
		return self._update_dialog_open

	@Property(str, notify=updateUiChanged)
	def updateDialogMode(self) -> str:  # noqa: N802
		return self._update_dialog_mode

	@Property(str, notify=updateUiChanged)
	def updateMessage(self) -> str:  # noqa: N802
		return self._update_message

	@Property(bool, notify=updateUiChanged)
	def updateCanApply(self) -> bool:  # noqa: N802
		return self._update_can_apply

	@Property(bool, notify=updateUiChanged)
	def updateBusy(self) -> bool:  # noqa: N802
		return self._update_busy

	@Slot()
	def checkForUpdates(self, silent: bool = False):  # noqa: N802
		if self._update_busy:
			return
		from srxy.i18n import tr as translate

		self._update_busy = True
		self._update_can_apply = False
		self._update_dialog_mode = "progress"
		self._update_message = translate("update.checking")
		self._update_dialog_open = not silent
		self._update_silent = silent
		self.updateUiChanged.emit()
		self._start_update_worker("check")

	@Slot()
	def applyUpdate(self):  # noqa: N802
		if self._update_busy:
			return
		from srxy.i18n import tr as translate

		self._update_busy = True
		self._update_dialog_mode = "progress"
		self._update_message = translate("update.updating")
		self._update_dialog_open = True
		self.updateUiChanged.emit()
		self._start_update_worker("apply")

	@Slot()
	def closeUpdateDialog(self):  # noqa: N802
		self._update_dialog_open = False
		self.updateUiChanged.emit()

	def _start_update_worker(self, action: str):
		self._dispose_update_worker(wait_ms=3000)
		thread = QThread(self)
		worker = _UpdateWorker(action)
		worker.moveToThread(thread)
		thread.started.connect(worker.run)
		if action == "check":
			worker.finished.connect(self._on_update_check_finished)
		else:
			worker.finished.connect(self._on_update_apply_finished)
		worker.failed.connect(self._on_update_failed)
		worker.status.connect(self._on_update_status)
		worker.finished.connect(thread.quit)
		worker.failed.connect(thread.quit)
		thread.finished.connect(self._on_update_thread_finished, Qt.ConnectionType.QueuedConnection)
		self._update_thread = thread
		self._update_worker = worker
		thread.start()

	@Slot()
	def _on_update_thread_finished(self):
		finished = self.sender()
		if self._update_thread is not None and finished is not self._update_thread:
			return
		worker = self._update_worker
		self._update_worker = None
		self._update_thread = None
		self._release_worker_on_main_thread(worker)

	@Slot(object)
	def _on_update_check_finished(self, info: object):
		from srxy.application.updates import UpdateInfo
		from srxy.i18n import tr as translate

		self._update_busy = False
		silent = self._update_silent
		if info is None:
			self._update_dialog_mode = "info"
			self._update_message = translate("update.offline")
			self._update_can_apply = False
			self._update_dialog_open = not silent
			self.updateUiChanged.emit()
			return
		if not isinstance(info, UpdateInfo):
			self._update_dialog_mode = "info"
			self._update_message = translate("update.offline")
			self._update_can_apply = False
			self._update_dialog_open = not silent
			self.updateUiChanged.emit()
			return
		if info.update_available:
			self._update_dialog_mode = "prompt"
			self._update_message = translate(
				"update.available",
				current=info.current_version,
				latest=info.latest_version,
			)
			self._update_can_apply = True
			self._update_dialog_open = True
		else:
			self._update_dialog_mode = "info"
			self._update_message = translate("update.up_to_date", version=info.current_version)
			self._update_can_apply = False
			self._update_dialog_open = not silent
		self.updateUiChanged.emit()

	@Slot(object)
	def _on_update_apply_finished(self, _ok: object):
		from srxy.i18n import tr as translate

		self._update_busy = False
		self._update_dialog_mode = "info"
		self._update_can_apply = False
		self._update_message = translate("update.complete_restart")
		self._update_dialog_open = True
		self.updateUiChanged.emit()

	@Slot(str)
	def _on_update_failed(self, message: str):
		from srxy.application.install_paths import srxy_home
		from srxy.i18n import tr as translate

		self._update_busy = False
		self._update_dialog_mode = "info"
		self._update_can_apply = False
		self._update_message = translate("update.failed")
		self._update_dialog_open = True
		self.updateUiChanged.emit()
		home = srxy_home()
		if home is not None:
			log_dir = home / "logs"
			log_dir.mkdir(parents=True, exist_ok=True)
			try:
				with (log_dir / "srxy.log").open("a", encoding="utf-8") as handle:
					handle.write(f"\n===== update failure =====\n{message}\n")
			except OSError:
				pass
		self.errorOccurred.emit(message)

	@Slot(str)
	def _on_update_status(self, message: str):
		self._update_message = message
		self.updateUiChanged.emit()

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
		self._capabilities_probing = False
		self._clamp_options_to_capabilities()
		self.capabilitiesChanged.emit()

	def search_thread_for_tests(self) -> QThread | None:
		return self._thread

	def set_search_subprocess_for_tests(self, process: object | None):
		self._search_subprocess = process

	def search_subprocess_for_tests(self) -> object | None:
		return self._search_subprocess

	def set_update_thread_for_tests(self, thread: QThread | None):
		self._update_thread = thread

	@staticmethod
	def _stop_qthread(thread: QThread | None, *, wait_ms: int):
		if thread is None:
			return
		try:
			from shiboken6 import isValid

			if not isValid(thread):
				return
			if thread.isRunning():
				thread.quit()
				thread.wait(wait_ms)
		except RuntimeError:
			# C++ QThread already destroyed (deleteLater race on quit).
			return

	def shutdown(self, *, thread_wait_ms: int = 3000):
		self._dispose_search_worker(wait_ms=thread_wait_ms)
		self._dispose_download_worker(wait_ms=thread_wait_ms)
		self._dispose_update_worker(wait_ms=thread_wait_ms)


def _load_preview_text(result: FileSearchResult) -> str:
	from srxy.i18n import tr

	path = result.path
	truncated_footer = tr("preview.truncated")
	try:
		if not path.is_file():
			if result.lines:
				joined = "\n".join(line.text for line in result.lines[:50])
				return format_preview_for_file(path, joined, truncated_footer=truncated_footer)
			return format_preview_message("(No file preview available)")
		raw = path.read_bytes()
		file_truncated = len(raw) > PREVIEW_MAX_BYTES
		data = raw[:PREVIEW_MAX_BYTES]
		if b"\x00" in data[:4096]:
			if result.lines:
				joined = "\n".join(line.text for line in result.lines[:50])
				return format_preview_for_file(
					path,
					joined,
					truncated=file_truncated,
					truncated_footer=truncated_footer,
				)
			return format_preview_message("(Binary file — showing matches only)")
		text = data.decode("utf-8", errors="replace")
		return format_preview_for_file(
			path,
			text,
			truncated=file_truncated,
			truncated_footer=truncated_footer,
		)
	except OSError:
		if result.lines:
			joined = "\n".join(line.text for line in result.lines[:50])
			return format_preview_for_file(path, joined, truncated_footer=truncated_footer)
		return format_preview_message("(Could not read file)")
