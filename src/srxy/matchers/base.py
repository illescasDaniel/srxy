from __future__ import annotations

from abc import ABC, abstractmethod


class Matcher(ABC):
	@abstractmethod
	def score(self, query: str, value: str) -> float:
		"""Return a relevance score in the range [0.0, 1.0]."""

	def score_with_breakdown(self, query: str, value: str) -> tuple[float, dict[str, float]]:
		score = self.score(query, value)
		return score, {}
