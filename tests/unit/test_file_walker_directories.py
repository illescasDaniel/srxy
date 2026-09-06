from __future__ import annotations

from pathlib import Path

import pytest

from srxy.adapters.outbound.content.file_walker import collect_files, iter_files


pytestmark = pytest.mark.unit


def test_given_nested_tree_when_include_directories_then_yields_subdirectories(tmp_path: Path):
	# given
	(tmp_path / "Invoices").mkdir()
	(tmp_path / "Invoices" / "jan.txt").write_text("x", encoding="utf-8")
	(tmp_path / "Photos").mkdir()
	(tmp_path / "notes.txt").write_text("x", encoding="utf-8")

	# when
	paths = collect_files(tmp_path, include_directories=True)

	# then
	assert tmp_path / "Invoices" in paths
	assert tmp_path / "Photos" in paths
	assert tmp_path / "Invoices" / "jan.txt" in paths
	assert tmp_path / "notes.txt" in paths


def test_given_default_when_include_directories_omitted_then_no_directories_yielded(tmp_path: Path):
	# given
	(tmp_path / "Invoices").mkdir()
	(tmp_path / "notes.txt").write_text("x", encoding="utf-8")

	# when
	paths = collect_files(tmp_path)

	# then
	assert paths == [tmp_path / "notes.txt"]


def test_given_search_root_when_include_directories_then_root_itself_is_not_yielded(tmp_path: Path):
	# given
	(tmp_path / "child").mkdir()

	# when
	paths = collect_files(tmp_path, include_directories=True)

	# then
	assert tmp_path not in paths
	assert tmp_path / "child" in paths


def test_given_hidden_directory_when_include_directories_then_skips_hidden_dir_by_default(tmp_path: Path):
	# given
	(tmp_path / ".git").mkdir()
	(tmp_path / "visible").mkdir()

	# when
	paths = collect_files(tmp_path, include_directories=True, skip_hidden_folders=True)

	# then
	assert tmp_path / ".git" not in paths
	assert tmp_path / "visible" in paths


def test_given_hidden_directory_when_skip_hidden_folders_disabled_then_includes_hidden_dir(tmp_path: Path):
	# given
	(tmp_path / ".git").mkdir()

	# when
	paths = collect_files(tmp_path, include_directories=True, skip_hidden_folders=False)

	# then
	assert tmp_path / ".git" in paths


def test_given_noise_directory_when_include_directories_then_skips_noise_dir_by_default(tmp_path: Path):
	# given
	(tmp_path / "node_modules").mkdir()
	(tmp_path / "visible").mkdir()

	# when
	paths = collect_files(tmp_path, include_directories=True, skip_noise_folders=True)

	# then
	assert tmp_path / "node_modules" not in paths
	assert tmp_path / "visible" in paths


def test_given_noise_directory_when_skip_noise_folders_disabled_then_includes_noise_dir(tmp_path: Path):
	# given
	(tmp_path / "node_modules").mkdir()

	# when
	paths = collect_files(tmp_path, include_directories=True, skip_noise_folders=False)

	# then
	assert tmp_path / "node_modules" in paths


def test_given_subdirectories_disabled_when_include_directories_then_still_yields_top_level_dirs(
	tmp_path: Path,
):
	# given — no recursion, but the immediate children of root are still visible.
	top = tmp_path / "top"
	top.mkdir()
	nested = top / "nested"
	nested.mkdir()

	# when
	paths = collect_files(tmp_path, include_directories=True, include_subdirectories=False)

	# then
	assert tmp_path / "top" in paths
	assert nested not in paths


def test_given_match_skipped_names_when_include_directories_then_includes_noise_dir_names(
	tmp_path: Path,
):
	# given
	(tmp_path / "node_modules").mkdir()

	# when
	paths = collect_files(
		tmp_path,
		include_directories=True,
		skip_noise_folders=True,
		match_skipped_names=True,
	)

	# then
	assert tmp_path / "node_modules" in paths


def test_given_cancel_check_when_include_directories_then_raises_search_cancelled(tmp_path: Path):
	from srxy.application.search_control import SearchCancelled

	# given
	(tmp_path / "one").mkdir()
	(tmp_path / "two").mkdir()

	def cancel_check() -> bool:
		return True

	# when / then
	with pytest.raises(SearchCancelled):
		list(iter_files(tmp_path, include_directories=True, cancel_check=cancel_check))
