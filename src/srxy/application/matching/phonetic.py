from __future__ import annotations

from functools import lru_cache

import jellyfish
from rapidfuzz import fuzz

from srxy.application.matching.base import Matcher


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


@lru_cache(maxsize=8192)
def _phonetic_codes(text: str) -> tuple[str | None, str, str]:
	"""Compute and cache all three phonetic codes for *text* in a single call.

	The query string is compared against every word/line in a document, so its
	codes would otherwise be recomputed thousands of times per search.  The
	cache also benefits repeated values such as short common words appearing
	across many files.
	"""
	return _phonetic_code(text), jellyfish.soundex(text), jellyfish.nysiis(text)


def _phonetic_signals(query: str, value: str) -> list[float]:
	scores: list[float] = []

	q_metaphone, q_soundex, q_nysiis = _phonetic_codes(query)
	v_metaphone, v_soundex, v_nysiis = _phonetic_codes(value)

	if q_metaphone and v_metaphone:
		if q_metaphone == v_metaphone:
			scores.append(1.0)
		else:
			scores.append(_metaphone_partial_score(q_metaphone, v_metaphone))

	if q_soundex == v_soundex:
		scores.append(_PHONETIC_ALT_MATCH_SCORE)

	if q_nysiis == v_nysiis:
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
