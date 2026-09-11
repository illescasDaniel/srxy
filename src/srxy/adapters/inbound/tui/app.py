from __future__ import annotations

import argparse
import asyncio
import multiprocessing
import queue
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import (
	Button,
	DataTable,
	Footer,
	Header,
	Input,
	Label,
	ProgressBar,
	Static,
)

from srxy.adapters.inbound.tui.desktop import TextualDesktopAdapter
from srxy.adapters.inbound.tui.labels import format_tui_match_labels
from srxy.adapters.inbound.tui.messages import (
	ActivityChanged,
	ProgressUpdated,
	ResultFound,
	SearchError,
	SearchFinished,
)
from srxy.adapters.inbound.tui.modals import ErrorModal, HelpModal, SearchFiltersModal, SearchOptionsModal
from srxy.adapters.inbound.tui.preflight import run_tui_preflight
from srxy.adapters.inbound.tui.query_builder import QueryBuilder
from srxy.adapters.inbound.tui.theme import detect_app_theme
from srxy.application.labels import (
	results_empty_before_search,
	results_empty_no_matches,
	results_empty_searching,
)
from srxy.application.search_filters import (
	SearchFilters,
	apply_search_filters_to_args,
	format_search_filters_summary,
	search_filters_from_args,
)
from srxy.application.search_formatting import (
	format_grouped_summary,
	format_score_percent,
	iter_grouped_line_displays,
)
from srxy.application.search_messages import format_no_matches_message
from srxy.application.search_options import (
	SearchOptions,
	apply_search_options_to_args,
	format_search_options_summary,
	search_options_from_args,
)
from srxy.application.search_runner_adapter import AdaptiveSearchRunner
from srxy.application.skipped_file_warnings import format_skipped_file_warnings
from srxy.application.subprocess_events import subprocess_event_to_search_event
from srxy.bootstrap import build_app_services
from srxy.domain.file_query import file_q_to_dict
from srxy.domain.models import FileSearchResult
from srxy.domain.progress import (
	ACTIVITY_SPINNER_FRAMES,
	ActivityUpdate,
	format_activity_status,
	is_generic_searching_activity,
)
from srxy.i18n import tr
from srxy.ports.inbound.search_runner import SearchRunnerPort
from srxy.ports.outbound.desktop import DesktopPort


_SEARCH_SENTINEL = object()
_SearchEvent = ProgressUpdated | ActivityChanged | ResultFound | SearchError | SearchFinished


@dataclass(frozen=True, slots=True)
class _SearchSnapshot:
	query: str
	path: str
	search_options: SearchOptions
	search_filters: SearchFilters


@dataclass(frozen=True, slots=True)
class _PreviewRow:
	location: str
	plain_text: str
	score: float


_PREVIEW_MATCH_WIDTH = 7
_PREVIEW_LOCATION_WIDTH = 32
_PREVIEW_LOCATION_DISPLAY_MAX = 32


def _preview_location_cell(location: str, *, max_len: int = _PREVIEW_LOCATION_DISPLAY_MAX) -> str:
	if len(location) <= max_len:
		return location
	return location[: max_len - 1] + "…"


class SrxyApp(App[int]):
	TITLE = "Srxy"
	BINDINGS = [
		Binding("question_mark", "show_help", "Help", show=True, priority=True),
		Binding("o", "open_file", "Open", show=True, priority=True),
		Binding("y", "copy_path", "Copy path", show=True, priority=True),
		Binding("m", "copy_match", "Copy match", show=True, priority=True),
		Binding("M", "copy_all_matches", "Copy all", show=True, priority=True),
		Binding("q", "request_quit", "Quit", show=True, priority=True),
		Binding("ctrl+c", "request_quit", "Quit", show=True, priority=True),
		Binding("slash", "focus_query", "Query", show=False),
		Binding("ctrl+s", "start_search", "Search", show=False),
	]

	CSS = """
	Screen {
		layout: vertical;
	}

	Footer {
		dock: bottom;
		height: 1;
	}

	#search-bar {
		height: auto;
		padding: 0 1;
	}

	#search-bar Label {
		width: auto;
		min-width: 8;
		height: 1;
		padding: 0 1 0 0;
		content-align: right middle;
		color: $text-muted;
	}

	#search-bar Input {
		width: 1fr;
		height: 1;
		margin-right: 1;
		border: none;
		padding: 0 1;
		color: $foreground;
		background: $surface;
		content-align: center middle;
	}

	#search-bar QueryBuilder {
		width: 1fr;
		margin-right: 1;
	}

	#search-bar #path-label,
	#search-bar #path-input,
	#search-bar #search-button {
		margin-top: 1;
	}

	#search-bar Button {
		height: 1;
		min-width: 10;
		border: none;
		padding: 0 1;
		content-align: center middle;
	}

	#filters-bar {
		height: auto;
		padding: 0 1 1 1;
	}

	#search-filters-button {
		height: 1;
		min-width: 12;
		border: none;
		background: $surface;
		color: $foreground;
		padding: 0 1;
		content-align: center middle;
		margin-right: 1;
	}

	#filters-summary {
		width: 1fr;
		height: 1;
		color: $text-muted;
		content-align: left middle;
	}

	#options-bar {
		height: auto;
		padding: 0 1 1 1;
	}

	#search-options-button {
		height: 1;
		min-width: 12;
		border: none;
		background: $surface;
		color: $foreground;
		padding: 0 1;
		content-align: center middle;
		margin-right: 1;
	}

	#options-summary {
		width: 1fr;
		height: 1;
		color: $text-muted;
		content-align: left middle;
	}

	#main-pane {
		height: 1fr;
		min-height: 6;
	}

	#results-panel {
		width: 2fr;
		border: solid $accent;
	}

	#preview-panel {
		width: 3fr;
		border: solid $accent;
	}

	#results-table {
		height: 1fr;
	}

	#results-panel.-empty #results-table {
		height: auto;
	}

	#results-empty {
		display: none;
		height: 1fr;
		content-align: center middle;
		color: $text-muted;
	}

	#results-panel.-empty #results-empty {
		display: block;
	}

	#preview-header {
		height: auto;
		padding: 0 1;
	}

	#preview-matches {
		height: 1fr;
	}

	#status-bar {
		height: auto;
		padding: 0 1;
	}

	#scan-progress {
		width: 1fr;
		margin-right: 1;
	}

	#status-message {
		width: 1fr;
	}

	#warnings-log {
		height: auto;
		max-height: 6;
		padding: 0 1;
		color: $warning;
	}
	"""

	def __init__(
		self,
		args: argparse.Namespace,
		*,
		auto_start: bool = False,
		search_runner: SearchRunnerPort | None = None,
		desktop: DesktopPort | None = None,
	):
		super().__init__()
		self.theme = detect_app_theme()
		self._args = args
		self._auto_start = auto_start
		if search_runner is None:
			services = build_app_services()
			search_runner = services.search_runner
		self._search_runner = search_runner
		if desktop is None:
			desktop = TextualDesktopAdapter(copy_fallback=lambda text: App.copy_to_clipboard(self, text))
		self._desktop = desktop
		self._results: list[FileSearchResult] = []
		self._result_index: dict[str, FileSearchResult] = {}
		self._searching = False
		self._cancel_search = False
		self._exit_code = 0
		self._warnings_text = ""
		self._last_search_snapshot: _SearchSnapshot | None = None
		self._active_file_limit: int | None = None
		self._preview_rows: list[_PreviewRow] = []
		self._activity: ActivityUpdate | None = None
		self._activity_spinner_index = 0
		self._activity_spinner_timer = None
		self._search_subprocess: asyncio.subprocess.Process | None = None
		self.search_options = search_options_from_args(args)
		self.search_filters = search_filters_from_args(args)
		apply_search_options_to_args(self._args, self.search_options)
		apply_search_filters_to_args(self._args, self.search_filters)

	@property
	def exit_code(self) -> int:
		return self._exit_code

	def compose(self) -> ComposeResult:
		yield Header()
		with Horizontal(id="search-bar"):
			yield QueryBuilder(id="query-builder", initial_query=self._args.query or "")
			yield Label(tr("tui.path"), id="path-label")
			yield Input(id="path-input", value=str(self._args.path), placeholder="")
			yield Button(tr("tui.search"), variant="primary", id="search-button")
		with Horizontal(id="options-bar"):
			yield Button(tr("tui.search_options"), id="search-options-button")
			yield Static(format_search_options_summary(self.search_options), id="options-summary")
		with Horizontal(id="filters-bar"):
			yield Button(tr("tui.filters"), id="search-filters-button")
			yield Static(format_search_filters_summary(self.search_filters), id="filters-summary")
		with Horizontal(id="main-pane"):
			with Vertical(id="results-panel"):
				yield DataTable(id="results-table", cursor_type="row", zebra_stripes=True)
				yield Static("", id="results-empty")
			with Vertical(id="preview-panel"):
				yield Static("", id="preview-header")
				yield DataTable(id="preview-matches", cursor_type="row", zebra_stripes=True)
		yield Static("", id="warnings-log")
		with Horizontal(id="status-bar"):
			yield ProgressBar(total=100, show_eta=False, id="scan-progress")
			# Plain text: Rich markup would swallow pip extras like [semantic].
			yield Label(tr("status.ready"), id="status-message", markup=False)
		yield Footer(show_command_palette=False)

	def on_mount(self):
		table = self.query_one("#results-table", DataTable)
		table.add_columns(tr("tui.col.match"), tr("tui.col.path"), tr("tui.col.matched"))
		self._setup_preview_columns(self.query_one("#preview-matches", DataTable))
		self._refresh_options_summary()
		self._refresh_filters_summary()
		self._update_search_button_state()
		self._sync_results_empty_hint()
		if self._auto_start and (self._args.query or "").strip():
			self.call_after_refresh(self.action_start_search)

	def _sync_results_empty_hint(self):
		try:
			panel = self.query_one("#results-panel", Vertical)
			empty = self.query_one("#results-empty", Static)
		except NoMatches:
			return
		if self._results:
			panel.remove_class("-empty")
			empty.update("")
			return
		if self._searching:
			message = results_empty_searching()
		elif self._last_search_snapshot is not None:
			message = results_empty_no_matches()
		else:
			message = results_empty_before_search()
		empty.update(message)
		panel.add_class("-empty")

	def _setup_preview_columns(self, table: DataTable[Any]):
		table.add_column(tr("tui.col.match"), width=_PREVIEW_MATCH_WIDTH)
		table.add_column(tr("tui.col.location"), width=_PREVIEW_LOCATION_WIDTH)
		table.add_column(tr("tui.col.text"))

	def _reset_preview_table(self, table: DataTable[Any]):
		table.clear(columns=True)
		self._setup_preview_columns(table)

	def _query_builder(self) -> QueryBuilder:
		return self.query_one("#query-builder", QueryBuilder)

	def _refresh_options_summary(self):
		self.query_one("#options-summary", Static).update(format_search_options_summary(self.search_options))

	def _refresh_filters_summary(self):
		self.query_one("#filters-summary", Static).update(format_search_filters_summary(self.search_filters))

	def _current_snapshot(self) -> _SearchSnapshot:
		builder = self._query_builder()
		return _SearchSnapshot(
			query=builder.to_snapshot_query_string(),
			path=self.query_one("#path-input", Input).value or ".",
			search_options=self.search_options,
			search_filters=self.search_filters,
		)

	def _update_search_button_state(self):
		try:
			button = self.query_one("#search-button", Button)
		except NoMatches:
			# QueryBuilder.Changed can arrive during mount/teardown (seen on Windows CI).
			return
		snapshot = self._current_snapshot()
		is_stale = self._last_search_snapshot is None or snapshot != self._last_search_snapshot
		button.set_class(is_stale, "-stale")
		button.variant = "warning" if is_stale else "primary"

	def _save_search_snapshot(self):
		self._last_search_snapshot = self._current_snapshot()
		self._update_search_button_state()

	def _sync_args_from_ui(self) -> argparse.Namespace:
		from srxy.application.search_filters import parse_search_filter_limits, validate_search_filters

		snapshot = self._current_snapshot()
		try:
			validate_search_filters(snapshot.search_filters)
		except ValueError as error:
			raise ValueError(str(error)) from error
		limit, max_matches = parse_search_filter_limits(snapshot.search_filters)
		args = argparse.Namespace(**vars(self._args))
		builder = self._query_builder()
		args.query = builder.to_query_string()
		args.query_expr = file_q_to_dict(builder.to_file_query())
		args.path = snapshot.path
		args.limit = limit
		args.max_matches = max_matches
		apply_search_filters_to_args(args, snapshot.search_filters)
		apply_search_options_to_args(args, snapshot.search_options)
		return args

	def _reset_results(self):
		self._results = []
		self._result_index = {}
		table = self.query_one("#results-table", DataTable)
		table.clear(columns=False)
		try:
			self.query_one("#preview-header", Static).update("")
			self._reset_preview_table(self.query_one("#preview-matches", DataTable))
		except NoMatches:
			pass
		self.query_one("#warnings-log", Static).update("")
		self._warnings_text = ""
		self._preview_rows = []
		self._sync_results_empty_hint()

	def _set_status(self, message: str):
		self.query_one("#status-message", Label).update(message)

	def _match_labels(self, result: FileSearchResult) -> str:
		return format_tui_match_labels(
			result,
			threshold=self._args.threshold,
			semantic_image_threshold=self._args.semantic_image_threshold,
			transcribe_threshold=self._args.transcribe_threshold,
		)

	def _update_preview(self, result: FileSearchResult | None):
		try:
			header = self.query_one("#preview-header", Static)
			table = self.query_one("#preview-matches", DataTable)
		except NoMatches:
			return
		header.update("")
		self._reset_preview_table(table)
		self._preview_rows = []
		if result is None:
			return
		query = self._query_builder().to_query_string()
		path_text = result.path.as_posix()
		label_text = self._match_labels(result)
		header.update(f"{path_text}  ·  {format_score_percent(result.score)}  ·  matched: {label_text}")
		for location, preview, score, plain_text, _line in iter_grouped_line_displays(
			result.lines, query=query, highlight="bold"
		):
			self._preview_rows.append(_PreviewRow(location=location, plain_text=plain_text, score=score))
			table.add_row(
				format_score_percent(score),
				_preview_location_cell(location),
				Text.from_markup(preview),
			)
		table.scroll_home(immediate=True, animate=False)

	def _trim_results_to_limit(self):
		if self._active_file_limit is None:
			return
		if len(self._results) <= self._active_file_limit:
			return
		trimmed = self._results[: self._active_file_limit]
		self._results = trimmed
		self._result_index = {item.path.as_posix(): item for item in trimmed}

	def _rebuild_results_table(self, *, select_path: str | None = None):
		table = self.query_one("#results-table", DataTable)
		table.clear(columns=False)
		select_row = 0
		for index, item in enumerate(self._results):
			path_text = item.path.as_posix()
			table.add_row(format_score_percent(item.score), path_text, self._match_labels(item), key=path_text)
			if select_path is not None and path_text == select_path:
				select_row = index
		if self._results:
			table.move_cursor(row=select_row)
		self._sync_results_empty_hint()

	def _insert_result_row(self, result: FileSearchResult):
		path_key = result.path.as_posix()
		if path_key in self._result_index:
			return
		self._results.append(result)
		self._result_index[path_key] = result
		self._results.sort(key=lambda item: item.score, reverse=True)
		self._trim_results_to_limit()
		select_path = path_key if path_key in self._result_index else None
		self._rebuild_results_table(select_path=select_path)

	def action_focus_query(self):
		self._query_builder().focus_first_term()

	def action_show_help(self):
		self.push_screen(HelpModal())

	@work
	async def action_open_search_filters(self):
		filters = await self.push_screen_wait(SearchFiltersModal(self.search_filters))
		if filters is not None:
			self.search_filters = filters
			apply_search_filters_to_args(self._args, filters)
			self._refresh_filters_summary()
			self._update_search_button_state()

	@work
	async def action_open_search_options(self):
		options = await self.push_screen_wait(SearchOptionsModal(self.search_options))
		if options is not None:
			self.search_options = options
			apply_search_options_to_args(self._args, options)
			self._refresh_options_summary()
			self._update_search_button_state()

	def action_open_file(self):
		table = self.query_one("#results-table", DataTable)
		if table.row_count == 0:
			return
		row_index = table.cursor_row
		if row_index < 0 or row_index >= len(self._results):
			return
		self._open_path(self._results[row_index].path)

	def _selected_result(self) -> FileSearchResult | None:
		table = self.query_one("#results-table", DataTable)
		if table.row_count == 0:
			return None
		row_index = table.cursor_row
		if row_index < 0 or row_index >= len(self._results):
			return None
		return self._results[row_index]

	def _copy_text(self, text: str, *, label: str):
		if not text.strip():
			self.notify(f"Nothing to copy ({label})", severity="warning")
			return
		try:
			self._desktop.copy_text(text)
		except OSError:
			self.notify(f"Could not copy {label}", severity="error")
			return
		self.notify(f"Copied {label}", timeout=1.5)

	def action_copy_path(self):
		result = self._selected_result()
		if result is None:
			self.notify("No file selected", severity="warning")
			return
		self._copy_text(result.path.as_posix(), label="path")

	def action_copy_match(self):
		if not self._preview_rows:
			self.notify("No preview match to copy", severity="warning")
			return
		table = self.query_one("#preview-matches", DataTable)
		row_index = table.cursor_row
		if row_index < 0 or row_index >= len(self._preview_rows):
			row_index = 0
		row = self._preview_rows[row_index]
		self._copy_text(f"{row.location}\t{row.plain_text}", label="match")

	def action_copy_all_matches(self):
		if not self._preview_rows:
			self.notify("No matches to copy", severity="warning")
			return
		lines = [f"{format_score_percent(row.score)}\t{row.location}\t{row.plain_text}" for row in self._preview_rows]
		self._copy_text("\n".join(lines), label="all matches")

	def _open_path(self, path: Path):
		try:
			self._desktop.open_path(path)
		except OSError:
			self.notify(f"Could not open {path}", severity="error")

	def action_start_search(self):
		if self._searching:
			return
		try:
			args = self._sync_args_from_ui()
		except ValueError as error:
			self.notify(str(error), severity="warning")
			return
		if not self._query_builder().has_nonempty_term():
			self.notify(tr("error.enter_search_query"), severity="warning")
			return
		self._active_file_limit = args.limit
		self._searching = True
		self._cancel_search = False
		self._exit_code = 0
		self._reset_results()
		progress = self.query_one("#scan-progress", ProgressBar)
		progress.update(total=100, progress=0)
		self._clear_activity_status()
		self._set_status(tr("status.starting"))
		self._start_search_flow(args)

	@work(exclusive=True)
	async def _start_search_flow(self, args: argparse.Namespace):
		try:
			error = await run_tui_preflight(self, args)
		except Exception as exc:
			error = str(exc)
		if error is not None:
			self.push_screen(ErrorModal(error))
			self._exit_code = 2
			self._searching = False
			self._set_status(error)
			self._save_search_snapshot()
			self._sync_results_empty_hint()
			return
		await self._run_search_with_queue(args)

	async def _run_search_with_queue(self, args: argparse.Namespace):
		if self._search_runner.uses_subprocess(args):
			await self._run_search_in_subprocess(args)
			return
		await self._run_search_in_thread(args)

	def _post_search_queue_event(self, message: _SearchEvent | object):
		if message is _SEARCH_SENTINEL:
			return
		if isinstance(message, (ProgressUpdated, ActivityChanged, ResultFound, SearchError, SearchFinished)):
			self.post_message(message)

	def _refresh_i18n(self):
		try:
			self.query_one("#path-label", Label).update(tr("tui.path"))
			self.query_one("#search-button", Button).label = tr("tui.search")
			self.query_one("#search-options-button", Button).label = tr("tui.search_options")
			self.query_one("#search-filters-button", Button).label = tr("tui.filters")
		except NoMatches:
			pass
		if not self._searching:
			self._set_status(tr("status.ready"))
		self._sync_results_empty_hint()
		self._refresh_options_summary()
		self._refresh_filters_summary()

	def _post_subprocess_event(self, event: dict[str, object]):
		from srxy.application.search_session import (
			SearchActivityEvent,
			SearchErrorEvent,
			SearchFinishedEvent,
			SearchProgressEvent,
			SearchResultEvent,
		)

		parsed = subprocess_event_to_search_event(event)
		if isinstance(parsed, SearchProgressEvent):
			self.post_message(ProgressUpdated(parsed.current, parsed.total))
		elif isinstance(parsed, SearchActivityEvent):
			self.post_message(ActivityChanged(parsed.update))
		elif isinstance(parsed, SearchResultEvent):
			self.post_message(ResultFound(parsed.result))
		elif isinstance(parsed, SearchErrorEvent):
			self.post_message(SearchError(parsed.message))
		elif isinstance(parsed, SearchFinishedEvent):
			self.post_message(
				SearchFinished(
					results=parsed.results,
					skipped_files=parsed.skipped_files,
					cancelled=parsed.cancelled,
				)
			)

	async def _drain_search_events(
		self,
		*,
		get_event: Callable[[], object | None],
		is_done: Callable[[], bool],
		post_event: Callable[[object], None],
	):
		while not self._cancel_search:
			message = get_event()
			if message is None:
				if is_done():
					break
				await asyncio.sleep(0.05)
				continue
			if message is _SEARCH_SENTINEL:
				break
			post_event(message)

		while True:
			message = get_event()
			if message is None:
				if is_done():
					break
				await asyncio.sleep(0.05)
				continue
			if message is _SEARCH_SENTINEL:
				break
			post_event(message)

	async def _run_search_in_thread(self, args: argparse.Namespace):
		from srxy.application.search_session import (
			SearchActivityEvent,
			SearchErrorEvent,
			SearchFinishedEvent,
			SearchProgressEvent,
			SearchResultEvent,
		)

		event_queue: queue.Queue[_SearchEvent | object] = queue.Queue()

		def run_search():
			def on_event(event: object):
				if isinstance(event, SearchProgressEvent):
					event_queue.put(ProgressUpdated(event.current, event.total))
				elif isinstance(event, SearchActivityEvent):
					event_queue.put(ActivityChanged(event.update))
				elif isinstance(event, SearchResultEvent):
					event_queue.put(ResultFound(event.result))
				elif isinstance(event, SearchErrorEvent):
					event_queue.put(SearchError(event.message))
				elif isinstance(event, SearchFinishedEvent):
					event_queue.put(
						SearchFinished(
							results=event.results,
							skipped_files=event.skipped_files,
							cancelled=event.cancelled,
						)
					)

			self._search_runner.run_blocking(args, on_event=on_event, cancel_check=lambda: self._cancel_search)
			event_queue.put(_SEARCH_SENTINEL)

		search_task = asyncio.create_task(asyncio.to_thread(run_search))

		def get_event():
			try:
				return event_queue.get_nowait()
			except queue.Empty:
				return None

		try:
			await self._drain_search_events(
				get_event=get_event,
				is_done=search_task.done,
				post_event=self._post_search_queue_event,
			)
		finally:
			await search_task

	async def _run_search_in_subprocess(self, args: argparse.Namespace):
		runner = self._search_runner
		if not isinstance(runner, AdaptiveSearchRunner):
			self.post_message(SearchError("subprocess search requires AdaptiveSearchRunner"))
			return
		terminal_event = False
		events = runner.iter_subprocess_events(
			args,
			cancel_check=lambda: self._cancel_search,
			on_process=self._register_search_subprocess,
		)
		try:
			async for event in events:
				if self._cancel_search:
					break
				event_type = event.get("type")
				if event_type in {"finished", "error"}:
					terminal_event = True
				self._post_subprocess_event(event)
		except Exception as error:
			self.post_message(SearchError(str(error)))
			return
		finally:
			self._search_subprocess = None
			await events.aclose()

		if not terminal_event and not self._cancel_search:
			self.post_message(SearchError("search worker exited unexpectedly"))
			return

		if self._cancel_search:
			self._searching = False
			self._set_status(tr("status.search_cancelled"))
			self._save_search_snapshot()

	@on(ProgressUpdated)
	def _on_progress_updated(self, message: ProgressUpdated):
		progress = self.query_one("#scan-progress", ProgressBar)
		if message.total <= 0:
			progress.update(total=100, progress=0)
			return
		percent = int((message.current / message.total) * 100)
		progress.update(total=100, progress=percent)
		# Sticky "Searching…" must not block determinate Scanning N/M text.
		if is_generic_searching_activity(self._activity, searching_label=tr("activity.searching")):
			self._set_status(tr("tui.status.scanning_files", current=message.current, total=message.total))

	def _clear_activity_status(self):
		if self._activity_spinner_timer is not None:
			self._activity_spinner_timer.stop()
			self._activity_spinner_timer = None
		self._activity = None
		self._activity_spinner_index = 0

	def _refresh_activity_status(self):
		if self._activity is None:
			return
		frame = ACTIVITY_SPINNER_FRAMES[self._activity_spinner_index % len(ACTIVITY_SPINNER_FRAMES)]
		self._set_status(format_activity_status(self._activity, spinner_frame=frame))

	def _tick_activity_spinner(self):
		if self._activity is None:
			self._clear_activity_status()
			return
		self._activity_spinner_index += 1
		self._refresh_activity_status()

	def _start_activity_spinner_if_needed(self):
		if self._activity_spinner_timer is None:
			self._activity_spinner_timer = self.set_interval(0.1, self._tick_activity_spinner)

	@on(ActivityChanged)
	def _on_activity_changed(self, message: ActivityChanged):
		activity = message.activity
		if activity is None:
			self._clear_activity_status()
			return
		self._activity = activity
		self._start_activity_spinner_if_needed()
		self._refresh_activity_status()

	@on(ResultFound)
	def _on_result_found(self, message: ResultFound):
		self._insert_result_row(message.result)
		self._set_status(tr("tui.status.match_found", name=message.result.path.name))

	@on(SearchError)
	def _on_search_error(self, message: SearchError):
		self._searching = False
		self._exit_code = 2
		self.push_screen(ErrorModal(message.error))
		self._set_status(message.error)
		self._save_search_snapshot()
		self._sync_results_empty_hint()

	@on(SearchFinished)
	def _on_search_finished(self, message: SearchFinished):
		self._searching = False
		if message.cancelled:
			self._clear_activity_status()
			progress = self.query_one("#scan-progress", ProgressBar)
			progress.update(total=100, progress=100)
			self._exit_code = 2
			self._set_status(tr("status.search_cancelled"))
			self._save_search_snapshot()
			self._sync_results_empty_hint()
			return
		for result in message.results:
			self._insert_result_row(result)
		self._trim_results_to_limit()
		self._rebuild_results_table(select_path=self._results[0].path.as_posix() if self._results else None)
		query = self._query_builder().to_query_string()
		path = self.query_one("#path-input", Input).value or "."
		warnings = format_skipped_file_warnings(message.skipped_files, self._sync_args_from_ui().max_file_size)
		if warnings:
			self._warnings_text = warnings
			self.query_one("#warnings-log", Static).update(warnings)
		match_count = len(message.results) if message.results else len(self._results)
		if match_count == 0:
			self._exit_code = 1
			self._set_status(format_no_matches_message(query, path))
		else:
			self._exit_code = 0
			summary = format_grouped_summary(match_count=match_count, query=query)
			self._set_status(summary)
			if self._results:
				self._update_preview(self._results[0])
		progress = self.query_one("#scan-progress", ProgressBar)
		progress.update(total=100, progress=100)
		self._clear_activity_status()
		self._save_search_snapshot()
		self._sync_results_empty_hint()

	@on(DataTable.RowHighlighted, "#results-table")
	def _on_results_row_highlighted(self, event: DataTable.RowHighlighted):
		if event.cursor_row < 0:
			return
		if event.cursor_row < len(self._results):
			self._update_preview(self._results[event.cursor_row])

	def on_button_pressed(self, event: Button.Pressed):
		if event.button.id == "search-button":
			self.action_start_search()
		elif event.button.id == "search-options-button":
			self.action_open_search_options()
		elif event.button.id == "search-filters-button":
			self.action_open_search_filters()

	def on_input_changed(self, event: Input.Changed):
		if event.input.id == "path-input":
			self._update_search_button_state()
		elif event.input.id is not None and event.input.id.startswith("query-term-"):
			self._update_search_button_state()

	def on_input_submitted(self, event: Input.Submitted):
		if event.input.id == "path-input" or (event.input.id is not None and event.input.id.startswith("query-term-")):
			self.action_start_search()

	@on(QueryBuilder.Changed)
	def _on_query_builder_changed(self, _event: QueryBuilder.Changed):
		self._update_search_button_state()

	def _register_search_subprocess(self, process: asyncio.subprocess.Process):
		self._search_subprocess = process

	def _kill_search_worker_sync(self):
		process = self._search_subprocess
		self._search_subprocess = None
		if process is None or process.returncode is not None:
			return
		try:
			process.kill()
		except ProcessLookupError:
			return
		transport = getattr(process, "_transport", None)
		if transport is not None:
			try:
				transport.close()
			except Exception:  # noqa: S110
				pass

	def action_request_quit(self):
		if self._searching:
			self._cancel_search = True
			self._kill_search_worker_sync()
		self.exit(self._exit_code)


def run_tui(args: argparse.Namespace, *, auto_start: bool = False) -> int:
	if sys.platform != "win32":
		try:
			multiprocessing.set_start_method("fork", force=True)
		except (RuntimeError, ValueError):
			pass
	services = build_app_services()
	app = SrxyApp(
		args,
		auto_start=auto_start,
		search_runner=services.search_runner,
	)
	result = app.run()
	return result if result is not None else 0


__all__ = ["SrxyApp", "run_tui"]
