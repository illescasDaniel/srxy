from __future__ import annotations

import argparse
import asyncio
import multiprocessing
import os
import platform
import queue
import shutil
import subprocess
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

from srxy.cli import (
	execute_search,
	format_grouped_summary,
	format_no_matches_message,
	format_score_percent,
	format_skipped_file_warnings,
	iter_grouped_line_displays,
	match_labels,
)
from srxy.file_query import file_q_to_dict
from srxy.models import FileSearchResult, SkippedFile
from srxy.tui.messages import (
	ActivityChanged,
	ProgressUpdated,
	ResultFound,
	SearchError,
	SearchFinished,
)
from srxy.tui.modals import ErrorModal, HelpModal, SearchOptionsModal, SizeLimitsModal
from srxy.tui.preflight import run_tui_preflight
from srxy.tui.query_builder import QueryBuilder
from srxy.tui.search_options import (
	SearchOptions,
	apply_search_options_to_args,
	format_search_options_summary,
	search_options_from_args,
)
from srxy.tui.search_worker import (
	file_result_from_dict,
	iter_subprocess_search_events,
	search_uses_subprocess,
	skipped_file_from_dict,
)
from srxy.tui.size_limits import SizeLimits, apply_size_limits_to_args, parse_size_limits, size_limits_from_args
from srxy.tui.theme import detect_app_theme


_SEARCH_SENTINEL = object()
_SearchEvent = ProgressUpdated | ActivityChanged | ResultFound | SearchError | SearchFinished


@dataclass(frozen=True, slots=True)
class _SearchSnapshot:
	query: str
	path: str
	search_options: SearchOptions
	limit_text: str
	max_matches_text: str
	size_limits: SizeLimits


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

	#search-bar Button {
		height: 1;
		min-width: 10;
		border: none;
		background: $primary;
		color: $button-foreground;
		padding: 0 1;
		content-align: center middle;
	}

	#search-button.-stale {
		background: $warning;
		color: $button-foreground;
	}

	#filters-bar {
		height: auto;
		padding: 0 1 1 1;
		margin-top: 1;
	}

	#filters-bar Label {
		width: auto;
		min-width: 14;
		height: 1;
		padding: 0 1 0 0;
		content-align: right middle;
		color: $text-muted;
	}

	#filters-bar Input {
		width: 1fr;
		height: 1;
		margin-right: 1;
		border: none;
		padding: 0 1;
		color: $foreground;
		background: $surface;
		content-align: center middle;
	}

	#filters-bar Input:last-of-type {
		margin-right: 1;
	}

	#filters-bar Button {
		height: 1;
		min-width: 14;
		border: none;
		background: $surface;
		color: $foreground;
		padding: 0 1;
		content-align: center middle;
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

	#status-bar Button {
		width: auto;
		min-width: 8;
		height: 1;
		margin-left: 1;
	}

	#copy-actions {
		width: auto;
		height: auto;
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
	):
		super().__init__()
		self.theme = detect_app_theme()
		self._args = args
		self._auto_start = auto_start
		self._results: list[FileSearchResult] = []
		self._result_index: dict[str, FileSearchResult] = {}
		self._searching = False
		self._cancel_search = False
		self._exit_code = 0
		self._warnings_text = ""
		self._last_search_snapshot: _SearchSnapshot | None = None
		self._active_file_limit: int | None = None
		self._preview_rows: list[_PreviewRow] = []
		self.search_options = search_options_from_args(args)
		self.size_limits = size_limits_from_args(args)
		apply_search_options_to_args(self._args, self.search_options)
		apply_size_limits_to_args(self._args, self.size_limits)

	@property
	def exit_code(self) -> int:
		return self._exit_code

	def compose(self) -> ComposeResult:
		yield Header()
		with Horizontal(id="search-bar"):
			yield Label("Query", id="query-label")
			yield QueryBuilder(id="query-builder", initial_query=self._args.query or "")
			yield Label("Path", id="path-label")
			yield Input(id="path-input", value=str(self._args.path), placeholder="")
			yield Button("Search", variant="primary", id="search-button")
		with Horizontal(id="options-bar"):
			yield Button("Advanced", id="search-options-button")
			yield Static(format_search_options_summary(self.search_options), id="options-summary")
		with Horizontal(id="filters-bar"):
			limit_value = "" if self._args.limit is None else str(self._args.limit)
			yield Label("Top files", id="filter-limit-label")
			yield Input(placeholder="all", id="filter-limit", value=limit_value)
			yield Label("Per file", id="filter-max-matches-label")
			yield Input(id="filter-max-matches", value=str(self._args.max_matches), placeholder="")
			yield Button("Size limits", id="size-limits-button")
		with Horizontal(id="main-pane"):
			with Vertical(id="results-panel"):
				yield DataTable(id="results-table", cursor_type="row", zebra_stripes=True)
			with Vertical(id="preview-panel"):
				yield Static("", id="preview-header")
				yield DataTable(id="preview-matches", cursor_type="row", zebra_stripes=True)
		yield Static("", id="warnings-log")
		with Horizontal(id="status-bar"):
			yield ProgressBar(total=100, show_eta=False, id="scan-progress")
			yield Label("Ready", id="status-message")
			with Horizontal(id="copy-actions"):
				yield Button("Path", id="copy-path-button")
				yield Button("Match", id="copy-match-button")
				yield Button("All", id="copy-all-button")
		yield Footer(show_command_palette=False)

	def on_mount(self):
		table = self.query_one("#results-table", DataTable)
		table.add_columns("Match", "Path", "Matched")
		self._setup_preview_columns(self.query_one("#preview-matches", DataTable))
		self._refresh_options_summary()
		self._update_search_button_state()
		if self._auto_start and (self._args.query or "").strip():
			self.call_after_refresh(self.action_start_search)

	def _setup_preview_columns(self, table: DataTable[Any]):
		table.add_column("Match", width=_PREVIEW_MATCH_WIDTH)
		table.add_column("Location", width=_PREVIEW_LOCATION_WIDTH)
		table.add_column("Text")

	def _reset_preview_table(self, table: DataTable[Any]):
		table.clear(columns=True)
		self._setup_preview_columns(table)

	def _query_builder(self) -> QueryBuilder:
		return self.query_one("#query-builder", QueryBuilder)

	def _refresh_options_summary(self):
		self.query_one("#options-summary", Static).update(format_search_options_summary(self.search_options))

	def _parse_optional_positive_int(self, raw: str, *, field_name: str) -> int | None:
		text = raw.strip()
		if not text:
			return None
		try:
			value = int(text)
		except ValueError as error:
			raise ValueError(f"{field_name} must be a positive integer") from error
		if value < 1:
			raise ValueError(f"{field_name} must be at least 1")
		return value

	def _current_snapshot(self) -> _SearchSnapshot:
		builder = self._query_builder()
		return _SearchSnapshot(
			query=builder.to_query_string(),
			path=self.query_one("#path-input", Input).value or ".",
			search_options=self.search_options,
			limit_text=self.query_one("#filter-limit", Input).value,
			max_matches_text=self.query_one("#filter-max-matches", Input).value,
			size_limits=self.size_limits,
		)

	def _update_search_button_state(self):
		button = self.query_one("#search-button", Button)
		snapshot = self._current_snapshot()
		is_stale = self._last_search_snapshot is None or snapshot != self._last_search_snapshot
		button.set_class(is_stale, "-stale")

	def _save_search_snapshot(self):
		self._last_search_snapshot = self._current_snapshot()
		self._update_search_button_state()

	def _sync_args_from_ui(self) -> argparse.Namespace:
		snapshot = self._current_snapshot()
		limit = (
			self._parse_optional_positive_int(snapshot.limit_text, field_name="Top files")
			if snapshot.limit_text.strip()
			else None
		)
		max_matches = self._parse_optional_positive_int(snapshot.max_matches_text, field_name="Matches per file") or 50
		max_file_size, max_ocr_file_size, max_transcribe_file_size = parse_size_limits(snapshot.size_limits)
		args = argparse.Namespace(**vars(self._args))
		builder = self._query_builder()
		args.query = builder.to_query_string()
		args.query_expr = file_q_to_dict(builder.to_file_query())
		args.path = snapshot.path
		args.limit = limit
		args.max_matches = max_matches
		args.max_file_size = max_file_size
		args.max_ocr_file_size = max_ocr_file_size
		args.max_transcribe_file_size = max_transcribe_file_size
		apply_search_options_to_args(args, snapshot.search_options)
		return args

	def _reset_results(self):
		self._results = []
		self._result_index = {}
		table = self.query_one("#results-table", DataTable)
		table.clear(columns=False)
		self.query_one("#preview-header", Static).update("")
		self._reset_preview_table(self.query_one("#preview-matches", DataTable))
		self.query_one("#warnings-log", Static).update("")
		self._warnings_text = ""
		self._preview_rows = []

	def _set_status(self, message: str):
		self.query_one("#status-message", Label).update(message)

	def _match_labels(self, result: FileSearchResult) -> str:
		return match_labels(
			result,
			threshold=self._args.threshold,
			semantic_image_threshold=self._args.semantic_image_threshold,
		)

	def _update_preview(self, result: FileSearchResult | None):
		header = self.query_one("#preview-header", Static)
		table = self.query_one("#preview-matches", DataTable)
		header.update("")
		self._reset_preview_table(table)
		self._preview_rows = []
		if result is None:
			return
		query = self._query_builder().to_query_string()
		path_text = result.path.as_posix()
		label_text = self._match_labels(result)
		header.update(f"{path_text}  ·  {format_score_percent(result.score)}  ·  matched: {label_text}")
		for location, preview, score, plain_text in iter_grouped_line_displays(
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

	def _current_applied_size_limits(self) -> SizeLimits:
		return size_limits_from_args(self._sync_args_from_ui())

	@work
	async def action_open_search_options(self):
		options = await self.push_screen_wait(SearchOptionsModal(self.search_options))
		if options is not None:
			self.search_options = options
			apply_search_options_to_args(self._args, options)
			self._refresh_options_summary()
			self._update_search_button_state()

	@work
	async def action_open_size_limits(self):
		current = self._current_applied_size_limits()
		limits = await self.push_screen_wait(SizeLimitsModal(current))
		if limits is not None:
			self.size_limits = limits
			apply_size_limits_to_args(self._args, limits)
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
		self.copy_to_clipboard(text)
		self.notify(f"Copied {label}", timeout=1.5)

	def copy_to_clipboard(self, text: str) -> None:
		if platform.system() == "Darwin":
			pbcopy = shutil.which("pbcopy")
			if pbcopy is not None:
				try:
					subprocess.run(  # noqa: S603
						[pbcopy],
						input=text.encode("utf-8"),
						check=True,
						timeout=3,
					)
					return
				except (OSError, subprocess.SubprocessError):
					pass
		super().copy_to_clipboard(text)

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

	@on(Button.Pressed, "#copy-path-button")
	def _on_copy_path_button(self):
		self.action_copy_path()

	@on(Button.Pressed, "#copy-match-button")
	def _on_copy_match_button(self):
		self.action_copy_match()

	@on(Button.Pressed, "#copy-all-button")
	def _on_copy_all_matches_button(self):
		self.action_copy_all_matches()

	def _open_path(self, path: Path):
		from srxy.archive_search import split_archive_member_path

		archive_path, member = split_archive_member_path(path)
		open_target = archive_path if member is not None else path
		system = platform.system()
		try:
			if system == "Darwin":
				subprocess.run(["open", str(open_target)], check=False)  # noqa: S603, S607
			elif system == "Windows":
				os.startfile(str(open_target))  # type: ignore[attr-defined]  # noqa: S606
			else:
				subprocess.run(["xdg-open", str(open_target)], check=False)  # noqa: S603, S607
		except OSError:
			self.notify(f"Could not open {open_target}", severity="error")

	def action_start_search(self):
		if self._searching:
			return
		try:
			args = self._sync_args_from_ui()
		except ValueError as error:
			self.notify(str(error), severity="warning")
			return
		if not self._query_builder().has_nonempty_term():
			self.notify("Enter a search query", severity="warning")
			return
		self._active_file_limit = args.limit
		self._reset_results()
		self._searching = True
		self._cancel_search = False
		self._exit_code = 0
		progress = self.query_one("#scan-progress", ProgressBar)
		progress.update(total=100, progress=0)
		self._set_status("Starting search…")
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
			return
		await self._run_search_with_queue(args)

	async def _run_search_with_queue(self, args: argparse.Namespace):
		if search_uses_subprocess(args):
			await self._run_search_in_subprocess(args)
			return
		await self._run_search_in_thread(args)

	def _post_search_queue_event(self, message: _SearchEvent | object):
		if message is _SEARCH_SENTINEL:
			return
		if isinstance(message, (ProgressUpdated, ActivityChanged, ResultFound, SearchError, SearchFinished)):
			self.post_message(message)

	def _post_subprocess_event(self, event: dict[str, object]):
		kind = event.get("type")
		if kind == "progress":
			current = event.get("current")
			total = event.get("total")
			if isinstance(current, int) and isinstance(total, int):
				self.post_message(ProgressUpdated(current, total))
		elif kind == "activity":
			message = event.get("message")
			self.post_message(ActivityChanged(message if isinstance(message, str) else None))
		elif kind == "result":
			result_data = event.get("result")
			if isinstance(result_data, dict):
				self.post_message(ResultFound(file_result_from_dict(result_data)))
		elif kind == "error":
			message = event.get("message")
			self.post_message(SearchError(str(message)))
		elif kind == "finished":
			results_data = event.get("results")
			skipped_data = event.get("skipped_files")
			results = [file_result_from_dict(item) for item in results_data] if isinstance(results_data, list) else []
			skipped_files = (
				[skipped_file_from_dict(item) for item in skipped_data] if isinstance(skipped_data, list) else []
			)
			self.post_message(SearchFinished(results=results, skipped_files=skipped_files))

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

		if self._cancel_search:
			return

		while True:
			message = get_event()
			if message is None:
				break
			if message is _SEARCH_SENTINEL:
				continue
			post_event(message)

	async def _run_search_in_thread(self, args: argparse.Namespace):
		event_queue: queue.Queue[_SearchEvent | object] = queue.Queue()

		def run_search():
			os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
			os.environ.setdefault("OMP_NUM_THREADS", "1")
			os.environ.setdefault("TQDM_DISABLE", "1")
			os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
			os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
			os.environ.setdefault("JOBLIB_MULTIPROCESSING", "0")
			skipped_files: list[SkippedFile] = []

			def on_progress(current: int, total: int):
				event_queue.put(ProgressUpdated(current, total))

			def on_activity(message: str | None):
				event_queue.put(ActivityChanged(message))

			def on_result(result: FileSearchResult):
				event_queue.put(ResultFound(result))

			try:
				results, skipped_files = execute_search(
					args,
					skipped_files=skipped_files,
					on_progress=on_progress,
					on_activity=on_activity,
					on_result=on_result,
				)
			except Exception as error:
				event_queue.put(SearchError(str(error)))
				event_queue.put(_SEARCH_SENTINEL)
				return

			event_queue.put(SearchFinished(results=results, skipped_files=skipped_files))
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

		if self._cancel_search:
			self._searching = False
			self._set_status("Search cancelled")
			self._save_search_snapshot()

	async def _run_search_in_subprocess(self, args: argparse.Namespace):
		terminal_event = False
		try:
			async for event in iter_subprocess_search_events(args, cancel_check=lambda: self._cancel_search):
				if self._cancel_search:
					break
				event_type = event.get("type")
				if event_type in {"finished", "error"}:
					terminal_event = True
				self._post_subprocess_event(event)
		except Exception as error:
			self.post_message(SearchError(str(error)))
			return

		if not terminal_event and not self._cancel_search:
			self.post_message(SearchError("search worker exited unexpectedly"))
			return

		if self._cancel_search:
			self._searching = False
			self._set_status("Search cancelled")
			self._save_search_snapshot()

	@on(ProgressUpdated)
	def _on_progress_updated(self, message: ProgressUpdated):
		progress = self.query_one("#scan-progress", ProgressBar)
		if message.total <= 0:
			progress.update(total=100, progress=0)
			return
		percent = int((message.current / message.total) * 100)
		progress.update(total=100, progress=percent)
		self._set_status(f"Scanning {message.current}/{message.total} files")

	@on(ActivityChanged)
	def _on_activity_changed(self, message: ActivityChanged):
		if message.activity:
			self._set_status(message.activity)

	@on(ResultFound)
	def _on_result_found(self, message: ResultFound):
		self._insert_result_row(message.result)
		self._set_status(f"Match found · {message.result.path.name}")

	@on(SearchError)
	def _on_search_error(self, message: SearchError):
		self._searching = False
		self._exit_code = 2
		self.push_screen(ErrorModal(message.error))
		self._set_status(message.error)
		self._save_search_snapshot()

	@on(SearchFinished)
	def _on_search_finished(self, message: SearchFinished):
		self._searching = False
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
		if not message.results:
			self._exit_code = 1
			self._set_status(format_no_matches_message(query, path))
		else:
			self._exit_code = 0
			summary = format_grouped_summary(match_count=len(message.results), query=query)
			self._set_status(summary)
			if self._results:
				self._update_preview(self._results[0])
		progress = self.query_one("#scan-progress", ProgressBar)
		progress.update(total=100, progress=100)
		self._save_search_snapshot()

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
		elif event.button.id == "size-limits-button":
			self.action_open_size_limits()

	def on_input_changed(self, event: Input.Changed):
		if event.input.id in {
			"path-input",
			"filter-limit",
			"filter-max-matches",
		}:
			self._update_search_button_state()
		elif event.input.id is not None and event.input.id.startswith("query-term-"):
			self._update_search_button_state()

	def on_input_submitted(self, event: Input.Submitted):
		if event.input.id == "path-input" or (event.input.id is not None and event.input.id.startswith("query-term-")):
			self.action_start_search()

	@on(QueryBuilder.Changed)
	def _on_query_builder_changed(self, _event: QueryBuilder.Changed):
		self._update_search_button_state()

	def action_request_quit(self):
		if self._searching:
			self._cancel_search = True
		self.exit(self._exit_code)


def run_tui(args: argparse.Namespace, *, auto_start: bool = False) -> int:
	if sys.platform != "win32":
		try:
			multiprocessing.set_start_method("fork", force=True)
		except (RuntimeError, ValueError):
			pass
	app = SrxyApp(args, auto_start=auto_start)
	result = app.run()
	return result if result is not None else 0


__all__ = ["SrxyApp", "run_tui"]
