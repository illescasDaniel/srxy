from __future__ import annotations

from typing import Any

from srxy.matchers.registry import get_matcher
from srxy.models import FieldConfig, MatchType, Q, QNodeType, SearchResult
from srxy.utils import discover_fields, get_field_value, normalize_text


_DEFAULT_MAGIC_SEARCH_FIELDS: list[str] = []


def _score_field(
	item: Any,
	query: str,
	field: str,
	match_type: MatchType,
	composite_weights: dict[MatchType, float] | None,
) -> tuple[float, Any]:
	value = normalize_text(get_field_value(item, field))
	matcher = get_matcher(match_type, composite_weights)
	if hasattr(matcher, "score_with_breakdown"):
		score, sub_breakdown = matcher.score_with_breakdown(query, value)
		if sub_breakdown:
			return score, sub_breakdown
		return score, score
	return matcher.score(query, value), matcher.score(query, value)


def _evaluate_leaf(item: Any, query: str, leaf: Q) -> tuple[float, dict[str, Any]]:
	if leaf.field is None:
		return 0.0, {}

	score, detail = _score_field(item, query, leaf.field, leaf.match, leaf.composite_weights)
	return score, {leaf.field: detail}


def _evaluate_q(item: Any, query: str, expr: Q) -> tuple[float, dict[str, Any]]:
	if expr.node_type == QNodeType.LEAF:
		return _evaluate_leaf(item, query, expr)

	child_results = [_evaluate_q(item, query, child) for child in expr.children]
	child_scores = [score for score, _ in child_results]
	breakdown = {}
	for _, child_breakdown in child_results:
		breakdown.update(child_breakdown)

	if not child_scores:
		return 0.0, breakdown

	if expr.node_type == QNodeType.AND:
		return min(child_scores), breakdown
	return max(child_scores), breakdown


def _evaluate_fields(
	item: Any,
	query: str,
	fields: list[FieldConfig],
	require_all: bool,
	threshold: float,
) -> tuple[float, dict[str, Any], bool]:
	field_scores: list[tuple[float, float]] = []
	breakdown: dict[str, Any] = {}

	for field_config in fields:
		score, detail = _score_field(
			item,
			query,
			field_config.name,
			field_config.match,
			field_config.composite_weights,
		)
		field_scores.append((score, field_config.weight))
		breakdown[field_config.name] = detail

	if not field_scores:
		return 0.0, breakdown, False

	if require_all and any(score <= 0.0 for score, _ in field_scores):
		return 0.0, breakdown, False

	if require_all and threshold > 0.0 and any(score < threshold for score, _ in field_scores):
		return 0.0, breakdown, False

	total_weight = sum(weight for _, weight in field_scores)
	if total_weight == 0.0:
		return 0.0, breakdown, False

	weighted_score = sum(score * weight for score, weight in field_scores) / total_weight
	return weighted_score, breakdown, True


def search(
	items: list[Any],
	query: str,
	*,
	fields: list[FieldConfig] | None = None,
	where: Q | None = None,
	threshold: float = 0.0,
	require_all: bool = False,
) -> list[SearchResult]:
	if fields is not None and where is not None:
		raise ValueError("Provide either 'fields' or 'where', not both")
	if fields is None and where is None:
		raise ValueError("Provide either 'fields' or 'where'")

	normalized_query = normalize_text(query)
	if not normalized_query:
		return []

	results: list[SearchResult] = []

	for item in items:
		if where is not None:
			score, breakdown = _evaluate_q(item, normalized_query, where)
			if score <= 0.0 or score < threshold:
				continue
			results.append(SearchResult(item=item, score=score, breakdown=breakdown))
		elif fields is not None:
			score, breakdown, include = _evaluate_fields(
				item,
				normalized_query,
				fields,
				require_all,
				threshold,
			)
			if not include or score <= 0.0 or score < threshold:
				continue
			results.append(SearchResult(item=item, score=score, breakdown=breakdown))

	results.sort(key=lambda result: result.score, reverse=True)
	return results


def magic_search(
	items: list[Any],
	query: str,
	*,
	fields: list[str] = _DEFAULT_MAGIC_SEARCH_FIELDS,
	threshold: float = 0.35,
) -> list[SearchResult]:
	field_names = fields
	if not field_names:
		field_names = discover_fields(items)
	if not field_names:
		return []

	where = Q.any(*(Q.composite(field) for field in field_names))
	return search(items, query, where=where, threshold=threshold)
