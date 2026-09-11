"""Preview text helpers for the GUI file pane (Qt-free).

Document content is plain file text; colours come from ``PreviewHighlighter``
and line numbers live in a separate QML gutter.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass


__all__ = [
	"PREVIEW_MAX_BYTES",
	"PREVIEW_MAX_LINES",
	"PreviewPalette",
	"PREVIEW_PALETTES",
	"prepare_preview_text",
	"preview_font_family",
	"preview_gutter_text",
	"segments_for_line",
]

PREVIEW_MAX_BYTES = 64 * 1024
PREVIEW_MAX_LINES = 2000


def preview_font_family() -> str:
	"""Return the monospace face used in the preview pane (matches QML)."""
	# Bare CSS "monospace" mapped to TypeWriter bitmap fonts on Windows in the
	# old RichText path; keep the same platform faces for the PlainText TextArea.
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


def preview_gutter_text(line_count: int) -> str:
	"""Return right-aligned line numbers ``\"1\\n2\\n…\\nN\"`` for the QML gutter."""
	if line_count <= 0:
		return ""
	width = max(3, len(str(line_count)))
	return "\n".join(f"{number:>{width}}" for number in range(1, line_count + 1))


def segments_for_line(line: str, suffix: str) -> list[Segment]:
	"""Tokenize one source line into coloured segments for ``PreviewHighlighter``."""
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
