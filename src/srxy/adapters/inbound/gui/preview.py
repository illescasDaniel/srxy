"""Lightweight HTML preview formatting for the GUI file pane."""

from __future__ import annotations

import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path


__all__ = [
	"PREVIEW_MAX_BYTES",
	"PREVIEW_MAX_LINES",
	"PreviewPalette",
	"PREVIEW_PALETTES",
	"format_preview_html",
	"format_preview_message",
	"format_preview_plain",
	"prepare_preview_text",
	"preview_font_family",
]

PREVIEW_MAX_BYTES = 64 * 1024
PREVIEW_MAX_LINES = 2000


def preview_font_family() -> str:
	"""Return the monospace face used in preview RichText HTML (matches QML)."""
	# Bare CSS "monospace" maps to TypeWriter bitmap fonts on Windows (8514oem /
	# Fixedsys); DirectWrite then fails and Qt spam-logs OpenType fallbacks.
	if sys.platform == "win32":
		return "Consolas"
	if sys.platform == "darwin":
		return "Menlo"
	return "monospace"


@dataclass(frozen=True)
class PreviewPalette:
	"""Colors used when rendering the file preview for a light/dark theme."""

	gutter: str
	keyword: str
	string: str
	comment: str
	heading: str
	footer: str
	hit_background: str
	find_background: str
	find_current_background: str


PREVIEW_PALETTES: dict[str, PreviewPalette] = {
	"light": PreviewPalette(
		gutter="#888888",
		keyword="#0550ae",
		string="#0a3069",
		comment="#6a737d",
		heading="#0550ae",
		footer="#6a737d",
		hit_background="#fff8c5",
		find_background="#ffe58f",
		find_current_background="#ffc107",
	),
	"dark": PreviewPalette(
		gutter="#6e7681",
		keyword="#ff7b72",
		string="#a5d6ff",
		comment="#8b949e",
		heading="#79c0ff",
		footer="#8b949e",
		hit_background="#3d3400",
		find_background="#574700",
		find_current_background="#7a5c00",
	),
}

_PY_KEYWORDS = frozenset(
	{
		"False",
		"None",
		"True",
		"and",
		"as",
		"assert",
		"async",
		"await",
		"break",
		"class",
		"continue",
		"def",
		"del",
		"elif",
		"else",
		"except",
		"finally",
		"for",
		"from",
		"global",
		"if",
		"import",
		"in",
		"is",
		"lambda",
		"nonlocal",
		"not",
		"or",
		"pass",
		"raise",
		"return",
		"try",
		"while",
		"with",
		"yield",
	}
)
_JS_KEYWORDS = frozenset(
	{
		"async",
		"await",
		"break",
		"case",
		"catch",
		"class",
		"const",
		"continue",
		"default",
		"else",
		"export",
		"extends",
		"false",
		"finally",
		"for",
		"function",
		"if",
		"import",
		"in",
		"let",
		"new",
		"null",
		"of",
		"return",
		"switch",
		"this",
		"throw",
		"true",
		"try",
		"typeof",
		"var",
		"void",
		"while",
		"yield",
	}
)
_SH_KEYWORDS = frozenset(
	{
		"case",
		"do",
		"done",
		"elif",
		"else",
		"esac",
		"fi",
		"for",
		"function",
		"if",
		"in",
		"select",
		"then",
		"until",
		"while",
	}
)
_QML_KEYWORDS = frozenset(
	{
		"alias",
		"default",
		"enum",
		"false",
		"id",
		"import",
		"null",
		"property",
		"readonly",
		"required",
		"signal",
		"true",
	}
)

_TOKEN_RE = re.compile(
	r"""
	(?P<comment>\#[^\n]*|//[^\n]*|/\*.*?\*/)|
	(?P<string>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)|
	(?P<word>\b[\w']+\b)|
	(?P<other>.)
	""",
	re.VERBOSE | re.DOTALL,
)

# ``(start, end, kind)`` segments — ``kind`` is one of "comment", "string",
# "keyword", "heading", or None (plain).  Offsets refer to the raw line.
Segment = tuple[int, int, str | None]
Overlay = tuple[int, int, str]  # (start, end, background) — non-overlapping


def _palette(theme: str) -> PreviewPalette:
	return PREVIEW_PALETTES.get(theme, PREVIEW_PALETTES["light"])


def _default_overlay(value: dict[int, list[tuple[int, int]]] | None) -> dict[int, list[tuple[int, int]]]:
	return value or {}


def prepare_preview_text(text: str) -> tuple[str, bool]:
	"""Cap preview payload by bytes and line count; return text and whether it was truncated."""
	truncated = False
	encoded = text.encode("utf-8")
	if len(encoded) > PREVIEW_MAX_BYTES:
		text = encoded[:PREVIEW_MAX_BYTES].decode("utf-8", errors="ignore")
		truncated = True
	lines = text.splitlines()
	if len(lines) > PREVIEW_MAX_LINES:
		lines = lines[:PREVIEW_MAX_LINES]
		text = "\n".join(lines)
		truncated = True
	return text, truncated


def format_preview_message(message: str) -> str:
	"""Escape a non-code status line for RichText preview."""
	return f'<span style="font-family:{preview_font_family()}">{html.escape(message)}</span>'


def format_preview_truncated_footer(message: str, *, theme: str = "light") -> str:
	"""Append a muted footer when preview content was capped."""
	body = html.escape(message)
	family = preview_font_family()
	return f'<div style="font-family:{family}; margin-top:8px; color:{_palette(theme).footer}">{body}</div>'


def format_preview_plain(
	path: Path | str,
	text: str,
	*,
	theme: str = "light",
	hit_spans: dict[int, list[tuple[int, int]]] | None = None,
	find_spans: dict[int, list[tuple[int, int]]] | None = None,
	current_spans: dict[int, list[tuple[int, int]]] | None = None,
) -> str:
	"""Return HTML with line numbers but no syntax highlighting (overlays still apply)."""
	lines = text.splitlines() or [""]
	return _format_lines(
		path, lines, plain=True, theme=theme, hit_spans=hit_spans, find_spans=find_spans, current_spans=current_spans
	)


def format_preview_html(
	path: Path | str,
	text: str,
	*,
	theme: str = "light",
	hit_spans: dict[int, list[tuple[int, int]]] | None = None,
	find_spans: dict[int, list[tuple[int, int]]] | None = None,
	current_spans: dict[int, list[tuple[int, int]]] | None = None,
) -> str:
	"""Return HTML with line numbers and basic syntax colors for ``text``."""
	text, _truncated = prepare_preview_text(text)
	lines = text.splitlines() or [""]
	return _format_lines(
		path, lines, plain=False, theme=theme, hit_spans=hit_spans, find_spans=find_spans, current_spans=current_spans
	)


def format_preview_for_file(
	path: Path | str,
	text: str,
	*,
	truncated: bool = False,
	truncated_footer: str = "",
	theme: str = "light",
	hit_spans: dict[int, list[tuple[int, int]]] | None = None,
	find_spans: dict[int, list[tuple[int, int]]] | None = None,
	current_spans: dict[int, list[tuple[int, int]]] | None = None,
) -> str:
	"""Format capped preview text with line numbers and syntax colors."""
	text, was_truncated = prepare_preview_text(text)
	truncated = truncated or was_truncated
	lines = text.splitlines() or [""]
	body = _format_lines(
		path,
		lines,
		plain=False,
		theme=theme,
		hit_spans=hit_spans,
		find_spans=find_spans,
		current_spans=current_spans,
	)
	if truncated and truncated_footer:
		body += format_preview_truncated_footer(truncated_footer, theme=theme)
	return body


def _format_lines(
	path: Path | str,
	lines: list[str],
	*,
	plain: bool,
	theme: str,
	hit_spans: dict[int, list[tuple[int, int]]] | None,
	find_spans: dict[int, list[tuple[int, int]]] | None,
	current_spans: dict[int, list[tuple[int, int]]] | None,
) -> str:
	palette = _palette(theme)
	hits = _default_overlay(hit_spans)
	finds = _default_overlay(find_spans)
	currents = _default_overlay(current_spans)
	suffix = Path(path).suffix.lower()
	width = max(3, len(str(len(lines))))
	parts = [
		f'<div style="font-family:{preview_font_family()}; white-space:pre-wrap;">',
	]
	for number, line in enumerate(lines, start=1):
		gutter = html.escape(f"{number:>{width}}")
		if plain:
			body = _render_line(
				line,
				[(0, len(line), None)],
				palette,
				hits.get(number, []),
				finds.get(number, []),
				currents.get(number, []),
			)
		else:
			body = _render_line(
				line,
				_segments_for_line(line, suffix),
				palette,
				hits.get(number, []),
				finds.get(number, []),
				currents.get(number, []),
			)
		parts.append(f'<span style="color:{palette.gutter}">{gutter}</span>  {body}<br/>')
	parts.append("</div>")
	return "".join(parts)


def _segments_for_line(line: str, suffix: str) -> list[Segment]:
	if suffix in {".md", ".markdown"}:
		return _markdown_segments(line)
	if suffix == ".json":
		return _json_segments(line)
	keywords = _keywords_for_suffix(suffix)
	if keywords is None:
		return [(0, len(line), None)]
	return _code_segments(line, keywords)


def _keywords_for_suffix(suffix: str) -> frozenset[str] | None:
	if suffix == ".py":
		return _PY_KEYWORDS
	if suffix in {".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs"}:
		return _JS_KEYWORDS
	if suffix in {".sh", ".bash"}:
		return _SH_KEYWORDS
	if suffix == ".qml":
		return _QML_KEYWORDS
	return None


def _code_segments(line: str, keywords: frozenset[str]) -> list[Segment]:
	# Line comments only for # and // (block comments rare in single-line pass).
	if line.lstrip().startswith("#") or line.lstrip().startswith("//"):
		return [(0, len(line), "comment")]
	segments: list[Segment] = []
	for match in _TOKEN_RE.finditer(line):
		kind = match.lastgroup
		value = match.group()
		start, end = match.span()
		if kind == "comment":
			segments.append((start, end, "comment"))
		elif kind == "string":
			segments.append((start, end, "string"))
		elif kind == "word" and value in keywords:
			segments.append((start, end, "keyword"))
		else:
			segments.append((start, end, None))
	return segments


def _markdown_segments(line: str) -> list[Segment]:
	stripped = line.lstrip()
	if stripped.startswith("#"):
		return [(0, len(line), "heading")]
	if stripped.startswith("```"):
		return [(0, len(line), "comment")]
	return [(0, len(line), None)]


def _json_segments(line: str) -> list[Segment]:
	segments: list[Segment] = []
	for match in _TOKEN_RE.finditer(line):
		kind = match.lastgroup
		value = match.group()
		start, end = match.span()
		if kind == "string":
			segments.append((start, end, "string"))
		elif kind == "word" and value in {"true", "false", "null"}:
			segments.append((start, end, "keyword"))
		else:
			segments.append((start, end, None))
	return segments


def _color_escape(kind: str | None, text: str, palette: PreviewPalette) -> str:
	if kind is None or not text:
		return html.escape(text)
	color = {
		"comment": palette.comment,
		"string": palette.string,
		"keyword": palette.keyword,
		"heading": palette.heading,
	}.get(kind)
	if color is None:
		return html.escape(text)
	return f'<span style="color:{color}">{html.escape(text)}</span>'


def _render_line(
	line: str,
	segments: list[Segment],
	palette: PreviewPalette,
	hits: list[tuple[int, int]],
	finds: list[tuple[int, int]],
	currents: list[tuple[int, int]],
) -> str:
	overlays = _merge_overlays(hits, finds, currents, palette)
	out: list[str] = []
	overlay_index = 0
	for start, end, kind in segments:
		while overlay_index < len(overlays) and overlays[overlay_index][1] <= start:
			overlay_index += 1
		position = start
		index = overlay_index
		while index < len(overlays) and overlays[index][0] < end:
			overlay_start, overlay_end, background = overlays[index]
			if overlay_end <= position:
				index += 1
				continue
			cut_start = max(overlay_start, position)
			cut_end = min(overlay_end, end)
			if cut_start > position:
				out.append(_color_escape(kind, line[position:cut_start], palette))
			out.append(
				f'<span style="background-color:{background}">{_color_escape(kind, line[cut_start:cut_end], palette)}</span>'
			)
			position = cut_end
			index += 1
		if position < end:
			out.append(_color_escape(kind, line[position:end], palette))
	return "".join(out)


def _merge_overlays(
	hits: list[tuple[int, int]],
	finds: list[tuple[int, int]],
	currents: list[tuple[int, int]],
	palette: PreviewPalette,
) -> list[Overlay]:
	"""Merge hit/find/current ranges into non-overlapping background spans.

	Precedence: current > find > hit.
	"""
	points: set[int] = set()
	for start, end in (*hits, *finds, *currents):
		if start < end:
			points.add(start)
			points.add(end)
	ordered = sorted(points)
	overlays: list[Overlay] = []
	for index in range(len(ordered) - 1):
		start, end = ordered[index], ordered[index + 1]
		if start == end:
			continue
		if _covers(currents, start, end):
			background = palette.find_current_background
		elif _covers(finds, start, end):
			background = palette.find_background
		elif _covers(hits, start, end):
			background = palette.hit_background
		else:
			continue
		if overlays and overlays[-1][1] == start and overlays[-1][2] == background:
			overlays[-1] = (overlays[-1][0], end, background)
		else:
			overlays.append((start, end, background))
	return overlays


def _covers(ranges: list[tuple[int, int]], start: int, end: int) -> bool:
	for range_start, range_end in ranges:
		if range_start <= start and range_end >= end:
			return True
	return False
