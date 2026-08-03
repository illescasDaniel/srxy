from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from srxy.application.use_cases.search_files import magic_file_search


pytestmark = pytest.mark.unit


def _mock_process_pool(*_args: object, **_kwargs: object):
	pool = MagicMock()
	pool.__enter__.return_value = pool
	pool.__exit__.return_value = False
	pool.submit.return_value = MagicMock(result=lambda: (None, []))
	return pool


def test_given_allow_process_pool_off_when_searching_then_skips_process_pool(tmp_path: Path):
	for index in range(60):
		(tmp_path / f"file{index:03d}.txt").write_text(f"needle {index}\n", encoding="utf-8")

	with patch("concurrent.futures.ProcessPoolExecutor", side_effect=_mock_process_pool) as process_pool:
		results = magic_file_search(
			tmp_path,
			"needle",
			search_names=False,
			allow_process_pool=False,
		)

	assert process_pool.called is False
	assert results


def test_given_allow_process_pool_on_when_searching_large_tree_then_uses_process_pool(tmp_path: Path):
	for index in range(60):
		(tmp_path / f"file{index:03d}.txt").write_text(f"needle {index}\n", encoding="utf-8")

	with (
		patch("concurrent.futures.ProcessPoolExecutor", side_effect=_mock_process_pool) as process_pool,
		patch("concurrent.futures.as_completed", return_value=[]),
	):
		magic_file_search(
			tmp_path,
			"needle",
			search_names=False,
			allow_process_pool=True,
		)

	assert process_pool.called is True


def test_given_cancel_during_listing_when_searching_then_raises(tmp_path: Path):
	root = tmp_path / "tree"
	root.mkdir()
	for index in range(5):
		(root / f"f{index}.txt").write_text("token", encoding="utf-8")

	from srxy.application.search_control import SearchCancelled

	with pytest.raises(SearchCancelled):
		magic_file_search(
			root,
			"token",
			search_names=False,
			cancel_check=lambda: True,
		)
