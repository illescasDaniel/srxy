from __future__ import annotations

from dataclasses import dataclass

import pytest
from tests.helpers import Product

from srxy import magic_search
from srxy.utils import discover_fields


pytestmark = pytest.mark.unit


def test_given_empty_items_when_discovering_fields_then_returns_empty_list():
	# given
	items: list[dict[str, str]] = []

	# when
	result = discover_fields(items)

	# then
	assert result == []


def test_given_sparse_dict_items_when_discovering_fields_then_returns_union_of_keys():
	# given
	items = [
		{"name": "alice", "role": "engineer"},
		{"name": "bob", "tags": "python"},
	]

	# when
	result = discover_fields(items)

	# then
	assert result == ["name", "role", "tags"]


def test_given_dataclass_items_when_discovering_fields_then_returns_field_names():
	# given
	@dataclass
	class Person:
		name: str
		age: int

	items = [Person("alice", 30)]

	# when
	result = discover_fields(items)

	# then
	assert result == ["age", "name"]


def test_given_object_with_private_attr_when_discovering_fields_then_skips_leading_underscore_names():
	# given
	class Item:
		def __init__(self):
			self.label = "visible"
			self._hidden = "secret"

	items = [Item()]

	# when
	result = discover_fields(items)

	# then
	assert "label" in result
	assert "_hidden" not in result


def test_given_food_items_when_magic_searching_salat_on_name_then_returns_salad(food_items: list[dict[str, str]]):
	# given
	query = "salat"

	# when
	results = magic_search(food_items, query, fields=["name"])

	# then
	assert results
	assert results[0].item["name"] in {"salt", "salad", "salty"}


def test_given_products_when_magic_searching_spatial_on_name_and_description_then_matches(
	products: list[Product],
):
	# given
	query = "spatial"

	# when
	results = magic_search(products, query, fields=["name", "description"])

	# then
	assert results
	assert any("spatial" in result.item.name.lower() for result in results)


def test_given_dict_items_when_magic_searching_with_default_fields_then_discovers_and_matches():
	# given
	items = [
		{"name": "salt", "category": "food"},
		{"name": "salad", "category": "greens"},
	]
	query = "salat"

	# when
	results = magic_search(items, query)

	# then
	assert results
	assert results[0].item["name"] in {"salt", "salad", "salty"}


def test_given_dict_items_when_magic_searching_with_empty_fields_then_discovers_and_matches():
	# given
	items = [
		{"name": "salt", "category": "food"},
		{"name": "salad", "category": "greens"},
	]
	query = "salat"

	# when
	results = magic_search(items, query, fields=[])

	# then
	assert results
	assert results[0].item["name"] in {"salt", "salad", "salty"}


def test_given_people_dataclass_when_magic_searching_with_empty_fields_then_discovers_and_matches():
	# given
	@dataclass
	class Person:
		name: str
		role: str

	items = [
		Person("Alice Chen", "engineer"),
		Person("Bob Jones", "designer"),
	]
	query = "engineer"

	# when
	results = magic_search(items, query, fields=[])

	# then
	assert results
	assert results[0].item.name == "Alice Chen"


def test_given_empty_items_when_magic_searching_then_returns_empty_list():
	# given
	items: list[dict[str, str]] = []

	# when
	results = magic_search(items, "test", fields=[])

	# then
	assert results == []


def test_given_high_threshold_when_magic_searching_weak_match_then_returns_empty(food_items: list[dict[str, str]]):
	# given
	query = "salat"

	# when
	results = magic_search(food_items, query, fields=["name"], threshold=0.95)

	# then
	assert results == []
