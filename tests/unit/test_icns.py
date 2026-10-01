"""Tests for pure-Python ``.icns`` packing (macOS 26+ iconutil -c workaround)."""

from __future__ import annotations

from pathlib import Path

import pytest

from srxy.resources.icons import macos_app_icon_path
from srxy.resources.icons.icns import write_icns_from_png


pytestmark = pytest.mark.unit


def test_given_square_png_when_writing_icns_then_file_has_icns_magic(tmp_path: Path):
	# given
	src = macos_app_icon_path()
	out = tmp_path / "srxy.icns"

	# when
	write_icns_from_png(src, out)

	# then
	data = out.read_bytes()
	assert data[:4] == b"icns"
	assert len(data) > 1024
	assert b"ic07" in data  # 128px PNG chunk
	assert b"ic10" in data  # 1024px PNG chunk
