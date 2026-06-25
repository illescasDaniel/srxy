from __future__ import annotations

import pytest
from tests.helpers import Product

from srxy import FieldConfig, MatchType, Q, search
from srxy.matchers.composite import CompositeMatcher
from srxy.matchers.registry import get_atomic_matcher, get_matcher, is_matcher_available


pytestmark = pytest.mark.unit


def test_given_salat_candidates_when_composite_matching_then_salad_scores_at_least_salty(
	food_items: list[dict[str, str]],
):
	# given
	matcher = CompositeMatcher()

	# when
	scores = {item["name"]: matcher.score("salat", item["name"]) for item in food_items}

	# then
	assert scores["salad"] >= scores["salty"]
	assert all(score > 0.0 for score in scores.values())


def test_given_special_query_when_composite_matching_then_spatial_beats_unrelated():
	# given
	matcher = CompositeMatcher()

	# when
	score_spatial = matcher.score("special", "spatial")
	score_special = matcher.score("special", "special")
	score_unrelated = matcher.score("special", "zzzzzz")

	# then
	assert score_spatial > score_unrelated
	assert score_special > score_spatial


def test_given_salat_and_salad_when_composite_matching_then_returns_breakdown():
	# given
	matcher = CompositeMatcher()
	query = "salat"
	value = "salad"

	# when
	score, breakdown = matcher.score_with_breakdown(query, value)

	# then
	assert 0.0 < score <= 1.0
	assert "fuzzy" in breakdown
	assert "partial" in breakdown
	assert "contains" in breakdown
	assert "semantic" in breakdown
	assert "phonetic" in breakdown


def test_given_fuzzy_only_weights_when_composite_matching_then_score_equals_fuzzy_component():
	# given
	weights = {MatchType.FUZZY: 1.0}
	matcher = CompositeMatcher(weights)

	# when
	score, breakdown = matcher.score_with_breakdown("salat", "salad")

	# then
	assert score == pytest.approx(breakdown["fuzzy"])


def test_given_products_and_fuzzy_name_field_when_searching_spatial_then_returns_match(
	products: list[Product],
):
	# given
	query = "spatial"
	fields = [FieldConfig("name", MatchType.FUZZY)]

	# when
	results = search(products, query, fields=fields, threshold=0.5)

	# then
	assert len(results) >= 1
	assert "spatial" in results[0].item.name.lower()


def test_given_products_and_exact_category_when_searching_food_then_returns_single_match(
	products: list[Product],
):
	# given
	query = "food"
	fields = [FieldConfig("category", MatchType.EXACT)]

	# when
	results = search(products, query, fields=fields)

	# then
	assert len(results) == 1
	assert results[0].item.category == "food"


def test_given_products_and_contains_description_when_searching_spatial_then_returns_two_matches(
	products: list[Product],
):
	# given
	query = "spatial"
	fields = [FieldConfig("description", MatchType.CONTAINS)]

	# when
	results = search(products, query, fields=fields)

	# then
	assert len(results) == 2


def test_given_food_items_and_composite_name_when_searching_salat_then_returns_close_match(
	food_items: list[dict[str, str]],
):
	# given
	query = "salat"
	fields = [FieldConfig("name", MatchType.COMPOSITE)]

	# when
	results = search(food_items, query, fields=fields, threshold=0.3)

	# then
	assert len(results) >= 1
	assert results[0].item["name"] in {"salt", "salad", "salty"}


def test_given_weighted_name_and_description_fields_when_searching_spatial_then_includes_breakdown(
	products: list[Product],
):
	# given
	query = "spatial"
	fields = [
		FieldConfig("name", MatchType.FUZZY, weight=2.0),
		FieldConfig("description", MatchType.CONTAINS, weight=1.0),
	]

	# when
	results = search(products, query, fields=fields, threshold=0.3)

	# then
	assert len(results) >= 1
	assert "name" in results[0].breakdown
	assert "description" in results[0].breakdown


def test_given_require_all_and_two_exact_fields_when_searching_spatial_then_keeps_matching_row():
	# given
	items = [
		{"code": "spatial", "status": "spatial"},
		{"code": "spatial", "status": "inactive"},
	]
	fields = [
		FieldConfig("code", MatchType.EXACT),
		FieldConfig("status", MatchType.EXACT),
	]

	# when
	results = search(items, "spatial", fields=fields, require_all=True)

	# then
	assert len(results) == 1
	assert results[0].item["status"] == "spatial"


def test_given_high_threshold_when_fuzzy_searching_salat_then_returns_empty(food_items: list[dict[str, str]]):
	# given
	fields = [FieldConfig("name", MatchType.FUZZY)]

	# when
	results = search(food_items, "salat", fields=fields, threshold=0.95)

	# then
	assert results == []


def test_given_empty_query_when_searching_products_then_returns_empty(products: list[Product]):
	# given
	fields = [FieldConfig("name", MatchType.FUZZY)]

	# when
	results = search(products, "", fields=fields)

	# then
	assert results == []


def test_given_composite_name_field_when_searching_salat_then_sorts_scores_descending(
	food_items: list[dict[str, str]],
):
	# given
	fields = [FieldConfig("name", MatchType.COMPOSITE)]

	# when
	results = search(food_items, "salat", fields=fields, threshold=0.0)

	# then
	scores = [result.score for result in results]
	assert scores == sorted(scores, reverse=True)


def test_given_dict_and_dataclass_items_when_fuzzy_searching_spatial_then_both_match(
	products: list[Product],
):
	# given
	dict_items = [{"name": "spatial tool"}]
	class_items = products[:1]
	fields = [FieldConfig("name", MatchType.FUZZY)]

	# when
	dict_results = search(dict_items, "spatial", fields=fields)
	class_results = search(class_items, "spatial", fields=fields)

	# then
	assert len(dict_results) == 1
	assert len(class_results) == 1


def test_given_fields_and_where_together_when_searching_then_raises_value_error(products: list[Product]):
	# given
	fields = [FieldConfig("name", MatchType.FUZZY)]
	where = Q.fuzzy("name")

	# when
	with pytest.raises(ValueError, match="either 'fields' or 'where'"):
		search(products, "test", fields=fields, where=where)

	# then
	assert True


def test_given_no_fields_or_where_when_searching_then_raises_value_error(products: list[Product]):
	# given
	query = "test"

	# when
	with pytest.raises(ValueError, match="either 'fields' or 'where'"):
		search(products, query)

	# then
	assert True


def test_given_core_match_types_when_checking_availability_then_all_are_available():
	# given
	match_types = (MatchType.EXACT, MatchType.CONTAINS, MatchType.PARTIAL, MatchType.FUZZY)

	# when
	availability = [is_matcher_available(match_type) for match_type in match_types]

	# then
	assert all(availability)


def test_given_composite_match_type_when_getting_matcher_then_scores_identical_strings_as_one():
	# given
	matcher = get_matcher(MatchType.COMPOSITE)

	# when
	score = matcher.score("a", "a")

	# then
	assert score == pytest.approx(1.0, abs=1e-6)


def test_given_phonetic_match_type_when_checking_availability_then_it_is_available():
	# given
	match_type = MatchType.PHONETIC

	# when
	available = is_matcher_available(match_type)

	# then
	assert available


def test_given_semantic_match_type_when_env_disabled_then_it_is_unavailable(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.delenv("SRXY_SEMANTIC", raising=False)
	get_atomic_matcher.cache_clear()

	# when
	available = is_matcher_available(MatchType.SEMANTIC)

	# then
	assert not available


def test_given_semantic_match_type_when_env_enabled_then_it_is_available(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_SEMANTIC", "1")
	get_atomic_matcher.cache_clear()

	# when
	available = is_matcher_available(MatchType.SEMANTIC)

	# then
	assert available


def test_given_semantic_query_when_env_disabled_then_search_raises_runtime_error(
	monkeypatch: pytest.MonkeyPatch,
	products: list[Product],
):
	# given
	monkeypatch.delenv("SRXY_SEMANTIC", raising=False)
	get_atomic_matcher.cache_clear()
	where = Q.semantic("name")

	# when
	with pytest.raises(RuntimeError, match="SRXY_SEMANTIC=1"):
		search(products, "spatial", where=where)

	# then
	assert True
