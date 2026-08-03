from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from srxy.adapters.outbound.content.file_walker import iter_files
from srxy.application.search_control import SearchCancelled


pytestmark = pytest.mark.unit


def test_given_cancel_during_listing_when_iter_files_then_raises(tmp_path: Path):
	root = tmp_path / "tree"
	root.mkdir()
	for index in range(5):
		(root / f"f{index}.txt").write_text("x", encoding="utf-8")

	def cancel_check():
		return True

	with pytest.raises(SearchCancelled):
		list(iter_files(root, cancel_check=cancel_check))


def test_given_root_path_when_iter_files_then_skips_pseudo_filesystems():
	def fake_walk(root: str):
		yield root, ["proc", "home", "sys"], []
		yield str(Path(root) / "home"), [], ["notes.txt"]

	with patch("srxy.adapters.outbound.content.file_walker.os.walk", side_effect=fake_walk):
		paths = list(iter_files(Path("/")))

	assert paths == [Path("/home/notes.txt")]
