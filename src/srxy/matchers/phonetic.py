from __future__ import annotations

import jellyfish
from rapidfuzz import fuzz

from srxy.matchers.base import Matcher


_PHONETIC_ALT_MATCH_SCORE = 0.85
_PHONETIC_PARTIAL_RATIO_THRESHOLD = 0.5
_PHONETIC_PARTIAL_SCORE_CAP = 0.5


def _phonetic_code(text: str) -> str | None:
	code = jellyfish.metaphone(text)
	return code or None


def _metaphone_partial_score(query_code: str, value_code: str) -> float:
	ratio = fuzz.ratio(query_code, value_code) / 100.0
	if ratio < _PHONETIC_PARTIAL_RATIO_THRESHOLD:
		return 0.0
	return ratio * _PHONETIC_PARTIAL_SCORE_CAP


def _phonetic_signals(query: str, value: str) -> list[float]:
	scores: list[float] = []

	query_metaphone = _phonetic_code(query)
	value_metaphone = _phonetic_code(value)
	if query_metaphone and value_metaphone:
		if query_metaphone == value_metaphone:
			scores.append(1.0)
		else:
			scores.append(_metaphone_partial_score(query_metaphone, value_metaphone))

	if jellyfish.soundex(query) == jellyfish.soundex(value):
		scores.append(_PHONETIC_ALT_MATCH_SCORE)

	if jellyfish.nysiis(query) == jellyfish.nysiis(value):
		scores.append(_PHONETIC_ALT_MATCH_SCORE)

	return scores


class PhoneticMatcher(Matcher):
	def score(self, query: str, value: str) -> float:
		if not query or not value:
			return 0.0

		scores = _phonetic_signals(query, value)
		if not scores:
			return 0.0
		return max(scores)
