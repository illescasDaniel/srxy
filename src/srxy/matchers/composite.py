from __future__ import annotations

from srxy.matchers.base import Matcher
from srxy.matchers.registry import get_atomic_matcher, is_matcher_available
from srxy.models import DEFAULT_COMPOSITE_WEIGHTS, MatchType


class CompositeMatcher(Matcher):
	def __init__(self, weights: dict[MatchType, float] | None = None):
		self.weights = weights or DEFAULT_COMPOSITE_WEIGHTS
		# Pre-fetch the active atomic matchers once at construction time.
		# Calling get_atomic_matcher() (which holds an lru_cache lock) inside
		# score_with_breakdown() added O(n_files × n_lines × n_matchers) lock
		# acquisitions per search — a measurable bottleneck under both sequential
		# and threaded workloads.  Availability is determined by env-vars that
		# are stable for the lifetime of a search, so snapshotting here is safe.
		self._active: list[tuple[MatchType, Matcher, float]] = [
			(match_type, get_atomic_matcher(match_type), weight)
			for match_type, weight in self.weights.items()
			if weight > 0.0 and match_type != MatchType.COMPOSITE and is_matcher_available(match_type)
		]

	def score(self, query: str, value: str) -> float:
		score, _ = self.score_with_breakdown(query, value)
		return score

	def score_with_breakdown(self, query: str, value: str) -> tuple[float, dict[str, float]]:
		if not self._active:
			return 0.0, {}
		total_weight = sum(weight for _, _, weight in self._active)
		score = 0.0
		breakdown: dict[str, float] = {}
		for match_type, matcher, weight in self._active:
			sub_score = matcher.score(query, value)
			breakdown[match_type.value] = sub_score
			score += sub_score * weight / total_weight
		return score, breakdown
