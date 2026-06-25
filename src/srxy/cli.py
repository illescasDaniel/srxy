from __future__ import annotations

import argparse
import json
import os
import sys

from srxy.file_search import magic_file_search, suggest_max_file_size
from srxy.models import FileSearchResult, SkippedFile
from srxy.utils import format_match_preview


_LOCATION_LABELS = {
	"line": "line",
	"page": "page",
	"paragraph": "paragraph",
	"row": "row",
	"slide": "slide",
}


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


def format_grouped(results: list[FileSearchResult], *, query: str = "") -> str:
	if not results:
		return ""

	lines: list[str] = []
	match_count = len(results)
	header = f"{match_count} file matched" if match_count == 1 else f"{match_count} files matched"
	if query:
		header += f' for "{query}"'
	lines.append(header)

	for index, result in enumerate(results):
		if index > 0:
			lines.append("")
		path_text = result.path.as_posix()
		label_text = _match_labels(result)
		lines.append(f"── {path_text} ──")
		lines.append(f"   score {result.score:.2f}  ·  matched: {label_text}")
		for line_match in result.lines:
			location = format_location_label(line_match.location_kind, line_match.line_number)
			preview = format_match_preview(line_match.text, query)
			lines.append(f"   {location}  ·  score {line_match.score:.2f}")
			lines.append(f"   │ {preview}")

	return "\n".join(lines)


def format_flat(results: list[FileSearchResult]) -> str:
	lines: list[str] = []
	for result in results:
		path_text = result.path.as_posix()
		if result.lines:
			for line_match in result.lines:
				lines.append(
					f"{path_text}:{line_match.location_kind}:{line_match.line_number}:"
					f"{line_match.score:.2f}:{line_match.text}"
				)
		elif "name" in result.breakdown and result.breakdown["name"] > 0.0:
			lines.append(f"{path_text}:name:0:{result.score:.2f}:{result.path.name}")
	return "\n".join(lines)


def format_json(results: list[FileSearchResult], *, query: str = "") -> str:
	payload = [
		{
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
		for result in results
	]
	return json.dumps(payload, indent=2)


def format_skipped_file_warnings(skipped_files: list[SkippedFile], max_file_size: int) -> str:
	if not skipped_files:
		return ""

	lines: list[str] = []
	for skipped in skipped_files:
		suggested = suggest_max_file_size(skipped.size_bytes)
		lines.append(
			f"warning: skipped content search in {skipped.path.as_posix()} "
			f"({skipped.size_bytes:,} bytes > --max-file-size {max_file_size:,})"
		)
		lines.append(f"  hint: rerun with --max-file-size {suggested}")
	return "\n".join(lines)


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
		)
	except FileNotFoundError as error:
		print(error, file=sys.stderr)
		return 2
	except ValueError as error:
		print(error, file=sys.stderr)
		return 2

	warnings = format_skipped_file_warnings(skipped_files, args.max_file_size)
	if warnings:
		print(warnings, file=sys.stderr)

	output = render_results(results, as_json=args.json, output_format=args.format, query=args.query)
	if output:
		print(output)

	return 0 if results else 1


if __name__ == "__main__":
	sys.exit(main())
