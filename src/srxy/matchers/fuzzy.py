from __future__ import annotations

from rapidfuzz import fuzz

from srxy.matchers.base import Matcher


class FuzzyMatcher(Matcher):
	def score(self, query: str, value: str) -> float:
		if not query or not value:
			return 0.0
		weighted = fuzz.WRatio(query, value)
		partial = fuzz.partial_ratio(query, value)
		return (weighted * 0.5 + partial * 0.5) / 100.0
