from __future__ import annotations

from srxy.matchers.base import Matcher


class PartialMatcher(Matcher):
	def score(self, query: str, value: str) -> float:
		if not query or not value:
			return 0.0
		if value.startswith(query) or value.endswith(query):
			return 1.0
		return 0.0
