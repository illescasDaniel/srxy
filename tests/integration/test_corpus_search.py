from __future__ import annotations

import pytest
from tests.helpers import LabeledQuery, top_k_hit_rate

from srxy import Q, SearchResult, magic_search, search


pytestmark = pytest.mark.integration


def test_given_news_corpus_when_composite_search_for_mars_then_ranks_science_article_first(
	search_corpus: list[dict[str, str]],
):
	# given
	query = "mars rover space exploration"
	where = Q.composite("title") | Q.composite("body")

	# when
	results = search(search_corpus, query, where=where, threshold=0.2)

	# then
	assert results
	assert results[0].item["id"] == "sci-mars-rover"
	assert results[0].score >= 0.2


def test_given_news_corpus_when_magic_search_for_mars_on_title_and_body_then_ranks_science_article_first(
	search_corpus: list[dict[str, str]],
):
	# given
	query = "mars rover space exploration"

	# when
	results = magic_search(search_corpus, query, fields=["title", "body"])

	# then
	assert results
	assert results[0].item["id"] == "sci-mars-rover"
	assert results[0].score >= 0.25


def test_given_news_corpus_when_magic_search_with_default_fields_then_ranks_science_article_first(
	search_corpus: list[dict[str, str]],
):
	# given
	query = "mars rover space exploration"

	# when
	results = magic_search(search_corpus, query)

	# then
	assert results
	assert results[0].item["id"] == "sci-mars-rover"
	assert results[0].score >= 0.25


def test_given_labeled_queries_when_magic_search_then_top1_hit_rate_meets_target(
	search_corpus: list[dict[str, str]],
	labeled_queries: list[LabeledQuery],
):
	# given
	results_by_query: list[list[SearchResult]] = []
	expected_ids: list[str] = []

	# when
	for labeled in labeled_queries:
		results = magic_search(search_corpus, labeled.query, fields=["title", "body"])
		results_by_query.append(results)
		expected_ids.append(labeled.expected_id)
	hit_rate = top_k_hit_rate(results_by_query, expected_ids, k=1)

	# then
	assert hit_rate >= 0.7


def test_given_news_corpus_when_composite_search_then_breakdown_includes_all_matchers(
	search_corpus: list[dict[str, str]],
):
	# given
	query = "mars rover space exploration"
	where = Q.composite("title")

	# when
	results = search(search_corpus, query, where=where, threshold=0.0)

	# then
	assert results
	title_breakdown = results[0].breakdown["title"]
	assert set(title_breakdown.keys()) == {
		"fuzzy",
		"semantic",
		"partial",
		"phonetic",
		"contains",
		"exact",
	}


def test_given_news_corpus_when_semantic_search_for_cyber_attack_then_ranks_security_article(
	search_corpus: list[dict[str, str]],
):
	# given
	query = "hackers stole customer data from cloud storage"
	where = Q.semantic("title") | Q.semantic("body")

	# when
	results = search(search_corpus, query, where=where, threshold=0.35)

	# then
	assert results
	top_ids = [result.item["id"] for result in results[:3]]
	assert "tech-cyber-breach" in top_ids


def test_given_news_corpus_when_phonetic_search_for_smith_name_then_finds_phonetic_match():
	# given
	items = [
		{"id": "person-smyth", "name": "Smyth", "bio": "Engineer"},
		{"id": "person-jones", "name": "Jones", "bio": "Designer"},
	]
	where = Q.phonetic("name")

	# when
	results = search(items, "smith", where=where)

	# then
	assert results
	assert results[0].item["id"] == "person-smyth"


def test_given_labeled_queries_when_composite_search_then_top1_hit_rate_meets_target(
	search_corpus: list[dict[str, str]],
	labeled_queries: list[LabeledQuery],
):
	# given
	where = Q.composite("title") | Q.composite("body")
	results_by_query: list[list[SearchResult]] = []
	expected_ids: list[str] = []

	# when
	for labeled in labeled_queries:
		results = search(search_corpus, labeled.query, where=where, threshold=0.15)
		results_by_query.append(results)
		expected_ids.append(labeled.expected_id)
	hit_rate = top_k_hit_rate(results_by_query, expected_ids, k=1)

	# then
	assert hit_rate >= 0.7


def test_given_labeled_queries_when_composite_search_then_top3_hit_rate_meets_target(
	search_corpus: list[dict[str, str]],
	labeled_queries: list[LabeledQuery],
):
	# given
	where = Q.composite("title") | Q.composite("body")
	results_by_query: list[list[SearchResult]] = []
	expected_ids: list[str] = []

	# when
	for labeled in labeled_queries:
		results = search(search_corpus, labeled.query, where=where, threshold=0.15)
		results_by_query.append(results)
		expected_ids.append(labeled.expected_id)
	hit_rate = top_k_hit_rate(results_by_query, expected_ids, k=3)

	# then
	assert hit_rate >= 0.9


def test_given_labeled_queries_when_measuring_expected_item_scores_then_meet_minimum_threshold(
	search_corpus: list[dict[str, str]],
	labeled_queries: list[LabeledQuery],
):
	# given
	where = Q.composite("title") | Q.composite("body")
	scores_for_expected: list[float] = []

	# when
	for labeled in labeled_queries:
		results = search(search_corpus, labeled.query, where=where, threshold=0.0)
		score_map = {result.item["id"]: result.score for result in results}
		scores_for_expected.append(score_map.get(labeled.expected_id, 0.0))
	mean_score = sum(scores_for_expected) / len(scores_for_expected)

	# then
	assert mean_score >= 0.25
	assert all(
		score >= labeled.min_top_score for score, labeled in zip(scores_for_expected, labeled_queries, strict=True)
	)


def test_given_technology_category_when_searching_exact_category_then_returns_only_technology_rows(
	search_corpus: list[dict[str, str]],
):
	# given
	query = "technology"
	where = Q.exact("category")

	# when
	results = search(search_corpus, query, where=where)

	# then
	assert len(results) == 3
	assert all(result.item["category"] == "technology" for result in results)


def test_given_fuzzy_title_field_when_searching_misspelled_football_then_finds_sports_article(
	search_corpus: list[dict[str, str]],
):
	# given
	query = "footbal championship"
	where = Q.fuzzy("title")

	# when
	results = search(search_corpus, query, where=where, threshold=0.5)

	# then
	assert results
	assert results[0].item["id"] == "sport-football-final"
