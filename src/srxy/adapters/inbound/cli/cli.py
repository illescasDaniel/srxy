from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import IO, Callable, TextIO

from srxy.adapters.outbound.models.model_store import (
	ensure_semantic_image_model,
	ensure_semantic_text_model,
	ensure_transcribe_model,
	semantic_image_model_missing_message,
	semantic_text_model_missing_message,
	transcribe_model_missing_message,
)
from srxy.adapters.outbound.ocr.ocr_text import is_ocr_available, ocr_unavailable_message
from srxy.adapters.outbound.semantic.semantic_image import (
	DEFAULT_SEMANTIC_IMAGE_THRESHOLD,
	is_semantic_image_available,
	semantic_image_unavailable_message,
)
from srxy.adapters.outbound.transcribe.transcribe_text import (
	DEFAULT_TRANSCRIBE_THRESHOLD,
	ffmpeg_available,
	ffmpeg_unavailable_message,
	transcribe_deps_installed,
	transcribe_unavailable_message,
)
from srxy.application.matching.semantic import (
	semantic_deps_unavailable_message,
	sentence_transformers_installed,
)
from srxy.application.search_formatting import (
	format_flat,
	format_flat_result,
	format_grouped,
	format_grouped_result,
	format_grouped_summary,
	format_location_label,
	format_score_percent,
	iter_grouped_line_displays,
	match_labels,
)
from srxy.application.use_cases.search_files import DEFAULT_MAX_FILE_SIZE, suggest_max_file_size
from srxy.application.utils import format_match_preview
from srxy.domain.file_query import FileQ, FileQueryParseError
from srxy.domain.models import FileSearchResult, SkippedFile
from srxy.domain.progress import ActivityCallback, ActivityUpdate, format_activity_status


_PROGRESS_BAR_WIDTH = 40
_TASK_BAR_WIDTH = 24
_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def format_json_result(result: FileSearchResult, *, query: str = "") -> dict[str, object]:
	return {
		"path": result.path.as_posix(),
		"score": result.score,
		"breakdown": result.breakdown,
		"term_surfaces": result.term_surfaces,
		"lines": [
			{
				"line_number": line_match.line_number,
				"location_kind": line_match.location_kind,
				"location_label": format_location_label(line_match.location_kind, line_match.line_number),
				"preview": format_match_preview(
					line_match.text,
					query,
					highlight="none" if line_match.location_kind == "semantic_image" else "guillemets",
				),
				"text": line_match.text,
				"score": line_match.score,
			}
			for line_match in result.lines
		],
	}


def format_json(results: list[FileSearchResult], *, query: str = "") -> str:
	payload = [format_json_result(result, query=query) for result in results]
	return json.dumps(payload, indent=2)


def package_version() -> str:
	try:
		return version("srxy")
	except PackageNotFoundError:
		return "unknown"


def normalize_max_file_size(value: int | None) -> int | None:
	if value is not None and value <= 0:
		return None
	return value


def format_no_matches_message(query: str, path: Path | str) -> str:
	from srxy.domain.file_query import format_query_for_display

	return f'No matches for "{format_query_for_display(query)}" in {Path(path).expanduser()}'


def format_skipped_file_warning(skipped: SkippedFile, max_file_size: int | None) -> str:
	if skipped.reason == "ocr_too_large":
		from srxy.adapters.outbound.ocr.ocr_text import ocr_max_file_size

		limit = ocr_max_file_size()
		limit_label = f"{limit:,}" if limit is not None else "limit"
		return (
			f"warning: skipped OCR in {skipped.path.as_posix()} "
			f"({skipped.size_bytes:,} bytes > --max-ocr-file-size {limit_label})\n"
			f"  hint: increase --max-ocr-file-size or unset SRXY_OCR_MAX_FILE_SIZE"
		)
	if skipped.reason == "transcribe_too_large":
		from srxy.adapters.outbound.transcribe.transcribe_text import transcribe_max_file_size

		limit = transcribe_max_file_size()
		limit_label = f"{limit:,}" if limit is not None else "limit"
		return (
			f"warning: skipped transcription in {skipped.path.as_posix()} "
			f"({skipped.size_bytes:,} bytes > --max-transcribe-file-size {limit_label})\n"
			f"  hint: increase --max-transcribe-file-size or unset SRXY_TRANSCRIBE_MAX_FILE_SIZE"
		)

	suggested = suggest_max_file_size(skipped.size_bytes)
	return (
		f"warning: skipped content search in {skipped.path.as_posix()} "
		f"({skipped.size_bytes:,} bytes > --max-file-size {max_file_size:,})\n"
		f"  hint: rerun with --max-file-size {suggested}"
	)


def format_skipped_file_warnings(skipped_files: list[SkippedFile], max_file_size: int | None) -> str:
	if not skipped_files:
		return ""

	lines: list[str] = []
	for skipped in skipped_files:
		lines.append(format_skipped_file_warning(skipped, max_file_size))
	return "\n".join(lines)


def _terminal_size(stream: TextIO) -> tuple[int, int]:
	try:
		size = os.get_terminal_size(stream.fileno())
	except (OSError, AttributeError):
		try:
			size = os.get_terminal_size()
		except OSError:
			return (80, 24)
	return (size.columns, size.lines)


class ProgressBar:
	def __init__(self, stream: TextIO | None = None):
		self._stream = stream or sys.stderr
		self._tty = self._stream.isatty()
		self._current = 0
		self._total = 0
		self._activity: ActivityUpdate | None = None
		self._spinner_index = 0
		self._spinner_stop = threading.Event()
		self._spinner_thread: threading.Thread | None = None
		self._match_flash = False
		self._two_line = False

	def flash_match(self):
		self._match_flash = True
		if self._tty and (self._searching() or self._activity is not None):
			self.refresh()

	def _stop_spinner(self):
		if self._spinner_thread is None:
			return
		self._spinner_stop.set()
		self._spinner_thread.join(timeout=1.0)
		self._spinner_thread = None
		self._spinner_stop.clear()

	def set_activity(self, update: ActivityUpdate | None):
		if update == self._activity:
			return
		self._match_flash = False
		was_two_line = self._two_line
		self._stop_spinner()
		self._activity = update
		self._two_line = update is not None
		if not self._tty:
			if update is not None and update.determinate:
				print(self._format_task_line(width=_TASK_BAR_WIDTH + 32), file=self._stream, flush=True)
			return
		if update is None:
			if was_two_line:
				self._erase_second_line()
			if self._searching():
				self.refresh()
			return
		if update.indeterminate:
			self._spinner_thread = threading.Thread(target=self._run_spinner, daemon=True)
			self._spinner_thread.start()
		else:
			self.refresh()

	def _erase_second_line(self):
		self._stream.write("\n\x1b[2K\x1b[1A")
		self._stream.flush()

	def _run_spinner(self):
		while not self._spinner_stop.is_set():
			frame = _SPINNER_FRAMES[self._spinner_index % len(_SPINNER_FRAMES)]
			self._spinner_index += 1
			self._write_display(spinner_frame=frame)
			if self._spinner_stop.wait(0.1):
				break

	def _truncate(self, message: str, *, width: int) -> str:
		if len(message) <= width:
			return message
		return message[: max(0, width - 3)] + "..."

	def _format_file_bar(self, *, width: int) -> str:
		ratio = self._current / self._total if self._total else 0.0
		filled = int(_PROGRESS_BAR_WIDTH * ratio)
		bar = "█" * filled + "░" * (_PROGRESS_BAR_WIDTH - filled)
		message = f"[{bar}] {self._current}/{self._total} files"
		if self._match_flash:
			message += " · match found"
		return self._truncate(message, width=width)

	def _format_task_line(self, *, width: int, spinner_frame: str | None = None) -> str:
		if self._activity is None:
			return ""
		frame = spinner_frame or _SPINNER_FRAMES[0]
		message = format_activity_status(self._activity, spinner_frame=frame)
		return self._truncate(message, width=width)

	def _write_display(self, *, spinner_frame: str | None = None):
		columns, _ = _terminal_size(self._stream)
		line1 = self._format_file_bar(width=columns) if self._total > 0 else ""
		if self._activity is None:
			if not line1:
				return
			self._stream.write(f"\r\x1b[2K{line1}")
		else:
			line2 = self._format_task_line(width=columns, spinner_frame=spinner_frame)
			if line1:
				self._stream.write(f"\r\x1b[2K{line1}\n\x1b[2K{line2}\x1b[1A")
			else:
				self._stream.write(f"\r\x1b[2K{line2}")
		self._stream.flush()

	def _searching(self) -> bool:
		return self._total > 0 and self._current < self._total

	def clear(self):
		self._stop_spinner()
		if not self._tty:
			return
		if self._two_line:
			self._stream.write("\x1b[2K\n\x1b[2K\x1b[1A")
		else:
			self._stream.write("\r\x1b[2K")
		self._stream.flush()

	def refresh(self):
		if not self._tty:
			return
		if self._total <= 0 and self._activity is None:
			return
		self._write_display()

	def update(self, current: int, total: int):
		self._match_flash = False
		self._current = current
		self._total = total
		if total <= 0:
			return

		if not self._tty:
			if current == total or current == 1 or current % max(1, total // 20) == 0:
				print(self._format_file_bar(width=_PROGRESS_BAR_WIDTH + 24), file=self._stream, flush=True)
			return

		self.refresh()

	def write_above(self, text: str, stdout: TextIO):
		if not self._tty:
			print(text, file=stdout, flush=True)
			return
		self.clear()
		print(text, file=stdout, flush=True)
		if self._searching() or self._activity is not None:
			self.refresh()

	def finish(self):
		self._activity = None
		self._two_line = False
		if not self._tty:
			return
		self.clear()
		self._stream.write("\n")
		self._stream.flush()


def render_progress(current: int, total: int, *, stream: TextIO | None = None):
	progress = ProgressBar(stream)
	progress.update(current, total)
	if current >= total:
		progress.finish()


class StreamingResultWriter:
	def __init__(
		self,
		*,
		as_json: bool,
		output_format: str,
		query: str,
		stdout: TextIO,
		output_path: Path | None,
		progress: ProgressBar | None = None,
	):
		self._as_json = as_json
		self._output_format = output_format
		self._query = query
		self._stdout = stdout
		self._output_path = output_path
		self._progress = progress
		self._match_count = 0
		self._output_handle: IO[str] | None = None
		self._json_started = False

		if output_path is not None:
			output_path.parent.mkdir(parents=True, exist_ok=True)
			self._output_handle = output_path.open("w", encoding="utf-8")

	def _write(self, text: str):
		if self._progress is not None:
			self._progress.write_above(text, self._stdout)
		else:
			try:
				print(text, file=self._stdout, flush=True)
			except UnicodeEncodeError:
				# Last resort when stdout cannot be reconfigured (legacy Windows code pages).
				encoding = getattr(self._stdout, "encoding", None) or "utf-8"
				safe = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
				print(safe, file=self._stdout, flush=True)
		if self._output_handle is not None:
			self._output_handle.write(text)
			self._output_handle.write("\n")
			self._output_handle.flush()

	def write_result(self, result: FileSearchResult):
		separator = self._match_count > 0
		self._match_count += 1

		if self._as_json:
			payload = format_json_result(result, query=self._query)
			encoded = json.dumps(payload, indent=2)
			if not self._json_started:
				self._write("[")
				self._json_started = True
			else:
				self._write(",")
			self._write(encoded)
			return

		if self._output_format == "flat":
			for line in format_flat_result(result):
				self._write(line)
			return

		self._write(format_grouped_result(result, query=self._query, separator=separator))

	def finalize(self):
		if self._as_json:
			if self._json_started:
				self._write("]")
			else:
				self._write("[]")
			return

		if self._match_count == 0:
			return

		if self._output_format == "grouped":
			summary = format_grouped_summary(match_count=self._match_count, query=self._query)
			self._write("")
			self._write(summary)

	def close(self):
		if self._output_handle is not None:
			self._output_handle.close()


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		prog="srxy",
		description="Fuzzy file and content search using composite matchers.",
	)
	parser.add_argument(
		"--version",
		action="version",
		version=f"%(prog)s {package_version()}",
	)
	parser.add_argument(
		"--language",
		choices=["en", "es"],
		default=None,
		help="UI language (default: system / SRXY_LANGUAGE / settings)",
	)
	parser.add_argument(
		"query",
		nargs="?",
		default=None,
		help="Search string; use | for OR, & for AND, quotes for phrases (e.g. '(red|blue)&color')",
	)
	parser.add_argument("path", nargs="?", default=".", help="File or directory to search (default: .)")
	parser.add_argument("--threshold", type=float, default=0.35, help="Minimum match score (default: 0.35)")
	parser.add_argument(
		"--max-file-size",
		type=int,
		default=DEFAULT_MAX_FILE_SIZE,
		help=(
			f"Skip text and document content search in files larger than this many bytes "
			f"(default: {DEFAULT_MAX_FILE_SIZE:,}; use 0 for unlimited)"
		),
	)
	parser.add_argument(
		"--max-matches",
		type=int,
		default=50,
		help="Maximum matching results per file: lines, OCR, transcript, metadata, etc. (default: 50)",
	)
	parser.add_argument(
		"--max-line-matches",
		type=int,
		dest="max_matches",
		help=argparse.SUPPRESS,
	)
	parser.add_argument(
		"-l",
		"--limit",
		type=int,
		default=None,
		help="Maximum number of matched files to return (default: unlimited)",
	)
	parser.add_argument(
		"--format",
		choices=("grouped", "flat"),
		default="grouped",
		help="Output format for human-readable results (default: grouped)",
	)
	parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
	parser.add_argument("--semantic", action="store_true", help="Enable semantic matching (SRXY_SEMANTIC=1)")
	parser.add_argument(
		"--semantic-image",
		action="store_true",
		help="Enable CLIP image semantic search on raster images (SRXY_SEMANTIC_IMAGE=1)",
	)
	parser.add_argument(
		"--semantic-image-threshold",
		type=float,
		default=DEFAULT_SEMANTIC_IMAGE_THRESHOLD,
		help=(
			f"Minimum CLIP image semantic score when it is the best match (default: {DEFAULT_SEMANTIC_IMAGE_THRESHOLD})"
		),
	)
	parser.add_argument(
		"--semantic-all",
		action="store_true",
		help="Enable text semantic, image semantic (CLIP), OCR, and transcription together",
	)
	parser.add_argument(
		"--ocr", action="store_true", help="Enable OCR for images and embedded document images (SRXY_OCR=1)"
	)
	parser.add_argument(
		"--max-ocr-file-size",
		type=int,
		default=None,
		help="Skip OCR on files larger than this many bytes (no default limit)",
	)
	parser.add_argument(
		"--transcribe",
		action="store_true",
		help="Enable audio/video transcription for searchable speech (SRXY_TRANSCRIBE=1)",
	)
	parser.add_argument(
		"--max-transcribe-file-size",
		type=int,
		default=None,
		help="Skip transcription on files larger than this many bytes (no default limit)",
	)
	parser.add_argument(
		"--transcribe-model",
		default=None,
		help="Whisper model size/name for transcription (default: base; SRXY_TRANSCRIBE_MODEL)",
	)
	parser.add_argument(
		"--transcribe-threshold",
		type=float,
		default=DEFAULT_TRANSCRIBE_THRESHOLD,
		help=(
			f"Minimum transcript score when transcription is the best match (default: {DEFAULT_TRANSCRIBE_THRESHOLD})"
		),
	)
	parser.add_argument(
		"--progress",
		action=argparse.BooleanOptionalAction,
		default=None,
		help="Show file-scan progress on stderr (default: on when stderr is a terminal)",
	)
	parser.add_argument(
		"-o",
		"--output",
		type=Path,
		help="Save search results to this file (same format as stdout)",
	)

	mode_group = parser.add_mutually_exclusive_group()
	mode_group.add_argument(
		"--names-only", action="store_true", help="Search file names only (disables docs/tags/metadata)"
	)
	mode_group.add_argument(
		"--content-only",
		action="store_true",
		help="Search docs/tags/metadata only (disables file names; power-ups still optional)",
	)

	search_group = parser.add_mutually_exclusive_group()
	search_group.add_argument(
		"--names", action="store_true", dest="search_names", default=None, help="Search file names"
	)
	search_group.add_argument("--no-names", action="store_false", dest="search_names", help="Skip file name search")

	content_group = parser.add_mutually_exclusive_group()
	content_group.add_argument(
		"--content",
		action="store_true",
		dest="search_contents",
		default=None,
		help="Search file contents (docs/tags, OCR, speech, visual; default on)",
	)
	content_group.add_argument(
		"--no-content",
		action="store_false",
		dest="search_contents",
		help="Skip file contents (filename-only unless other where options apply)",
	)

	docs_group = parser.add_mutually_exclusive_group()
	docs_group.add_argument(
		"--docs-tags",
		action="store_true",
		dest="search_docs_tags",
		default=None,
		help="Search docs, tags & metadata inside files (recommended; default on)",
	)
	docs_group.add_argument(
		"--no-docs-tags",
		action="store_false",
		dest="search_docs_tags",
		help="Skip docs/tags/metadata (OCR / speech / visual can still run with --content)",
	)

	parser.add_argument(
		"--include-hidden",
		action="store_true",
		help="Search hidden directories and files (default: skip dot-prefixed entries)",
	)
	parser.add_argument(
		"--include-noise",
		action="store_true",
		help="Search noise directories like __pycache__ and node_modules (default: skip)",
	)
	parser.add_argument(
		"--include-noise-files",
		action="store_true",
		help="Search junk/lock/temp files like uv.lock, package-lock.json, *.min.js (default: skip)",
	)
	parser.add_argument(
		"--match-skipped-names",
		action="store_true",
		help="Match filenames of otherwise-skipped hidden/cache/junk paths (content still skipped)",
	)
	parser.add_argument(
		"--include-archives",
		action="store_true",
		help="Search inside compressed archives (.zip, .tar, .tar.gz, .gz) (default: skip)",
	)
	parser.add_argument(
		"--include-subdirectories",
		action=argparse.BooleanOptionalAction,
		default=True,
		help="Recurse into subdirectories (default: on; use --no-include-subdirectories for this folder only)",
	)
	parser.add_argument(
		"--cli",
		action="store_true",
		help="Force plain-text CLI output (no GUI or TUI)",
	)
	parser.add_argument(
		"--tui",
		action="store_true",
		help="Force the Textual TUI (skip GUI)",
	)

	return parser


def resolve_search_modes(args: argparse.Namespace) -> tuple[bool, bool]:
	from srxy.application.search_runner import resolve_search_modes as _resolve

	return _resolve(args)


def resolve_show_progress(args: argparse.Namespace) -> bool:
	if args.progress is not None:
		return args.progress
	return sys.stderr.isatty()


def render_results(
	results: list[FileSearchResult],
	*,
	as_json: bool,
	output_format: str,
	query: str = "",
) -> str:
	if as_json:
		return format_json(results, query=query)
	if output_format == "flat":
		return format_flat(results)
	return format_grouped(results, query=query)


def should_use_tui(args: argparse.Namespace) -> bool:
	from srxy.application.launch import should_use_tui as _should

	return _should(args)


def should_use_gui(args: argparse.Namespace) -> bool:
	from srxy.application.launch import should_use_gui as _should

	return _should(args)


def apply_args_to_env(args: argparse.Namespace):
	from srxy.application.search_runner import apply_args_to_env as _apply

	_apply(args)


def _args_want_ocr(args: argparse.Namespace) -> bool:
	return bool(args.ocr or args.semantic_all)


def _args_want_transcribe(args: argparse.Namespace) -> bool:
	return bool(args.transcribe or args.semantic_all)


def _args_want_semantic_text(args: argparse.Namespace) -> bool:
	return bool(args.semantic or args.semantic_all)


def _args_want_semantic_image(args: argparse.Namespace) -> bool:
	return bool(args.semantic_image or args.semantic_all)


def sync_options_to_args(
	args: argparse.Namespace,
	*,
	search_names: bool,
	search_contents: bool,
	search_docs_tags: bool = True,
	semantic: bool,
	semantic_image: bool,
	ocr: bool,
	transcribe: bool,
	include_hidden: bool,
	include_noise: bool,
	include_noise_files: bool = False,
	match_skipped_names: bool = False,
	include_archives: bool,
	include_subdirectories: bool = True,
):
	from srxy.application.search_options import sync_options_to_args as _sync

	_sync(
		args,
		search_names=search_names,
		search_contents=search_contents,
		search_docs_tags=search_docs_tags,
		semantic=semantic,
		semantic_image=semantic_image,
		ocr=ocr,
		transcribe=transcribe,
		include_hidden=include_hidden,
		include_noise=include_noise,
		include_noise_files=include_noise_files,
		match_skipped_names=match_skipped_names,
		include_archives=include_archives,
		include_subdirectories=include_subdirectories,
	)


def run_preflight(
	args: argparse.Namespace,
	*,
	interactive: bool,
	prompt_yes: Callable[[str], bool] | None = None,
) -> str | None:
	apply_args_to_env(args)

	if _args_want_ocr(args) and not is_ocr_available():
		return ocr_unavailable_message()

	if _args_want_transcribe(args) and not transcribe_deps_installed():
		return transcribe_unavailable_message()
	if _args_want_transcribe(args) and not ffmpeg_available():
		return ffmpeg_unavailable_message()
	if _args_want_transcribe(args) and not ensure_transcribe_model(
		interactive=interactive,
		prompt_yes=prompt_yes,
	):
		return transcribe_model_missing_message()

	if _args_want_semantic_text(args):
		if not sentence_transformers_installed():
			return semantic_deps_unavailable_message()
		if not ensure_semantic_text_model(interactive=interactive, prompt_yes=prompt_yes):
			return semantic_text_model_missing_message()

	if _args_want_semantic_image(args):
		if not is_semantic_image_available():
			return semantic_image_unavailable_message()
		if not ensure_semantic_image_model(interactive=interactive, prompt_yes=prompt_yes):
			return semantic_image_model_missing_message()

	return None


def resolve_file_query(args: argparse.Namespace) -> FileQ:
	from srxy.application.search_runner import resolve_file_query as _resolve

	return _resolve(args)


def execute_search(
	args: argparse.Namespace,
	*,
	skipped_files: list[SkippedFile] | None = None,
	on_progress: Callable[[int, int], None] | None = None,
	on_activity: ActivityCallback | None = None,
	on_result: Callable[[FileSearchResult], None] | None = None,
) -> tuple[list[FileSearchResult], list[SkippedFile]]:
	from srxy.application.search_runner import execute_search as _execute

	return _execute(
		args,
		skipped_files=skipped_files,
		on_progress=on_progress,
		on_activity=on_activity,
		on_result=on_result,
		allow_process_pool=True,
	)


def run_plain(args: argparse.Namespace) -> int:
	from srxy.bootstrap import build_app_services

	if args.query is None:
		print("error: the following arguments are required: query", file=sys.stderr)
		return 2

	error = run_preflight(args, interactive=sys.stdin.isatty())
	if error is not None:
		print(error, file=sys.stderr)
		return 2

	try:
		resolve_file_query(args)
	except FileQueryParseError as error:
		print(f"error: invalid query: {error}", file=sys.stderr)
		return 2

	services = build_app_services()
	skipped_files: list[SkippedFile] = []
	show_progress = resolve_show_progress(args)
	progress = ProgressBar() if show_progress else None
	writer = StreamingResultWriter(
		as_json=args.json,
		output_format=args.format,
		query=args.query,
		stdout=sys.stdout,
		output_path=args.output,
		progress=progress,
	)

	def on_progress(current: int, total: int):
		if progress is not None:
			progress.set_activity(None)
			progress.update(current, total)

	def on_activity(update: ActivityUpdate | None):
		if progress is not None:
			progress.set_activity(update)

	def on_result(_result: FileSearchResult):
		if progress is not None:
			progress.flash_match()

	try:
		results, skipped_files = services.file_search.execute(
			args,
			skipped_files=skipped_files,
			on_progress=on_progress,
			on_activity=on_activity,
			on_result=on_result,
		)
	except FileNotFoundError as error:
		if progress is not None:
			progress.finish()
		writer.close()
		print(error, file=sys.stderr)
		return 2
	except ValueError as error:
		if progress is not None:
			progress.finish()
		writer.close()
		print(error, file=sys.stderr)
		return 2

	if progress is not None:
		progress.finish()

	for result in results:
		writer.write_result(result)
	writer.finalize()
	writer.close()

	skipped_warnings = format_skipped_file_warnings(skipped_files, args.max_file_size)
	if skipped_warnings:
		print(skipped_warnings, file=sys.stderr)

	if not results:
		print(format_no_matches_message(args.query, args.path), file=sys.stderr)

	return 0 if results else 1


def _configure_stdio_utf8():
	"""Prefer UTF-8 on Windows consoles so grouped CLI glyphs (── │ ·) print cleanly."""
	for stream in (sys.stdout, sys.stderr):
		reconfigure = getattr(stream, "reconfigure", None)
		if callable(reconfigure):
			try:
				reconfigure(encoding="utf-8", errors="replace")
			except (OSError, ValueError, AttributeError):
				pass


def main(argv: list[str] | None = None) -> int:
	_configure_stdio_utf8()
	parser = build_parser()
	args = parser.parse_args(argv)
	from srxy.application.settings import set_language_setting
	from srxy.i18n import resolve_language, set_language

	if getattr(args, "language", None):
		set_language(str(args.language))
		set_language_setting(str(args.language))
	else:
		set_language(resolve_language())
	auto_start = args.query is not None and bool(args.query.strip())

	if should_use_gui(args):
		from srxy.adapters.inbound.gui import run_gui

		return run_gui(args, auto_start=auto_start)

	if should_use_tui(args):
		from srxy.adapters.inbound.tui import run_tui

		return run_tui(args, auto_start=auto_start)

	from srxy.application.launch import gui_display_available, gui_importable

	# Desktop / start-menu launches have no TTY. If the GUI cannot start, exit with a
	# clear message instead of falling through to CLI (which needs a query).
	explicit_cli = bool(
		getattr(args, "cli", False)
		or args.json
		or args.format == "flat"
		or args.output is not None
		or os.environ.get("CI", "").strip().lower() in {"1", "true", "yes", "on"}
	)
	if gui_display_available() and not gui_importable() and not explicit_cli:
		message = (
			"srxy GUI could not start because PySide6 is not installed in this environment.\n"
			"Reinstall with the desktop installer (local wheel/source), or:\n"
			"  uv pip install 'PySide6>=6.6'\n"
			"Logs (prefix installs): $SRXY_HOME/logs/srxy.log"
		)
		print(message, file=sys.stderr)
		return 2

	return run_plain(args)


__all__ = [
	"ProgressBar",
	"build_parser",
	"format_flat",
	"format_flat_result",
	"format_grouped",
	"format_grouped_result",
	"format_grouped_summary",
	"format_json",
	"format_json_result",
	"format_location_label",
	"format_no_matches_message",
	"format_score_percent",
	"format_skipped_file_warning",
	"format_skipped_file_warnings",
	"iter_grouped_line_displays",
	"main",
	"match_labels",
	"package_version",
	"render_progress",
	"resolve_search_modes",
	"run_plain",
	"run_preflight",
]


if __name__ == "__main__":
	sys.exit(main())
