"""Lightweight HTML preview formatting for the GUI file pane."""

from __future__ import annotations

import html
import re
from pathlib import Path


__all__ = [
	"PREVIEW_MAX_BYTES",
	"PREVIEW_MAX_LINES",
	"format_preview_html",
	"format_preview_message",
	"format_preview_plain",
	"prepare_preview_text",
]

PREVIEW_MAX_BYTES = 64 * 1024
PREVIEW_MAX_LINES = 2000
_PLAIN_PREVIEW_BYTES = 16 * 1024

_LN_COLOR = "#888888"
_KW_COLOR = "#0550ae"
_STR_COLOR = "#0a3069"
_CMT_COLOR = "#6a737d"
_MD_HEADING = "#0550ae"
_TRUNC_FOOTER_COLOR = "#6a737d"

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
	return f'<span style="font-family:monospace">{html.escape(message)}</span>'


def format_preview_truncated_footer(message: str) -> str:
	"""Append a muted footer when preview content was capped."""
	body = html.escape(message)
	return f'<div style="font-family:monospace; margin-top:8px; color:{_TRUNC_FOOTER_COLOR}">{body}</div>'


def format_preview_plain(path: Path | str, text: str) -> str:
	"""Return HTML with line numbers but no syntax highlighting."""
	lines = text.splitlines() or [""]
	width = max(3, len(str(len(lines))))
	parts = [
		'<div style="font-family:monospace; white-space:pre-wrap;">',
	]
	for number, line in enumerate(lines, start=1):
		gutter = html.escape(f"{number:>{width}}")
		body = html.escape(line)
		parts.append(f'<span style="color:{_LN_COLOR}">{gutter}</span>  {body}<br/>')
	parts.append("</div>")
	return "".join(parts)


def format_preview_html(path: Path | str, text: str) -> str:
	"""Return HTML with line numbers and basic syntax colors for ``text``."""
	text, _truncated = prepare_preview_text(text)
	suffix = Path(path).suffix.lower()
	if len(text.encode("utf-8")) > _PLAIN_PREVIEW_BYTES or text.count("\n") >= 500:
		return format_preview_plain(path, text)
	lines = text.splitlines() or [""]
	width = max(3, len(str(len(lines))))
	parts = [
		'<div style="font-family:monospace; white-space:pre-wrap;">',
	]
	for number, line in enumerate(lines, start=1):
		gutter = html.escape(f"{number:>{width}}")
		body = _highlight_line(line, suffix)
		parts.append(f'<span style="color:{_LN_COLOR}">{gutter}</span>  {body}<br/>')
	parts.append("</div>")
	return "".join(parts)


def format_preview_for_file(
	path: Path | str,
	text: str,
	*,
	truncated: bool = False,
	truncated_footer: str = "",
) -> str:
	"""Format capped preview text, using plain layout for large payloads."""
	text, was_truncated = prepare_preview_text(text)
	truncated = truncated or was_truncated
	use_plain = len(text.encode("utf-8")) > _PLAIN_PREVIEW_BYTES or text.count("\n") >= 500
	if use_plain:
		body = format_preview_plain(path, text)
	else:
		suffix = Path(path).suffix.lower()
		lines = text.splitlines() or [""]
		width = max(3, len(str(len(lines))))
		parts = [
			'<div style="font-family:monospace; white-space:pre-wrap;">',
		]
		for number, line in enumerate(lines, start=1):
			gutter = html.escape(f"{number:>{width}}")
			line_body = _highlight_line(line, suffix)
			parts.append(f'<span style="color:{_LN_COLOR}">{gutter}</span>  {line_body}<br/>')
		parts.append("</div>")
		body = "".join(parts)
	if truncated and truncated_footer:
		body += format_preview_truncated_footer(truncated_footer)
	return body


def _highlight_line(line: str, suffix: str) -> str:
	if suffix in {".md", ".markdown"}:
		return _highlight_markdown_line(line)
	if suffix == ".json":
		return _highlight_json_line(line)
	keywords = _keywords_for_suffix(suffix)
	if keywords is None:
		return html.escape(line)
	return _highlight_tokens(line, keywords)


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


def _span(color: str, text: str) -> str:
	return f'<span style="color:{color}">{html.escape(text)}</span>'


def _highlight_tokens(line: str, keywords: frozenset[str]) -> str:
	# Line comments only for # and // (block comments rare in single-line pass).
	if line.lstrip().startswith("#") or line.lstrip().startswith("//"):
		return _span(_CMT_COLOR, line)
	parts: list[str] = []
	for match in _TOKEN_RE.finditer(line):
		kind = match.lastgroup
		value = match.group()
		if kind == "comment":
			parts.append(_span(_CMT_COLOR, value))
		elif kind == "string":
			parts.append(_span(_STR_COLOR, value))
		elif kind == "word" and value in keywords:
			parts.append(_span(_KW_COLOR, value))
		else:
			parts.append(html.escape(value))
	return "".join(parts)


def _highlight_markdown_line(line: str) -> str:
	stripped = line.lstrip()
	if stripped.startswith("#"):
		return _span(_MD_HEADING, line)
	if stripped.startswith("```"):
		return _span(_CMT_COLOR, line)
	return html.escape(line)


def _highlight_json_line(line: str) -> str:
	parts: list[str] = []
	for match in _TOKEN_RE.finditer(line):
		kind = match.lastgroup
		value = match.group()
		if kind == "string":
			parts.append(_span(_STR_COLOR, value))
		elif kind == "word" and value in {"true", "false", "null"}:
			parts.append(_span(_KW_COLOR, value))
		else:
			parts.append(html.escape(value))
	return "".join(parts)
