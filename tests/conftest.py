from __future__ import annotations

import pytest
from tests.helpers import Product


@pytest.fixture
def food_items() -> list[dict[str, str]]:
	return [
		{"name": "salt"},
		{"name": "salty"},
		{"name": "salad"},
	]


@pytest.fixture
def products() -> list[Product]:
	return [
		Product("spatial analyzer", "tool for spatial data", "software", "active", "spatializer"),
		Product("special offer", "limited time deal", "promo", "active"),
		Product("salad bowl", "fresh greens", "food", "active"),
		Product("inactive tool", "old spatial app", "software", "inactive", "spatial"),
	]
