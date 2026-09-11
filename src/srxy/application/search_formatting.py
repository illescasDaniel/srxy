"""Shared result formatting helpers for CLI, TUI, and GUI."""

from __future__ import annotations

from srxy.application.search_defaults import (
	DEFAULT_SEMANTIC_IMAGE_THRESHOLD,
	DEFAULT_TRANSCRIBE_THRESHOLD,
)
from srxy.application.utils import PreviewHighlight, format_match_preview
from srxy.domain.models import FileSearchResult, LineMatch


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

_CONTENT_LOCATION_KINDS = frozenset({"line", "page", "paragraph", "row", "slide"})


def format_transcript_timestamp(seconds: int) -> str:
	total = max(0, int(seconds))
	minutes, secs = divmod(total, 60)
	return f"{minutes:02d}:{secs:02d}"


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


def _name_matched(result: FileSearchResult, *, threshold: float) -> bool:
	if result.term_surfaces:
		return any(scores.get("name", 0.0) >= threshold for scores in result.term_surfaces.values())
	return result.breakdown.get("name", 0.0) >= threshold


def _content_matched_from_terms(result: FileSearchResult, *, threshold: float) -> bool:
	if result.term_surfaces:
		return any(scores.get("content", 0.0) >= threshold for scores in result.term_surfaces.values())
	return result.breakdown.get("content", 0.0) >= threshold


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


def format_score_percent(score: float) -> str:
	return f"{round(score * 100)}%"


def format_grouped_summary(*, match_count: int, query: str = "") -> str:
	header = f"{match_count} file matched" if match_count == 1 else f"{match_count} files matched"
	if query:
		from srxy.domain.file_query import format_query_for_display

		header += f' for "{format_query_for_display(query)}"'
	return header


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
) -> list[tuple[str, str, float, str, int]]:
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

	displays: list[tuple[str, str, float, str, int]] = []
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
		first_number = min(numbers) if kind == "line" else 0
		displays.append(
			(
				_format_match_location(kind, numbers, matched_term=first.matched_term),
				preview,
				score,
				plain_preview,
				first_number,
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
	for location, preview, score, _plain, _line in iter_grouped_line_displays(result.lines, query=query):
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


__all__ = [
	"format_flat",
	"format_flat_result",
	"format_grouped",
	"format_grouped_result",
	"format_grouped_summary",
	"format_location_label",
	"format_score_percent",
	"iter_grouped_line_displays",
	"match_labels",
]
