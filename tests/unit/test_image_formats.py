from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from srxy.image_formats import (
	is_raw_image_path,
	is_semantic_image_path,
	open_image_for_vision,
)


pytestmark = pytest.mark.unit


def test_given_dng_path_when_checking_semantic_image_path_then_returns_true(tmp_path: Path):
	# given
	dng_path = tmp_path / "photo.dng"

	# when / then
	assert is_semantic_image_path(dng_path) is True
	assert is_raw_image_path(dng_path) is True


def test_given_png_path_when_checking_raw_path_then_returns_false(tmp_path: Path):
	# given
	png_path = tmp_path / "photo.png"

	# when / then
	assert is_semantic_image_path(png_path) is True
	assert is_raw_image_path(png_path) is False


@patch("srxy.image_formats._open_raw_image")
@patch("srxy.image_formats.rawpy_available", return_value=True)
def test_given_raw_path_when_opening_for_vision_then_uses_raw_decoder(
	mock_rawpy_available: MagicMock,
	mock_open_raw: MagicMock,
	tmp_path: Path,
):
	# given
	raw_path = tmp_path / "photo.dng"
	raw_path.write_bytes(b"dng")
	mock_image = MagicMock()
	mock_open_raw.return_value = mock_image

	# when
	with open_image_for_vision(raw_path) as image:
		# then
		assert image is mock_image

	mock_open_raw.assert_called_once_with(raw_path)
	mock_image.close.assert_called_once()


@patch("srxy.image_formats.rawpy_available", return_value=False)
def test_given_raw_path_without_rawpy_when_opening_for_vision_then_raises(tmp_path: Path):
	# given
	raw_path = tmp_path / "photo.dng"
	raw_path.write_bytes(b"dng")

	# when / then
	with pytest.raises(OSError, match="rawpy"):
		with open_image_for_vision(raw_path):
			pass
