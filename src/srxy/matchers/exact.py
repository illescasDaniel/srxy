from __future__ import annotations

from srxy.matchers.base import Matcher


class ExactMatcher(Matcher):
	def score(self, query: str, value: str) -> float:
		if not query or not value:
			return 0.0
		return 1.0 if query == value else 0.0
