from __future__ import annotations

from functools import lru_cache

from srxy.application.matching.base import Matcher
from srxy.application.matching.contains import ContainsMatcher
from srxy.application.matching.exact import ExactMatcher
from srxy.application.matching.partial import PartialMatcher
from srxy.domain.models import MatchType


def _semantic_unavailable_message() -> str:
	from srxy.application.install_method import semantic_enable_hint
	from srxy.i18n import tr

	return tr("unavailable.semantic_disabled", hint=semantic_enable_hint())


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
		from srxy.application.matching.fuzzy import FuzzyMatcher

		return FuzzyMatcher()
	if match_type == MatchType.PHONETIC:
		from srxy.application.matching.phonetic import PhoneticMatcher

		return PhoneticMatcher()
	if not is_matcher_available(MatchType.SEMANTIC):
		raise RuntimeError(_semantic_unavailable_message())
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
