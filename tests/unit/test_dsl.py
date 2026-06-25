from __future__ import annotations

import pytest
from tests.helpers import Product

from srxy import Q, search
from srxy.models import QNodeType


pytestmark = pytest.mark.unit


def test_given_field_name_and_match_type_when_constructing_q_leaf_then_stores_configuration():
	# given
	from srxy import MatchType

	field = "name"
	match = MatchType.FUZZY
	weight = 2.0

	# when
	q = Q(field, match=match, weight=weight)

	# then
	assert q.node_type == QNodeType.LEAF
	assert q.field == field
	assert q.weight == weight


def test_given_shorthand_constructors_when_building_q_leaves_then_set_expected_match_types():
	# given
	shorthands = (
		(Q.composite("name"), "composite"),
		(Q.fuzzy("name"), "fuzzy"),
		(Q.exact("status"), "exact"),
		(Q.contains("desc"), "contains"),
		(Q.partial("sku"), "partial"),
		(Q.phonetic("last"), "phonetic"),
		(Q.semantic("body"), "semantic"),
	)

	# when
	values = [leaf.match.value for leaf, _expected in shorthands]

	# then
	assert values == [expected for _leaf, expected in shorthands]


def test_given_two_leaf_nodes_when_anding_then_builds_and_expression():
	# given
	left = Q.fuzzy("name")
	right = Q.exact("status")

	# when
	expr = left & right

	# then
	assert expr.node_type == QNodeType.AND
	assert len(expr.children) == 2


def test_given_two_leaf_nodes_when_oring_then_builds_or_expression():
	# given
	left = Q.fuzzy("name")
	right = Q.fuzzy("alias")

	# when
	expr = left | right

	# then
	assert expr.node_type == QNodeType.OR
	assert len(expr.children) == 2


def test_given_multiple_nodes_when_using_q_all_then_builds_and_expression():
	# given
	children = (Q.fuzzy("name"), Q.exact("status"))

	# when
	expr = Q.all(*children)

	# then
	assert expr.node_type == QNodeType.AND


def test_given_multiple_nodes_when_using_q_any_then_builds_or_expression():
	# given
	children = (Q.fuzzy("name"), Q.fuzzy("alias"))

	# when
	expr = Q.any(*children)

	# then
	assert expr.node_type == QNodeType.OR


def test_given_nested_leaf_nodes_when_combining_with_and_then_outer_node_is_and():
	# given
	or_expr = Q.any(Q.fuzzy("name"), Q.fuzzy("alias"))
	status_expr = Q.exact("status")

	# when
	expr = or_expr & status_expr

	# then
	assert expr.node_type == QNodeType.AND
	assert expr.children[0].node_type == QNodeType.OR


def test_given_no_children_when_calling_q_all_then_raises_value_error():
	# given
	children: tuple[Q, ...] = ()

	# when
	with pytest.raises(ValueError):
		Q.all(*children)

	# then
	assert True


def test_given_non_q_operand_when_anding_then_raises_type_error():
	# given
	left = Q.fuzzy("name")
	right = "invalid"

	# when
	with pytest.raises(TypeError):
		_ = left & right  # type: ignore[operator]

	# then
	assert True


def test_given_products_and_exact_alias_when_searching_spatializer_then_returns_single_match(
	products: list[Product],
):
	# given
	where = Q.exact("alias")

	# when
	results = search(products, "spatializer", where=where)

	# then
	assert len(results) == 1
	assert results[0].item.alias == "spatializer"


def test_given_active_spatial_products_when_and_searching_name_and_status_then_all_results_active(
	products: list[Product],
):
	# given
	where = Q.all(Q.fuzzy("name"), Q.exact("status"))

	# when
	results = search(products, "spatial", where=where, threshold=0.5)

	# then
	for result in results:
		assert result.item.status == "active"
		assert "spatial" in result.item.name.lower()


def test_given_inactive_spatial_product_when_and_searching_name_and_status_then_excludes_it(
	products: list[Product],
):
	# given
	where = Q.all(Q.fuzzy("name"), Q.exact("status"))

	# when
	results = search(products, "spatial", where=where, threshold=0.5)
	names = [result.item.name for result in results]

	# then
	assert "inactive tool" not in names


def test_given_name_or_tags_composite_when_searching_salat_then_matches_salad_or_tagged_item():
	# given
	items = [
		{"name": "unrelated", "tags": "unrelated"},
		{"name": "unrelated", "tags": "salat mix"},
		{"name": "salad", "tags": "unrelated"},
	]
	where = Q.composite("name") | Q.composite("tags")

	# when
	results = search(items, "salat", where=where, threshold=0.3)
	matched_names = {result.item["name"] for result in results}

	# then
	assert "salad" in matched_names or any("salat" in result.item["tags"] for result in results)


def test_given_sku_or_label_exact_match_when_searching_abc_123_then_returns_full_match_row():
	# given
	items = [
		{"sku": "ABC-123", "label": "ABC-123"},
		{"sku": "ABC-123", "label": "other"},
		{"sku": "XYZ", "label": "ABC-123"},
	]
	where = Q.any(Q.exact("sku"), Q.exact("barcode")) & Q.exact("label")

	# when
	results = search(items, "abc-123", where=where)

	# then
	assert len(results) == 1
	assert results[0].item["sku"] == "ABC-123"
	assert results[0].item["label"] == "ABC-123"


def test_given_or_expression_when_one_field_matches_exactly_then_score_is_one():
	# given
	items = [{"a": "hello", "b": "world"}]
	where = Q.exact("a") | Q.exact("b")

	# when
	results = search(items, "hello", where=where)

	# then
	assert len(results) == 1
	assert results[0].score == 1.0


def test_given_and_expression_when_both_fields_match_then_score_is_one():
	# given
	items = [{"a": "hello", "b": "hello"}]
	where = Q.exact("a") & Q.exact("b")

	# when
	results = search(items, "hello", where=where)

	# then
	assert len(results) == 1
	assert results[0].score == 1.0


def test_given_and_expression_when_one_field_misses_then_returns_empty():
	# given
	items = [{"a": "hello", "b": "world"}]
	where = Q.exact("a") & Q.exact("b")

	# when
	results = search(items, "hello", where=where)

	# then
	assert results == []


def test_given_composite_name_expression_when_searching_spatial_then_breakdown_contains_name(
	products: list[Product],
):
	# given
	where = Q.composite("name")

	# when
	results = search(products, "spatial", where=where, threshold=0.3)

	# then
	assert "name" in results[0].breakdown
	assert isinstance(results[0].breakdown["name"], dict)


def test_given_high_threshold_when_or_fuzzy_searching_unrelated_values_then_returns_empty():
	# given
	items = [{"a": "xyz", "b": "also-xyz"}]
	where = Q.fuzzy("a") | Q.fuzzy("b")

	# when
	results = search(items, "hello", where=where, threshold=0.8)

	# then
	assert results == []
