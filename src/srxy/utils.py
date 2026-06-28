from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping
from typing import Any, Literal

from rich.markup import escape


PreviewHighlight = Literal["guillemets", "bold", "none"]

_WORD_PATTERN = re.compile(r"[\w']+", flags=re.UNICODE)
_WORD_FUZZY_SCORE_CUTOFF = 50.0
_WORD_SEMANTIC_SCORE_CUTOFF = 0.5
_MIN_QUERY_WORD_LENGTH = 3
_MIN_WORD_PAIR_RATIO = 80.0


def normalize_text(value: Any) -> str:
	if value is None:
		return ""
	return str(value).strip().lower()


def collapse_whitespace(text: str) -> str:
	return " ".join(text.split())


def query_words(text: str) -> list[str]:
	words: list[str] = []
	for match in _WORD_PATTERN.finditer(text):
		word = match.group()
		normalized = normalize_text(word)
		if len(normalized) < _MIN_QUERY_WORD_LENGTH:
			continue
		if any(char.isalpha() for char in normalized):
			words.append(word)
	return words


def word_pair_match_allowed(
	query_word: str,
	doc_word: str,
	breakdown: Mapping[str, float],
	*,
	allow_semantic: bool = True,
) -> bool:
	if breakdown.get("exact", 0.0) > 0.0 or breakdown.get("contains", 0.0) > 0.0:
		return True
	if breakdown.get("partial", 0.0) > 0.0:
		return True
	normalized_query = normalize_text(query_word)
	normalized_word = normalize_text(doc_word)
	if normalized_query == normalized_word:
		return True
	if normalized_query in normalized_word.split():
		return True
	from srxy.matchers.registry import is_matcher_available
	from srxy.models import MatchType

	if (
		allow_semantic
		and is_matcher_available(MatchType.SEMANTIC)
		and breakdown.get("semantic", 0.0) >= _WORD_SEMANTIC_SCORE_CUTOFF
	):
		return True
	from rapidfuzz.fuzz import ratio

	return ratio(normalized_query, normalized_word) >= _MIN_WORD_PAIR_RATIO


_PREVIEW_ELLIPSIS = "..."


def split_tag_label(text: str) -> tuple[str | None, str]:
	collapsed = collapse_whitespace(text)
	if not collapsed.startswith("["):
		return None, collapsed
	bracket_end = collapsed.find("]")
	if bracket_end < 0:
		return None, collapsed
	label = collapsed[: bracket_end + 1]
	# Only strip a metadata field label like [Lyrics], not inline [Intro: ...] markers.
	if ":" in label[1:-1]:
		return None, collapsed
	body = collapsed[bracket_end + 1 :].strip()
	return label, body


def find_match_span(text: str, query: str, *, highlight_term: str | None = None) -> tuple[int, int]:
	_body_label, body = split_tag_label(collapse_whitespace(text))
	if not body:
		return 0, 0

	if highlight_term:
		return _find_match_span_for_term(body, highlight_term)

	from srxy.file_query import query_highlight_terms

	terms = query_highlight_terms(query)
	if not terms:
		return _find_match_span_for_term(body, query)
	if len(terms) == 1:
		return _find_match_span_for_term(body, terms[0])
	return _find_best_term_span(body, terms)


def _find_best_term_span(body: str, terms: list[str]) -> tuple[int, int]:
	best_span = (0, 0)
	best_score = -1.0
	for term in terms:
		start, end = _find_match_span_for_term(body, term)
		score = _span_match_score(body, start, end, term)
		if score > best_score:
			best_score = score
			best_span = (start, end)
	return best_span


def _span_match_score(text: str, start: int, end: int, term: str) -> float:
	from rapidfuzz.fuzz import partial_ratio

	collapsed = collapse_whitespace(text)
	if start >= end or not collapsed:
		return 0.0
	snippet = collapsed[start:end]
	return float(partial_ratio(normalize_text(term), snippet.lower()))


def _find_match_span_for_term(text: str, query: str) -> tuple[int, int]:
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

	if " " in normalized_query:
		multi_word_span = _find_multi_word_highlight_span(collapsed, normalized_query)
		if multi_word_span is not None:
			return multi_word_span
		terms = query_words(normalized_query)
		if len(terms) >= 2:
			best_term_span = _find_best_term_span(collapsed, terms)
			if best_term_span != (0, 0):
				return best_term_span
			return 0, 0

	from rapidfuzz.fuzz import partial_ratio_alignment

	alignment = partial_ratio_alignment(normalized_query, normalized_text, score_cutoff=60)
	if alignment is not None and alignment.dest_start < alignment.dest_end:
		return alignment.dest_start, alignment.dest_end

	if " " not in normalized_query:
		word_index = normalized_text.find(normalized_query)
		if word_index >= 0:
			return word_index, word_index + len(normalized_query)

	word_fuzzy_span = _find_word_fuzzy_span(collapsed, normalized_query)
	if word_fuzzy_span is not None:
		return word_fuzzy_span

	word_semantic_span = _find_semantic_word_span(collapsed, query)
	if word_semantic_span is not None:
		return word_semantic_span

	return 0, min(len(collapsed), 1)


def _find_multi_word_highlight_span(collapsed: str, normalized_query: str) -> tuple[int, int] | None:
	words = query_words(normalized_query)
	if len(words) < 2:
		return None
	positions: list[tuple[int, int]] = []
	for word in words:
		normalized_word = normalize_text(word)
		found: tuple[int, int] | None = None
		for match in _WORD_PATTERN.finditer(collapsed):
			candidate = match.group()
			if normalize_text(candidate) == normalized_word:
				found = (match.start(), match.end())
				break
		if found is None:
			return None
		positions.append(found)
	start = min(position[0] for position in positions)
	end = max(position[1] for position in positions)
	return start, end


def _find_any_query_word_span(collapsed: str, terms: list[str]) -> tuple[int, int]:
	for term in terms:
		normalized_term = normalize_text(term)
		for match in _WORD_PATTERN.finditer(collapsed):
			if normalize_text(match.group()) == normalized_term:
				return match.start(), match.end()
	return 0, 0


def _find_word_fuzzy_span(text: str, normalized_query: str) -> tuple[int, int] | None:
	from rapidfuzz.fuzz import partial_ratio

	best_span: tuple[int, int] | None = None
	best_score = 0.0
	for match in _WORD_PATTERN.finditer(text):
		word = match.group()
		word_score = float(partial_ratio(normalized_query, normalize_text(word)))
		if word_score > best_score:
			best_score = word_score
			best_span = (match.start(), match.end())
	if best_span is not None and best_score >= _WORD_FUZZY_SCORE_CUTOFF:
		return best_span
	return None


def _find_semantic_word_span(text: str, query: str) -> tuple[int, int] | None:
	from srxy.matchers.registry import get_atomic_matcher, is_matcher_available
	from srxy.models import MatchType

	if not is_matcher_available(MatchType.SEMANTIC):
		return None

	semantic = get_atomic_matcher(MatchType.SEMANTIC)
	best_span: tuple[int, int] | None = None
	best_score = 0.0
	for match in _WORD_PATTERN.finditer(text):
		word = match.group()
		word_score = semantic.score(query, normalize_text(word))
		if word_score > best_score:
			best_score = word_score
			best_span = (match.start(), match.end())
	if best_span is not None and best_score >= _WORD_SEMANTIC_SCORE_CUTOFF:
		return best_span
	return None


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
	highlight_term: str | None = None,
) -> str:
	tag_label, body = split_tag_label(collapse_whitespace(text))
	if not body:
		return tag_label or ""
	if not query or highlight == "none":
		plain = f"{tag_label} {body}".strip() if tag_label else body
		if len(plain) <= max_length:
			return plain
		return plain[: max_length - len(_PREVIEW_ELLIPSIS)] + _PREVIEW_ELLIPSIS

	if highlight_term:
		start, end = _find_match_span_for_term(body, highlight_term)
	elif query:
		from srxy.file_query import parse_file_query, query_highlight_terms, query_is_compound

		terms = query_highlight_terms(query)
		if len(terms) > 1:
			try:
				phrase_words = not query_is_compound(parse_file_query(query))
			except ValueError:
				phrase_words = False
			if phrase_words:
				multi_word_span = _find_multi_word_highlight_span(body, " ".join(terms))
				if multi_word_span is not None:
					start, end = multi_word_span
				else:
					start, end = _find_any_query_word_span(body, terms)
			else:
				start, end = _find_best_term_span(body, terms)
		elif len(terms) == 1:
			start, end = _find_match_span_for_term(body, terms[0])
		else:
			start, end = _find_match_span_for_term(body, query)
	else:
		start, end = 0, min(len(body), 1)
	if start >= end and query and len(query_words(query)) >= 2:
		plain = f"{tag_label} {body}".strip() if tag_label else body
		if len(plain) <= max_length:
			return plain
		return plain[: max_length - len(_PREVIEW_ELLIPSIS)] + _PREVIEW_ELLIPSIS
	if start >= end:
		end = min(len(body), start + 1)
	match_text = body[start:end]
	highlighted = _wrap_match_highlight(match_text, highlight=highlight)

	def assemble(prefix_start: int, suffix_end: int) -> str:
		prefix = body[prefix_start:start]
		suffix = body[end:suffix_end]
		prefix_ellipsis = _PREVIEW_ELLIPSIS if prefix_start > 0 else ""
		suffix_ellipsis = _PREVIEW_ELLIPSIS if suffix_end < len(body) else ""
		body_preview = (
			f"{prefix_ellipsis}"
			f"{_escape_preview_segment(prefix, highlight=highlight)}"
			f"{highlighted}"
			f"{_escape_preview_segment(suffix, highlight=highlight)}"
			f"{suffix_ellipsis}"
		)
		if tag_label:
			return f"{tag_label} {body_preview}"
		return body_preview

	if highlight == "guillemets" and len(body) + 2 <= max_length:
		core = body[:start] + highlighted + body[end:]
		return f"{tag_label} {core}".strip() if tag_label else core

	full_preview = assemble(0, len(body))
	if len(full_preview) <= max_length:
		return full_preview

	if len(highlighted) >= max_length:
		return highlighted[: max_length - len(_PREVIEW_ELLIPSIS)] + _PREVIEW_ELLIPSIS

	remaining = max_length - len(highlighted)
	before_budget = remaining // 2
	after_budget = remaining - before_budget
	prefix_start = max(0, start - before_budget)
	suffix_end = min(len(body), end + after_budget)
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
