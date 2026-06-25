from __future__ import annotations

from srxy.matchers.base import Matcher
from srxy.matchers.registry import get_atomic_matcher, is_matcher_available
from srxy.models import DEFAULT_COMPOSITE_WEIGHTS, MatchType


class CompositeMatcher(Matcher):
	def __init__(self, weights: dict[MatchType, float] | None = None):
		self.weights = weights or DEFAULT_COMPOSITE_WEIGHTS

	def score(self, query: str, value: str) -> float:
		score, _ = self.score_with_breakdown(query, value)
		return score

	def score_with_breakdown(self, query: str, value: str) -> tuple[float, dict[str, float]]:
		active: list[tuple[MatchType, Matcher, float]] = []
		for match_type, weight in self.weights.items():
			if weight <= 0.0 or match_type == MatchType.COMPOSITE:
				continue
			if not is_matcher_available(match_type):
				continue
			active.append((match_type, get_atomic_matcher(match_type), weight))

		if not active:
			return 0.0, {}

		total_weight = sum(weight for _, _, weight in active)
		score = 0.0
		breakdown: dict[str, float] = {}
		for match_type, matcher, weight in active:
			sub_score = matcher.score(query, value)
			breakdown[match_type.value] = sub_score
			score += sub_score * weight / total_weight

		return score, breakdown
