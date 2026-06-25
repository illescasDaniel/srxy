from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import IO, TextIO

from srxy.file_search import magic_file_search, suggest_max_file_size
from srxy.models import FileSearchResult, LineMatch, SkippedFile
from srxy.utils import format_match_preview


_LOCATION_LABELS = {
	"line": "line",
	"page": "page",
	"paragraph": "paragraph",
	"row": "row",
	"slide": "slide",
}

_PROGRESS_BAR_WIDTH = 40


def format_location_label(kind: str, number: int) -> str:
	label = _LOCATION_LABELS.get(kind, kind)
	return f"{label} {number}"


def _match_labels(result: FileSearchResult) -> str:
	labels: list[str] = []
	if "name" in result.breakdown and result.breakdown["name"] > 0.0:
		labels.append("name")
	if result.lines or result.breakdown.get("content", 0.0) > 0.0:
		labels.append("content")
	return ", ".join(labels) if labels else "match"


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


def _format_locations(kind: str, numbers: list[int]) -> str:
	label = _LOCATION_LABELS.get(kind, kind)
	sorted_numbers = sorted(numbers)
	if len(sorted_numbers) == 1:
		return f"{label} {sorted_numbers[0]}"
	return f"{label}s {_format_number_ranges(sorted_numbers)}"


def _iter_grouped_line_displays(
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
	label_text = _match_labels(result)
	lines.append(f"── {path_text} ──")
	lines.append(f"   score {result.score:.2f}  ·  matched: {label_text}")
	for location, preview, score in _iter_grouped_line_displays(result.lines, query=query):
		lines.append(f"   {location}  ·  score {score:.2f}")
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
				f"{line_match.score:.2f}:{line_match.text}"
			)
	elif "name" in result.breakdown and result.breakdown["name"] > 0.0:
		lines.append(f"{path_text}:name:0:{result.score:.2f}:{result.path.name}")
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


def format_skipped_file_warning(skipped: SkippedFile, max_file_size: int) -> str:
	suggested = suggest_max_file_size(skipped.size_bytes)
	return (
		f"warning: skipped content search in {skipped.path.as_posix()} "
		f"({skipped.size_bytes:,} bytes > --max-file-size {max_file_size:,})\n"
		f"  hint: rerun with --max-file-size {suggested}"
	)


def format_skipped_file_warnings(skipped_files: list[SkippedFile], max_file_size: int) -> str:
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

	def _format_message(self, *, width: int) -> str:
		ratio = self._current / self._total if self._total else 0.0
		filled = int(_PROGRESS_BAR_WIDTH * ratio)
		bar = "█" * filled + "░" * (_PROGRESS_BAR_WIDTH - filled)
		message = f"[{bar}] {self._current}/{self._total} files"
		if len(message) > width:
			return message[: max(0, width - 3)] + "..."
		return message

	def _searching(self) -> bool:
		return self._total > 0 and self._current < self._total

	def clear(self):
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
	parser.add_argument("query", help="Search string")
	parser.add_argument("path", nargs="?", default=".", help="File or directory to search (default: .)")
	parser.add_argument("--threshold", type=float, default=0.25, help="Minimum match score (default: 0.25)")
	parser.add_argument(
		"--max-file-size",
		type=int,
		default=1_048_576,
		help="Skip content search in files larger than this many bytes (default: 1048576)",
	)
	parser.add_argument(
		"--max-line-matches",
		type=int,
		default=50,
		help="Maximum matching lines returned per file (default: 50)",
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


def main(argv: list[str] | None = None) -> int:
	parser = build_parser()
	args = parser.parse_args(argv)

	if args.semantic:
		os.environ["SRXY_SEMANTIC"] = "1"

	search_names, search_contents = resolve_search_modes(args)
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
			progress.update(current, total)

	def on_result(result: FileSearchResult):
		writer.write_result(result)

	try:
		results = magic_file_search(
			args.path,
			args.query,
			search_names=search_names,
			search_contents=search_contents,
			threshold=args.threshold,
			max_file_size=args.max_file_size,
			max_line_matches=args.max_line_matches,
			skip_hidden_folders=not args.include_hidden,
			skip_noise_folders=not args.include_noise,
			skipped_files=skipped_files if search_contents else None,
			on_progress=on_progress,
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

	for skipped in skipped_files:
		print(format_skipped_file_warning(skipped, args.max_file_size), file=sys.stderr)

	if progress is not None:
		progress.finish()

	writer.finalize()
	writer.close()

	return 0 if results else 1


if __name__ == "__main__":
	sys.exit(main())
