from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from pathlib import Path
from typing import IO, Callable, TextIO

from srxy.file_search import magic_file_search, suggest_max_file_size
from srxy.matchers.semantic import (
	semantic_env_enabled,
	sentence_transformers_installed,
)
from srxy.model_store import (
	ensure_semantic_image_model,
	ensure_semantic_text_model,
	ensure_transcribe_model,
	semantic_image_model_missing_message,
	semantic_text_model_missing_message,
	transcribe_model_missing_message,
)
from srxy.models import FileSearchResult, LineMatch, SkippedFile
from srxy.ocr_text import is_ocr_available, ocr_requested, ocr_unavailable_message
from srxy.semantic_image import (
	DEFAULT_SEMANTIC_IMAGE_THRESHOLD,
	is_semantic_image_available,
	semantic_image_requested,
	semantic_image_unavailable_message,
)
from srxy.transcribe_text import (
	DEFAULT_TRANSCRIBE_THRESHOLD,
	ffmpeg_available,
	ffmpeg_unavailable_message,
	format_transcript_timestamp,
	transcribe_deps_installed,
	transcribe_requested,
	transcribe_unavailable_message,
)
from srxy.utils import format_match_preview


_LOCATION_LABELS = {
	"line": "line",
	"page": "page",
	"paragraph": "paragraph",
	"row": "row",
	"slide": "slide",
	"tag": "tag",
	"ocr": "ocr",
	"transcript": "transcript",
}

_PROGRESS_BAR_WIDTH = 40
_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})


def format_location_label(kind: str, number: int) -> str:
	if kind == "transcript":
		return f"transcript at {format_transcript_timestamp(number)}"
	label = _LOCATION_LABELS.get(kind, kind)
	return f"{label} {number}"


def _format_transcript_locations(seconds_list: list[int]) -> str:
	timestamps = [format_transcript_timestamp(seconds) for seconds in sorted(seconds_list)]
	if len(timestamps) == 1:
		return f"transcript at {timestamps[0]}"
	return f"transcript at {', '.join(timestamps)}"


def _format_locations(kind: str, numbers: list[int]) -> str:
	if kind == "transcript":
		return _format_transcript_locations(numbers)
	label = _LOCATION_LABELS.get(kind, kind)
	sorted_numbers = sorted(numbers)
	if len(sorted_numbers) == 1:
		return f"{label} {sorted_numbers[0]}"
	return f"{label}s {_format_number_ranges(sorted_numbers)}"


def match_labels(result: FileSearchResult) -> str:
	labels: list[str] = []
	if "name" in result.breakdown and result.breakdown["name"] > 0.0:
		labels.append("name")
	if result.lines or result.breakdown.get("content", 0.0) > 0.0:
		labels.append("content")
	if result.breakdown.get("semantic_image", 0.0) > 0.0:
		labels.append("image semantic")
	return ", ".join(labels) if labels else "match"


def format_score_percent(score: float) -> str:
	return f"{round(score * 100)}%"


def format_grouped_summary(*, match_count: int, query: str = "") -> str:
	header = f"{match_count} file matched" if match_count == 1 else f"{match_count} files matched"
	if query:
		header += f' for "{query}"'
	return header


def _format_number_ranges(numbers: list[int]) -> str:
	if not numbers:
		return ""

	parts: list[str] = []
	start = numbers[0]
	prev = numbers[0]
	for number in numbers[1:]:
		if number == prev + 1:
			prev = number
			continue
		parts.append(f"{start}-{prev}" if start != prev else str(start))
		start = number
		prev = number
	parts.append(f"{start}-{prev}" if start != prev else str(start))
	return ", ".join(parts)


def iter_grouped_line_displays(
	line_matches: list[LineMatch],
	*,
	query: str,
) -> list[tuple[str, str, float]]:
	groups: dict[tuple[float, str, str], list[LineMatch]] = {}
	group_order: list[tuple[float, str, str]] = []
	for line_match in line_matches:
		preview = format_match_preview(line_match.text, query)
		key = (line_match.score, line_match.location_kind, preview)
		if key not in groups:
			groups[key] = []
			group_order.append(key)
		groups[key].append(line_match)

	displays: list[tuple[str, str, float]] = []
	for score, kind, preview in group_order:
		numbers = [line_match.line_number for line_match in groups[(score, kind, preview)]]
		displays.append((_format_locations(kind, numbers), preview, score))
	return displays


def format_grouped_result(result: FileSearchResult, *, query: str = "", separator: bool = False) -> str:
	lines: list[str] = []
	if separator:
		lines.append("")
	path_text = result.path.as_posix()
	label_text = match_labels(result)
	lines.append(f"── {path_text} ──")
	lines.append(f"   match {format_score_percent(result.score)}  ·  matched: {label_text}")
	for location, preview, score in iter_grouped_line_displays(result.lines, query=query):
		lines.append(f"   {location}  ·  match {format_score_percent(score)}")
		lines.append(f"   │ {preview}")
	return "\n".join(lines)


def format_grouped(results: list[FileSearchResult], *, query: str = "") -> str:
	if not results:
		return ""

	lines: list[str] = [format_grouped_summary(match_count=len(results), query=query)]
	for index, result in enumerate(results):
		lines.append(format_grouped_result(result, query=query, separator=index > 0))
	return "\n".join(lines)


def format_flat_result(result: FileSearchResult) -> list[str]:
	path_text = result.path.as_posix()
	lines: list[str] = []
	if result.lines:
		for line_match in result.lines:
			lines.append(
				f"{path_text}:{line_match.location_kind}:{line_match.line_number}:"
				f"{format_score_percent(line_match.score)}:{line_match.text}"
			)
	elif "name" in result.breakdown and result.breakdown["name"] > 0.0:
		lines.append(f"{path_text}:name:0:{format_score_percent(result.score)}:{result.path.name}")
	return lines


def format_flat(results: list[FileSearchResult]) -> str:
	lines: list[str] = []
	for result in results:
		lines.extend(format_flat_result(result))
	return "\n".join(lines)


def format_json_result(result: FileSearchResult, *, query: str = "") -> dict[str, object]:
	return {
		"path": result.path.as_posix(),
		"score": result.score,
		"breakdown": result.breakdown,
		"lines": [
			{
				"line_number": line_match.line_number,
				"location_kind": line_match.location_kind,
				"location_label": format_location_label(line_match.location_kind, line_match.line_number),
				"preview": format_match_preview(line_match.text, query),
				"text": line_match.text,
				"score": line_match.score,
			}
			for line_match in result.lines
		],
	}


def format_json(results: list[FileSearchResult], *, query: str = "") -> str:
	payload = [format_json_result(result, query=query) for result in results]
	return json.dumps(payload, indent=2)


def format_no_matches_message(query: str, path: Path | str) -> str:
	return f'No matches for "{query}" in {Path(path).expanduser()}'


def format_skipped_file_warning(skipped: SkippedFile, max_file_size: int | None) -> str:
	if skipped.reason == "ocr_too_large":
		from srxy.ocr_text import ocr_max_file_size

		limit = ocr_max_file_size()
		limit_label = f"{limit:,}" if limit is not None else "limit"
		return (
			f"warning: skipped OCR in {skipped.path.as_posix()} "
			f"({skipped.size_bytes:,} bytes > --max-ocr-file-size {limit_label})\n"
			f"  hint: increase --max-ocr-file-size or unset SRXY_OCR_MAX_FILE_SIZE"
		)
	if skipped.reason == "transcribe_too_large":
		from srxy.transcribe_text import transcribe_max_file_size

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
		self._activity_message: str | None = None
		self._spinner_index = 0
		self._spinner_stop = threading.Event()
		self._spinner_thread: threading.Thread | None = None
		self._match_flash = False

	def flash_match(self):
		self._match_flash = True
		if self._tty and self._searching() and self._activity_message is None:
			self.refresh()

	def _stop_spinner(self):
		if self._spinner_thread is None:
			return
		self._spinner_stop.set()
		self._spinner_thread.join(timeout=1.0)
		self._spinner_thread = None
		self._spinner_stop.clear()

	def set_activity(self, message: str | None):
		if message == self._activity_message:
			return
		self._match_flash = False
		self._stop_spinner()
		self._activity_message = message
		if message is None:
			if self._tty and self._searching():
				self.refresh()
			return
		if not self._tty:
			return
		self._spinner_thread = threading.Thread(target=self._run_spinner, daemon=True)
		self._spinner_thread.start()

	def _run_spinner(self):
		while not self._spinner_stop.is_set():
			frame = _SPINNER_FRAMES[self._spinner_index % len(_SPINNER_FRAMES)]
			self._spinner_index += 1
			columns, _ = _terminal_size(self._stream)
			message = f"{frame} {self._activity_message}"
			if len(message) > columns:
				message = message[: max(0, columns - 3)] + "..."
			self._stream.write(f"\r\x1b[2K{message}")
			self._stream.flush()
			if self._spinner_stop.wait(0.1):
				break

	def _format_message(self, *, width: int) -> str:
		ratio = self._current / self._total if self._total else 0.0
		filled = int(_PROGRESS_BAR_WIDTH * ratio)
		bar = "█" * filled + "░" * (_PROGRESS_BAR_WIDTH - filled)
		message = f"[{bar}] {self._current}/{self._total} files"
		if self._match_flash:
			message += " · match found"
		if len(message) > width:
			return message[: max(0, width - 3)] + "..."
		return message

	def _searching(self) -> bool:
		return self._total > 0 and self._current < self._total

	def clear(self):
		self._stop_spinner()
		if not self._tty:
			return
		self._stream.write("\r\x1b[2K")
		self._stream.flush()

	def refresh(self):
		if not self._tty or self._total <= 0:
			return
		columns, _ = _terminal_size(self._stream)
		message = self._format_message(width=columns)
		self._stream.write(f"\r\x1b[2K{message}")
		self._stream.flush()

	def update(self, current: int, total: int):
		self._match_flash = False
		self._current = current
		self._total = total
		if total <= 0:
			return

		if not self._tty:
			if current == total or current == 1 or current % max(1, total // 20) == 0:
				print(self._format_message(width=_PROGRESS_BAR_WIDTH + 24), file=self._stream, flush=True)
			return

		self.refresh()

	def write_above(self, text: str, stdout: TextIO):
		if not self._tty:
			print(text, file=stdout, flush=True)
			return
		self.clear()
		print(text, file=stdout, flush=True)
		if self._searching():
			self.refresh()

	def finish(self):
		self._activity_message = None
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
			print(text, file=self._stdout, flush=True)
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
	parser.add_argument("query", nargs="?", default=None, help="Search string")
	parser.add_argument("path", nargs="?", default=".", help="File or directory to search (default: .)")
	parser.add_argument("--threshold", type=float, default=0.35, help="Minimum match score (default: 0.35)")
	parser.add_argument(
		"--max-file-size",
		type=int,
		default=None,
		help="Skip text and document content search in files larger than this many bytes (default: unlimited)",
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
	parser.add_argument("--ocr", action="store_true", help="Enable OCR for images and PDF embedded images (SRXY_OCR=1)")
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
	mode_group.add_argument("--names-only", action="store_true", help="Search file names only")
	mode_group.add_argument("--content-only", action="store_true", help="Search file contents only")

	search_group = parser.add_mutually_exclusive_group()
	search_group.add_argument(
		"--names", action="store_true", dest="search_names", default=None, help="Search file names"
	)
	search_group.add_argument("--no-names", action="store_false", dest="search_names", help="Skip file name search")

	content_group = parser.add_mutually_exclusive_group()
	content_group.add_argument(
		"--content", action="store_true", dest="search_contents", default=None, help="Search contents"
	)
	content_group.add_argument("--no-content", action="store_false", dest="search_contents", help="Skip content search")

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
		"--no-tui",
		action="store_true",
		help="Force plain-text output even on an interactive terminal",
	)

	return parser


def resolve_search_modes(args: argparse.Namespace) -> tuple[bool, bool]:
	if args.names_only:
		return True, False
	if args.content_only:
		return False, True

	search_names = True if args.search_names is None else args.search_names
	search_contents = True if args.search_contents is None else args.search_contents
	return search_names, search_contents


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
	if args.no_tui:
		return False
	if args.json or args.format == "flat" or args.output is not None:
		return False
	if os.environ.get("CI", "").strip().lower() in _TRUTHY_ENV_VALUES:
		return False
	return sys.stdout.isatty() and sys.stderr.isatty()


def apply_args_to_env(args: argparse.Namespace):
	if args.semantic_all:
		os.environ["SRXY_SEMANTIC"] = "1"
		os.environ["SRXY_OCR"] = "1"
		os.environ["SRXY_SEMANTIC_IMAGE"] = "1"
		os.environ["SRXY_TRANSCRIBE"] = "1"
	if args.semantic:
		os.environ["SRXY_SEMANTIC"] = "1"
	if args.semantic_image:
		os.environ["SRXY_SEMANTIC_IMAGE"] = "1"
	if args.ocr:
		os.environ["SRXY_OCR"] = "1"
	if args.max_ocr_file_size is not None:
		os.environ["SRXY_OCR_MAX_FILE_SIZE"] = str(args.max_ocr_file_size)
	if args.transcribe:
		os.environ["SRXY_TRANSCRIBE"] = "1"
	if args.max_transcribe_file_size is not None:
		os.environ["SRXY_TRANSCRIBE_MAX_FILE_SIZE"] = str(args.max_transcribe_file_size)
	if args.transcribe_model is not None:
		os.environ["SRXY_TRANSCRIBE_MODEL"] = args.transcribe_model
	os.environ["SRXY_TRANSCRIBE_THRESHOLD"] = str(args.transcribe_threshold)


def sync_options_to_args(
	args: argparse.Namespace,
	*,
	search_names: bool,
	search_contents: bool,
	semantic: bool,
	semantic_image: bool,
	ocr: bool,
	transcribe: bool,
	include_hidden: bool,
	include_noise: bool,
):
	args.names_only = search_names and not search_contents
	args.content_only = search_contents and not search_names
	args.search_names = search_names
	args.search_contents = search_contents
	args.semantic = semantic
	args.semantic_image = semantic_image
	args.semantic_all = False
	args.ocr = ocr
	args.transcribe = transcribe
	args.include_hidden = include_hidden
	args.include_noise = include_noise


def run_preflight(
	args: argparse.Namespace,
	*,
	interactive: bool,
	prompt_yes: Callable[[str], bool] | None = None,
) -> str | None:
	apply_args_to_env(args)

	if ocr_requested(None) and not is_ocr_available():
		return ocr_unavailable_message()

	if transcribe_requested(None) and not transcribe_deps_installed():
		return transcribe_unavailable_message()
	if transcribe_requested(None) and not ffmpeg_available():
		return ffmpeg_unavailable_message()
	if transcribe_requested(None) and not ensure_transcribe_model(
		interactive=interactive,
		prompt_yes=prompt_yes,
	):
		return transcribe_model_missing_message()

	if semantic_env_enabled():
		if not sentence_transformers_installed():
			return "Semantic matching requires the optional dependency: pip install 'srxy[semantic]'"
		if not ensure_semantic_text_model(interactive=interactive, prompt_yes=prompt_yes):
			return semantic_text_model_missing_message()

	if semantic_image_requested(None):
		if not is_semantic_image_available():
			return semantic_image_unavailable_message()
		if not ensure_semantic_image_model(interactive=interactive, prompt_yes=prompt_yes):
			return semantic_image_model_missing_message()

	return None


def execute_search(
	args: argparse.Namespace,
	*,
	skipped_files: list[SkippedFile] | None = None,
	on_progress: Callable[[int, int], None] | None = None,
	on_activity: Callable[[str | None], None] | None = None,
	on_result: Callable[[FileSearchResult], None] | None = None,
) -> tuple[list[FileSearchResult], list[SkippedFile]]:
	search_names, search_contents = resolve_search_modes(args)
	effective_skipped = skipped_files if skipped_files is not None else []
	query = args.query or ""
	results = magic_file_search(
		args.path,
		query,
		search_names=search_names,
		search_contents=search_contents,
		threshold=args.threshold,
		semantic_image_threshold=args.semantic_image_threshold,
		transcribe_threshold=args.transcribe_threshold,
		limit=args.limit,
		max_file_size=args.max_file_size,
		max_matches=args.max_matches,
		skip_hidden_folders=not args.include_hidden,
		skip_noise_folders=not args.include_noise,
		skipped_files=effective_skipped
		if search_contents or ocr_requested(None) or transcribe_requested(None)
		else None,
		ocr=ocr_requested(None),
		transcribe=transcribe_requested(None),
		on_progress=on_progress,
		on_activity=on_activity,
		on_result=on_result,
	)
	return results, effective_skipped


def run_plain(args: argparse.Namespace) -> int:
	if args.query is None:
		print("error: the following arguments are required: query", file=sys.stderr)
		return 2

	error = run_preflight(args, interactive=sys.stdin.isatty())
	if error is not None:
		print(error, file=sys.stderr)
		return 2

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

	def on_activity(message: str | None):
		if progress is not None:
			progress.set_activity(message)

	def on_result(_result: FileSearchResult):
		if progress is not None:
			progress.flash_match()

	try:
		results, skipped_files = execute_search(
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


def main(argv: list[str] | None = None) -> int:
	parser = build_parser()
	args = parser.parse_args(argv)

	if should_use_tui(args):
		from srxy.tui import run_tui

		auto_start = args.query is not None and bool(args.query.strip())
		return run_tui(args, auto_start=auto_start)

	return run_plain(args)


if __name__ == "__main__":
	sys.exit(main())
