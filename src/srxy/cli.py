from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import IO, Callable, TextIO

from srxy.file_query import FileQ, FileQueryParseError, coerce_file_query, file_q_from_dict
from srxy.file_search import DEFAULT_MAX_FILE_SIZE, magic_file_search, suggest_max_file_size
from srxy.matchers.semantic import (
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
from srxy.progress import ActivityCallback, ActivityUpdate, format_activity_status
from srxy.semantic_image import (
	DEFAULT_SEMANTIC_IMAGE_THRESHOLD,
	is_semantic_image_available,
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
from srxy.utils import PreviewHighlight, format_match_preview


_LOCATION_LABELS = {
	"line": "line",
	"page": "page",
	"paragraph": "paragraph",
	"row": "row",
	"slide": "slide",
	"tag": "tag",
	"ocr": "ocr",
	"semantic_image": "image",
	"transcript": "transcript",
}

_PROGRESS_BAR_WIDTH = 40
_TASK_BAR_WIDTH = 24
_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})
_CONTENT_LOCATION_KINDS = frozenset({"line", "page", "paragraph", "row", "slide"})


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


def _line_match_threshold(
	location_kind: str,
	*,
	threshold: float,
	semantic_image_threshold: float,
	transcribe_threshold: float,
) -> float:
	if location_kind == "transcript":
		return transcribe_threshold
	if location_kind == "semantic_image":
		return semantic_image_threshold
	return threshold


def _line_counts_as_match(
	line: LineMatch,
	*,
	threshold: float,
	semantic_image_threshold: float,
	transcribe_threshold: float,
) -> bool:
	cutoff = _line_match_threshold(
		line.location_kind,
		threshold=threshold,
		semantic_image_threshold=semantic_image_threshold,
		transcribe_threshold=transcribe_threshold,
	)
	return line.score >= cutoff


def match_labels(
	result: FileSearchResult,
	*,
	threshold: float = 0.35,
	semantic_image_threshold: float = DEFAULT_SEMANTIC_IMAGE_THRESHOLD,
	transcribe_threshold: float = DEFAULT_TRANSCRIBE_THRESHOLD,
) -> str:
	labels: list[str] = []
	if _name_matched(result, threshold=threshold):
		labels.append("name")
	for line in result.lines:
		if not _line_counts_as_match(
			line,
			threshold=threshold,
			semantic_image_threshold=semantic_image_threshold,
			transcribe_threshold=transcribe_threshold,
		):
			continue
		if line.location_kind in _CONTENT_LOCATION_KINDS:
			if "content" not in labels:
				labels.append("content")
		elif line.location_kind == "ocr" and "ocr" not in labels:
			labels.append("ocr")
		elif line.location_kind == "transcript" and "transcript" not in labels:
			labels.append("transcript")
		elif line.location_kind == "tag" and "tag" not in labels:
			labels.append("tag")
		elif line.location_kind == "semantic_image" and "image semantic" not in labels:
			labels.append("image semantic")
	if not result.lines and _content_matched_from_terms(result, threshold=threshold):
		labels.append("content")
	semantic_image_score = result.breakdown.get("semantic_image", 0.0)
	if (
		semantic_image_score >= semantic_image_threshold
		and semantic_image_score >= result.score - 1e-9
		and "image semantic" not in labels
	):
		labels.append("image semantic")
	return ", ".join(labels) if labels else "match"


def _name_matched(result: FileSearchResult, *, threshold: float) -> bool:
	if result.term_surfaces:
		return any(scores.get("name", 0.0) >= threshold for scores in result.term_surfaces.values())
	return result.breakdown.get("name", 0.0) >= threshold


def _content_matched_from_terms(result: FileSearchResult, *, threshold: float) -> bool:
	if result.term_surfaces:
		return any(scores.get("content", 0.0) >= threshold for scores in result.term_surfaces.values())
	return result.breakdown.get("content", 0.0) >= threshold


def format_score_percent(score: float) -> str:
	return f"{round(score * 100)}%"


def format_grouped_summary(*, match_count: int, query: str = "") -> str:
	header = f"{match_count} file matched" if match_count == 1 else f"{match_count} files matched"
	if query:
		from srxy.file_query import format_query_for_display

		header += f' for "{format_query_for_display(query)}"'
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


def _format_match_location(kind: str, numbers: list[int], *, matched_term: str | None = None) -> str:
	location = _format_locations(kind, numbers)
	if matched_term:
		return f'{location} · "{matched_term}"'
	return location


def iter_grouped_line_displays(
	line_matches: list[LineMatch],
	*,
	query: str,
	highlight: PreviewHighlight = "guillemets",
) -> list[tuple[str, str, float, str]]:
	groups: dict[tuple[float, str, str], list[LineMatch]] = {}
	group_order: list[tuple[float, str, str]] = []
	for line_match in line_matches:
		line_highlight: PreviewHighlight = "none" if line_match.location_kind == "semantic_image" else highlight
		highlight_term = line_match.matched_term
		plain_preview = format_match_preview(
			line_match.text,
			query,
			highlight="none",
			highlight_term=highlight_term,
		)
		preview = format_match_preview(
			line_match.text,
			query,
			highlight=line_highlight,
			highlight_term=highlight_term,
		)
		key = (line_match.score, line_match.location_kind, plain_preview)
		if key not in groups:
			groups[key] = []
			group_order.append(key)
		groups[key].append(line_match)

	displays: list[tuple[str, str, float, str]] = []
	for score, kind, plain_preview in group_order:
		numbers = [line_match.line_number for line_match in groups[(score, kind, plain_preview)]]
		first = groups[(score, kind, plain_preview)][0]
		line_highlight = "none" if first.location_kind == "semantic_image" else highlight
		preview = format_match_preview(
			first.text,
			query,
			highlight=line_highlight,
			highlight_term=first.matched_term,
		)
		displays.append(
			(
				_format_match_location(kind, numbers, matched_term=first.matched_term),
				preview,
				score,
				plain_preview,
			)
		)
	return displays


def format_grouped_result(result: FileSearchResult, *, query: str = "", separator: bool = False) -> str:
	lines: list[str] = []
	if separator:
		lines.append("")
	path_text = result.path.as_posix()
	label_text = match_labels(result)
	lines.append(f"── {path_text} ──")
	lines.append(f"   match {format_score_percent(result.score)}  ·  matched: {label_text}")
	for location, preview, score, _plain in iter_grouped_line_displays(result.lines, query=query):
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


def format_flat_result(result: FileSearchResult, *, threshold: float = 0.35) -> list[str]:
	path_text = result.path.as_posix()
	lines: list[str] = []
	if result.lines:
		for line_match in result.lines:
			lines.append(
				f"{path_text}:{line_match.location_kind}:{line_match.line_number}:"
				f"{format_score_percent(line_match.score)}:{line_match.text}"
			)
	elif _name_matched(result, threshold=threshold):
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
	from srxy.file_query import format_query_for_display

	return f'No matches for "{format_query_for_display(query)}" in {Path(path).expanduser()}'


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
	parser.add_argument(
		"--version",
		action="version",
		version=f"%(prog)s {package_version()}",
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
		"--include-archives",
		action="store_true",
		help="Search inside compressed archives (.zip, .tar, .tar.gz, .gz) (default: skip)",
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
	else:
		_set_mode_env("SRXY_SEMANTIC", args.semantic)
		_set_mode_env("SRXY_OCR", args.ocr)
		_set_mode_env("SRXY_SEMANTIC_IMAGE", args.semantic_image)
		_set_mode_env("SRXY_TRANSCRIBE", args.transcribe)
	if args.max_ocr_file_size is not None:
		os.environ["SRXY_OCR_MAX_FILE_SIZE"] = str(args.max_ocr_file_size)
	if args.max_transcribe_file_size is not None:
		os.environ["SRXY_TRANSCRIBE_MAX_FILE_SIZE"] = str(args.max_transcribe_file_size)
	if args.transcribe_model is not None:
		os.environ["SRXY_TRANSCRIBE_MODEL"] = args.transcribe_model
	os.environ["SRXY_TRANSCRIBE_THRESHOLD"] = str(args.transcribe_threshold)


def _set_mode_env(name: str, enabled: bool):
	if enabled:
		os.environ[name] = "1"
	else:
		os.environ.pop(name, None)


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
	semantic: bool,
	semantic_image: bool,
	ocr: bool,
	transcribe: bool,
	include_hidden: bool,
	include_noise: bool,
	include_archives: bool,
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
	args.include_archives = include_archives


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
			return "Semantic matching requires the optional dependency: pip install 'srxy[semantic]'"
		if not ensure_semantic_text_model(interactive=interactive, prompt_yes=prompt_yes):
			return semantic_text_model_missing_message()

	if _args_want_semantic_image(args):
		if not is_semantic_image_available():
			return semantic_image_unavailable_message()
		if not ensure_semantic_image_model(interactive=interactive, prompt_yes=prompt_yes):
			return semantic_image_model_missing_message()

	return None


def resolve_file_query(args: argparse.Namespace) -> FileQ:
	if getattr(args, "query_expr", None) is not None:
		value = args.query_expr
		if isinstance(value, FileQ):
			return value
		if isinstance(value, dict):
			return file_q_from_dict(value)
	query = args.query or ""
	return coerce_file_query(query)


def execute_search(
	args: argparse.Namespace,
	*,
	skipped_files: list[SkippedFile] | None = None,
	on_progress: Callable[[int, int], None] | None = None,
	on_activity: ActivityCallback | None = None,
	on_result: Callable[[FileSearchResult], None] | None = None,
) -> tuple[list[FileSearchResult], list[SkippedFile]]:
	search_names, search_contents = resolve_search_modes(args)
	effective_skipped = skipped_files if skipped_files is not None else []
	query_expr = resolve_file_query(args)
	results = magic_file_search(
		args.path,
		query_expr,
		search_names=search_names,
		search_contents=search_contents,
		threshold=args.threshold,
		semantic_image_threshold=args.semantic_image_threshold,
		transcribe_threshold=args.transcribe_threshold,
		limit=args.limit,
		max_file_size=normalize_max_file_size(args.max_file_size),
		max_matches=args.max_matches,
		skip_hidden_folders=not args.include_hidden,
		skip_noise_folders=not args.include_noise,
		include_archives=bool(getattr(args, "include_archives", False)),
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

	try:
		resolve_file_query(args)
	except FileQueryParseError as error:
		print(f"error: invalid query: {error}", file=sys.stderr)
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

	def on_activity(update: ActivityUpdate | None):
		if progress is not None:
			progress.set_activity(update)

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
