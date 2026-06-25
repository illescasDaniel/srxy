from __future__ import annotations

from functools import lru_cache

from srxy.matchers.base import Matcher
from srxy.matchers.contains import ContainsMatcher
from srxy.matchers.exact import ExactMatcher
from srxy.matchers.fuzzy import FuzzyMatcher
from srxy.matchers.partial import PartialMatcher
from srxy.matchers.phonetic import PhoneticMatcher
from srxy.models import MatchType


_SEMANTIC_UNAVAILABLE_MESSAGE = (
	"Semantic matching is disabled. Set SRXY_SEMANTIC=1 and install the optional "
	"dependency: pip install 'srxy[semantic]'"
)


def is_matcher_available(match_type: MatchType) -> bool:
	if match_type == MatchType.SEMANTIC:
		from srxy.matchers.semantic import is_semantic_available

		return is_semantic_available()
	return match_type in {
		MatchType.EXACT,
		MatchType.CONTAINS,
		MatchType.PARTIAL,
		MatchType.FUZZY,
		MatchType.PHONETIC,
		MatchType.COMPOSITE,
	}


@lru_cache(maxsize=16)
def get_atomic_matcher(match_type: MatchType) -> Matcher:
	if match_type == MatchType.COMPOSITE:
		raise ValueError("Use get_matcher() for composite matching")
	if match_type == MatchType.EXACT:
		return ExactMatcher()
	if match_type == MatchType.CONTAINS:
		return ContainsMatcher()
	if match_type == MatchType.PARTIAL:
		return PartialMatcher()
	if match_type == MatchType.FUZZY:
		return FuzzyMatcher()
	if match_type == MatchType.PHONETIC:
		return PhoneticMatcher()
	if not is_matcher_available(MatchType.SEMANTIC):
		raise RuntimeError(_SEMANTIC_UNAVAILABLE_MESSAGE)
	from srxy.matchers.semantic import SemanticMatcher

	return SemanticMatcher()


def get_matcher(
	match_type: MatchType,
	composite_weights: dict[MatchType, float] | None = None,
) -> Matcher:
	if match_type == MatchType.COMPOSITE:
		from srxy.matchers.composite import CompositeMatcher

		return CompositeMatcher(composite_weights)
	return get_atomic_matcher(match_type)
