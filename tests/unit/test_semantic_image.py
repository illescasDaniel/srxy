from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from srxy.semantic_image import (
	is_semantic_image_path,
	reset_semantic_image_model,
	score_image,
	semantic_image_requested,
)


pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def reset_model():
	reset_semantic_image_model()
	yield
	reset_semantic_image_model()


def test_given_explicit_false_when_requesting_semantic_image_then_returns_false(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_SEMANTIC_IMAGE", "1")

	# when / then
	assert semantic_image_requested(False) is False


def test_given_env_set_when_requesting_semantic_image_then_returns_true(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_SEMANTIC_IMAGE", "1")

	# when / then
	assert semantic_image_requested(None) is True


@patch("srxy.semantic_image._cosine_similarity", return_value=0.82)
@patch("srxy.semantic_image._encode_image")
@patch("srxy.semantic_image.encode_semantic_image_query")
def test_given_mocked_embeddings_when_scoring_image_then_returns_similarity(
	mock_encode_query: MagicMock,
	mock_encode_image: MagicMock,
	_mock_cosine: MagicMock,
	tmp_path: Path,
):
	# given
	image_path = tmp_path / "dog.png"
	image_path.write_bytes(b"png")
	mock_encode_query.return_value = [1.0, 0.0]
	mock_encode_image.return_value = [1.0, 0.0]

	# when
	score = score_image("a dog", image_path)

	# then
	assert score == pytest.approx(0.82)


def test_given_non_image_path_when_scoring_image_then_returns_zero(tmp_path: Path):
	# given
	text_path = tmp_path / "notes.txt"
	text_path.write_text("hello", encoding="utf-8")

	# when / then
	assert score_image("hello", text_path) == 0.0


def test_given_dng_path_when_checking_semantic_image_path_then_returns_true(tmp_path: Path):
	# given
	dng_path = tmp_path / "photo.dng"

	# when / then
	assert is_semantic_image_path(dng_path) is True
