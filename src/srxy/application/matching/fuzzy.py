from __future__ import annotations

from srxy.application.matching.base import Matcher


class FuzzyMatcher(Matcher):
	def score(self, query: str, value: str) -> float:
		from rapidfuzz import fuzz

		if not query or not value:
			return 0.0
		weighted = fuzz.WRatio(query, value)
		partial = fuzz.partial_ratio(query, value)
		return (weighted * 0.5 + partial * 0.5) / 100.0
