from __future__ import annotations

import pytest

from srxy.matchers.contains import ContainsMatcher
from srxy.matchers.exact import ExactMatcher
from srxy.matchers.fuzzy import FuzzyMatcher
from srxy.matchers.partial import PartialMatcher
from srxy.matchers.phonetic import PhoneticMatcher
from srxy.models import DEFAULT_COMPOSITE_WEIGHTS, MatchType
from srxy.utils import get_field_value, normalize_text


pytestmark = pytest.mark.unit


def test_given_mixed_case_text_when_normalizing_then_lowercases_and_strips():
	# given
	value = "  Hello World  "

	# when
	result = normalize_text(value)

	# then
	assert result == "hello world"


def test_given_none_when_normalizing_then_returns_empty_string():
	# given
	value = None

	# when
	result = normalize_text(value)

	# then
	assert result == ""


def test_given_integer_when_normalizing_then_returns_string_form():
	# given
	value = 42

	# when
	result = normalize_text(value)

	# then
	assert result == "42"


def test_given_dict_item_when_getting_field_then_returns_value():
	# given
	item = {"name": "alice"}

	# when
	result = get_field_value(item, "name")

	# then
	assert result == "alice"


def test_given_object_item_when_getting_field_then_returns_attribute():
	# given
	class Item:
		name = "bob"

	item = Item()

	# when
	result = get_field_value(item, "name")

	# then
	assert result == "bob"


def test_given_missing_field_when_getting_value_then_returns_none():
	# given
	item = {"other": 1}

	# when
	result = get_field_value(item, "name")

	# then
	assert result is None


def test_given_equal_strings_when_exact_matching_then_scores_one():
	# given
	matcher = ExactMatcher()
	query = "hello"
	value = "hello"

	# when
	score = matcher.score(query, value)

	# then
	assert score == 1.0


def test_given_different_case_strings_when_exact_matching_then_scores_zero():
	# given
	matcher = ExactMatcher()
	query = "hello"
	value = "HELLO"

	# when
	score = matcher.score(query, value)

	# then
	assert score == 0.0


def test_given_unrelated_strings_when_exact_matching_then_scores_zero():
	# given
	matcher = ExactMatcher()
	query = "hello"
	value = "world"

	# when
	score = matcher.score(query, value)

	# then
	assert score == 0.0


def test_given_empty_query_when_exact_matching_then_scores_zero():
	# given
	matcher = ExactMatcher()
	query = ""
	value = "hello"

	# when
	score = matcher.score(query, value)

	# then
	assert score == 0.0


def test_given_substring_query_when_contains_matching_then_scores_one():
	# given
	matcher = ContainsMatcher()
	query = "spa"
	value = "spatial"

	# when
	score = matcher.score(query, value)

	# then
	assert score == 1.0


def test_given_missing_substring_when_contains_matching_then_scores_zero():
	# given
	matcher = ContainsMatcher()
	query = "xyz"
	value = "spatial"

	# when
	score = matcher.score(query, value)

	# then
	assert score == 0.0


def test_given_prefix_query_when_partial_matching_then_scores_one():
	# given
	matcher = PartialMatcher()
	query = "sal"
	value = "salad"

	# when
	score = matcher.score(query, value)

	# then
	assert score == 1.0


def test_given_suffix_query_when_partial_matching_then_scores_one():
	# given
	matcher = PartialMatcher()
	query = "lad"
	value = "salad"

	# when
	score = matcher.score(query, value)

	# then
	assert score == 1.0


def test_given_middle_query_when_partial_matching_then_scores_zero():
	# given
	matcher = PartialMatcher()
	query = "ala"
	value = "salad"

	# when
	score = matcher.score(query, value)

	# then
	assert score == 0.0


def test_given_similar_words_when_fuzzy_matching_then_scores_high():
	# given
	matcher = FuzzyMatcher()
	query = "special"
	value = "spatial"

	# when
	score = matcher.score(query, value)

	# then
	assert score > 0.7


def test_given_identical_words_when_fuzzy_matching_then_scores_one():
	# given
	matcher = FuzzyMatcher()
	query = "hello"
	value = "hello"

	# when
	score = matcher.score(query, value)

	# then
	assert score == 1.0


def test_given_unrelated_words_when_fuzzy_matching_then_scores_low():
	# given
	matcher = FuzzyMatcher()
	query = "hello"
	value = "zzzzzz"

	# when
	score = matcher.score(query, value)

	# then
	assert score < 0.3


def test_given_phonetically_similar_names_when_phonetic_matching_then_scores_one():
	# given
	matcher = PhoneticMatcher()
	query = "smith"
	value = "smyth"

	# when
	score = matcher.score(query, value)

	# then
	assert score == 1.0


def test_given_phonetically_different_words_when_phonetic_matching_then_scores_zero():
	# given
	matcher = PhoneticMatcher()
	query = "hello"
	value = "world"

	# when
	score = matcher.score(query, value)

	# then
	assert score == 0.0


def test_given_default_composite_weights_when_summed_then_equal_one():
	# given
	weights = DEFAULT_COMPOSITE_WEIGHTS

	# when
	total = sum(weights.values())

	# then
	assert total == pytest.approx(1.0)


def test_given_default_composite_weights_when_checked_then_include_all_atomic_matchers():
	# given
	weights = DEFAULT_COMPOSITE_WEIGHTS

	# when
	match_types = set(weights.keys())

	# then
	assert match_types == {
		MatchType.FUZZY,
		MatchType.SEMANTIC,
		MatchType.PARTIAL,
		MatchType.PHONETIC,
		MatchType.CONTAINS,
		MatchType.EXACT,
	}


def test_given_phonetically_similar_variants_when_phonetic_matching_then_scores_one():
	# given
	matcher = PhoneticMatcher()

	# when
	stephen_score = matcher.score("stephen", "steven")
	knight_score = matcher.score("knight", "night")

	# then
	assert stephen_score == 1.0
	assert knight_score == 1.0
