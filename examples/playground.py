"""Local sandbox for trying srxy outside pytest.

Run from the repo root with the dev venv:

    python examples/playground.py

Or install from PyPI and run the playground:

    scripts/test-package
    scripts/test-package --testpypi   # use TestPyPI instead

Edit this file freely — it is not collected by pytest.
"""

from __future__ import annotations

from dataclasses import dataclass

from srxy import FieldConfig, MatchType, Q, SearchResult, magic_file_search, magic_search, search


@dataclass
class Person:
	name: str
	age: int
	role: str = ""


FOOD_ITEMS = [
	{"name": "salt"},
	{"name": "salty"},
	{"name": "salad"},
]

PEOPLE = [
	Person("Alice Chen", 30, "engineer"),
	Person("Bob Jones", 41, "designer"),
	Person("Alicia Smyth", 28, "engineer"),
]


def print_results(label: str, results: list[SearchResult]):
	print(f"\n=== {label} ===")
	if not results:
		print("(no matches)")
		return
	for rank, result in enumerate(results, start=1):
		item = result.item
		if isinstance(item, dict):
			summary = item.get("name", item)
		else:
			summary = getattr(item, "name", item)
		print(f"{rank}. {summary!r}  score={result.score:.3f}")
		if result.breakdown:
			print(f"   breakdown: {result.breakdown}")


def demo_magic_search():
	results = magic_search(PEOPLE, "alicia", fields=["name", "role"])
	print_results("magic_search explicit fields (name | role)", results)

	results = magic_search(PEOPLE, "engineer")
	print_results("magic_search auto-discover all fields (default)", results)


def demo_composite_fuzzy():
	results = search(
		FOOD_ITEMS,
		"salat",
		where=Q.composite("name"),
		threshold=0.3,
	)
	print_results("composite fuzzy (salat → salad)", results)


def demo_dataclass_and_dsl():
	results = search(
		PEOPLE,
		"alicia",
		where=Q.composite("name"),
		threshold=0.4,
	)
	print_results("dataclass + composite name (fuzzy, semantic, phonetic, …)", results)


def demo_field_config():
	results = search(
		PEOPLE,
		"engineer",
		fields=[
			FieldConfig("role", MatchType.EXACT, weight=2.0),
			FieldConfig("name", MatchType.CONTAINS, weight=1.0),
		],
		threshold=0.5,
	)
	print_results("FieldConfig (exact role + contains name)", results)


def demo_nested_boolean():
	items = [
		{"sku": "ABC-123", "barcode": "XYZ-999", "label": "ABC-123"},
		{"sku": "DEF-456", "barcode": "ABC-123", "label": "other"},
	]
	results = search(
		items,
		"ABC-123",
		where=Q.any(Q.exact("sku"), Q.exact("barcode")) & Q.exact("label"),
	)
	print_results("nested AND/OR (sku|barcode) & label", results)


def demo_file_search():
	from pathlib import Path

	repo_root = Path(__file__).resolve().parent.parent
	results = magic_file_search(repo_root / "src" / "srxy", "registry", threshold=0.3)
	print(f"\n=== magic_file_search (registry in src/srxy) ===")
	if not results:
		print("(no matches)")
		return
	for rank, result in enumerate(results[:5], start=1):
		print(f"{rank}. {result.path}  score={result.score:.3f}  breakdown={result.breakdown}")
		for line_match in result.lines[:3]:
			print(f"   line {line_match.line_number}: {line_match.text!r}  score={line_match.score:.3f}")


def main():
	demo_magic_search()
	demo_composite_fuzzy()
	demo_dataclass_and_dsl()
	demo_field_config()
	demo_nested_boolean()
	demo_file_search()


if __name__ == "__main__":
	main()
