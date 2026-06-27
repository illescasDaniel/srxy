from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any, Literal

from rich.markup import escape


PreviewHighlight = Literal["guillemets", "bold", "none"]


def normalize_text(value: Any) -> str:
	if value is None:
		return ""
	return str(value).strip().lower()


def collapse_whitespace(text: str) -> str:
	return " ".join(text.split())


def find_match_span(text: str, query: str) -> tuple[int, int]:
	collapsed = collapse_whitespace(text)
	normalized_text = collapsed.lower()
	normalized_query = normalize_text(query)
	if not collapsed:
		return 0, 0
	if not normalized_query:
		return 0, min(len(collapsed), 1)

	exact_index = normalized_text.find(normalized_query)
	if exact_index >= 0:
		return exact_index, exact_index + len(normalized_query)

	from rapidfuzz.fuzz import partial_ratio_alignment

	alignment = partial_ratio_alignment(normalized_query, normalized_text, score_cutoff=1)
	if alignment is not None and alignment.dest_start < alignment.dest_end:
		return alignment.dest_start, alignment.dest_end

	for word in normalized_query.split():
		word_index = normalized_text.find(word)
		if word_index >= 0:
			return word_index, word_index + len(word)

	return 0, min(len(collapsed), 1)


def _wrap_match_highlight(match_text: str, *, highlight: PreviewHighlight) -> str:
	if highlight == "bold":
		return f"[bold]{escape(match_text)}[/bold]"
	if highlight == "guillemets":
		return f"«{match_text}»"
	return match_text


def _escape_preview_segment(text: str, *, highlight: PreviewHighlight) -> str:
	if highlight == "bold":
		return escape(text)
	return text


def format_match_preview(
	text: str,
	query: str,
	*,
	max_length: int = 100,
	highlight: PreviewHighlight = "guillemets",
) -> str:
	collapsed = collapse_whitespace(text)
	if not collapsed:
		return ""
	if not query:
		if len(collapsed) <= max_length:
			return collapsed
		return collapsed[: max_length - 1] + "…"

	start, end = find_match_span(collapsed, query)
	if start >= end:
		end = min(len(collapsed), start + 1)
	match_text = collapsed[start:end]
	highlighted = _wrap_match_highlight(match_text, highlight=highlight)

	def assemble(prefix_start: int, suffix_end: int) -> str:
		prefix = collapsed[prefix_start:start]
		suffix = collapsed[end:suffix_end]
		prefix_ellipsis = "…" if prefix_start > 0 else ""
		suffix_ellipsis = "…" if suffix_end < len(collapsed) else ""
		return (
			f"{prefix_ellipsis}"
			f"{_escape_preview_segment(prefix, highlight=highlight)}"
			f"{highlighted}"
			f"{_escape_preview_segment(suffix, highlight=highlight)}"
			f"{suffix_ellipsis}"
		)

	if highlight == "guillemets" and len(collapsed) + 2 <= max_length:
		return collapsed[:start] + highlighted + collapsed[end:]

	full_preview = assemble(0, len(collapsed))
	if len(full_preview) <= max_length:
		return full_preview

	if len(highlighted) >= max_length:
		return highlighted[: max_length - 1] + "…"

	remaining = max_length - len(highlighted)
	before_budget = remaining // 2
	after_budget = remaining - before_budget
	prefix_start = max(0, start - before_budget)
	suffix_end = min(len(collapsed), end + after_budget)
	return assemble(prefix_start, suffix_end)


def _is_public_field_name(name: str) -> bool:
	return not name.startswith("_")


def _fields_for_item(item: Any) -> set[str]:
	if isinstance(item, Mapping):
		return {str(key) for key in item}

	if dataclasses.is_dataclass(item) and not isinstance(item, type):
		return {field.name for field in dataclasses.fields(item)}

	names: set[str] = set()
	try:
		names.update(str(key) for key in vars(item))
	except TypeError:
		pass

	for name in dir(item):
		if _is_public_field_name(name):
			names.add(name)

	return names


def discover_fields(items: list[Any]) -> list[str]:
	if not items:
		return []

	field_names: set[str] = set()
	for item in items:
		field_names.update(name for name in _fields_for_item(item) if _is_public_field_name(name))

	return sorted(field_names)


def get_field_value(item: Any, field_name: str) -> Any:
	if isinstance(item, Mapping):
		try:
			return item[field_name]
		except KeyError:
			pass

	try:
		return item[field_name]  # type: ignore[index]
	except (KeyError, TypeError):
		pass

	return getattr(item, field_name, None)
