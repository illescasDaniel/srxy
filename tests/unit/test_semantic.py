from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from srxy.matchers.semantic import SemanticMatcher, reset_semantic_model


pytestmark = [pytest.mark.unit, pytest.mark.semantic, pytest.mark.usefixtures("mock_semantic_model")]


def setup_function():
	reset_semantic_model()


def teardown_function():
	reset_semantic_model()


def test_given_empty_query_when_semantic_matching_then_returns_zero():
	# given
	matcher = SemanticMatcher()
	query = ""
	value = "hello"

	# when
	score = matcher.score(query, value)

	# then
	assert score == 0.0


@patch("srxy.matchers.semantic._cosine_similarity", return_value=0.85)
@patch("srxy.matchers.semantic._get_model")
def test_given_mocked_embeddings_when_semantic_matching_then_uses_cosine_similarity(
	mock_get_model: MagicMock,
	_mock_cosine: MagicMock,
):
	# given
	mock_model = MagicMock()
	mock_model.encode.side_effect = lambda text: [1.0, 0.0]
	mock_get_model.return_value = mock_model
	matcher = SemanticMatcher()

	# when
	score = matcher.score("hello", "hi")

	# then
	assert score == pytest.approx(0.85)
	assert mock_model.encode.call_count == 2


@patch("srxy.matchers.semantic._cosine_similarity")
@patch("srxy.matchers.semantic._get_model")
def test_given_out_of_range_cosine_values_when_semantic_matching_then_clamps_to_unit_interval(
	mock_get_model: MagicMock,
	mock_cosine: MagicMock,
):
	# given
	mock_model = MagicMock()
	mock_model.encode.side_effect = lambda text: [1.0]
	mock_get_model.return_value = mock_model
	matcher = SemanticMatcher()

	# when
	mock_cosine.return_value = 1.5
	high_score = matcher.score("a", "b")
	mock_cosine.return_value = -0.5
	low_score = matcher.score("a", "b")

	# then
	assert high_score == 1.0
	assert low_score == 0.0
