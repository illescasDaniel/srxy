from __future__ import annotations

from functools import lru_cache

from srxy.application.matching.base import Matcher
from srxy.application.matching.contains import ContainsMatcher
from srxy.application.matching.exact import ExactMatcher
from srxy.application.matching.fuzzy import FuzzyMatcher
from srxy.application.matching.partial import PartialMatcher
from srxy.application.matching.phonetic import PhoneticMatcher
from srxy.domain.models import MatchType


_SEMANTIC_UNAVAILABLE_MESSAGE = (
	"Semantic matching is disabled. Set SRXY_SEMANTIC=1 and install the optional "
	"dependency: uv tool install 'srxy[semantic]' (or: pipx install 'srxy[semantic]')"
)


def is_matcher_available(match_type: MatchType) -> bool:
	if match_type == MatchType.SEMANTIC:
		from srxy.application.matching.semantic import is_semantic_available

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
	from srxy.application.matching.semantic import SemanticMatcher

	return SemanticMatcher()


def get_matcher(
	match_type: MatchType,
	composite_weights: dict[MatchType, float] | None = None,
) -> Matcher:
	if match_type == MatchType.COMPOSITE:
		from srxy.application.matching.composite import CompositeMatcher

		return CompositeMatcher(composite_weights)
	return get_atomic_matcher(match_type)
