from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from srxy.application.search_control import SearchCancelled
from srxy.application.use_cases.search_files import FileSearchUseCase
from srxy.domain.models import FileSearchResult, SkippedFile
from srxy.domain.progress import ActivityUpdate


pytestmark = pytest.mark.unit


class _FakeWalker:
	"""Deterministic walker that marks when the generator is exhausted."""

	def __init__(self, paths: list[Path]):
		self._paths = paths
		self.exhausted = False
		self.yielded = 0

	def iter_files(
		self,
		root: Path,
		*,
		skip_hidden_folders: bool = True,
		skip_noise_folders: bool = True,
		skip_noise_files: bool = True,
		match_skipped_names: bool = False,
		include_archives: bool = False,
		include_subdirectories: bool = True,
		cancel_check: Callable[[], bool] | None = None,
		skipped_files: list[SkippedFile] | None = None,
	) -> Iterator[Path]:
		_ = (
			root,
			skip_hidden_folders,
			skip_noise_folders,
			skip_noise_files,
			match_skipped_names,
			include_archives,
			include_subdirectories,
			skipped_files,
		)
		for path in self._paths:
			if cancel_check is not None and cancel_check():
				raise SearchCancelled()
			self.yielded += 1
			yield path
		self.exhausted = True

	def collect_files(
		self,
		root: Path,
		*,
		skip_hidden_folders: bool = True,
		skip_noise_folders: bool = True,
		skip_noise_files: bool = True,
		match_skipped_names: bool = False,
		include_archives: bool = False,
		include_subdirectories: bool = True,
		cancel_check: Callable[[], bool] | None = None,
		skipped_files: list[SkippedFile] | None = None,
	) -> list[Path]:
		return list(
			self.iter_files(
				root,
				skip_hidden_folders=skip_hidden_folders,
				skip_noise_folders=skip_noise_folders,
				skip_noise_files=skip_noise_files,
				match_skipped_names=match_skipped_names,
				include_archives=include_archives,
				include_subdirectories=include_subdirectories,
				cancel_check=cancel_check,
				skipped_files=skipped_files,
			)
		)

	def is_searchable(self, path: Path) -> bool:
		_ = path
		return True

	def is_archive_member(self, path: Path) -> bool:
		_ = path
		return False


def test_given_streaming_walk_when_searching_then_results_arrive_before_walk_finishes(tmp_path: Path):
	# given
	alpha = tmp_path / "alpha.txt"
	beta = tmp_path / "beta.txt"
	gamma = tmp_path / "gamma.txt"
	alpha.write_text("hello", encoding="utf-8")
	beta.write_text("revenue report", encoding="utf-8")
	gamma.write_text("goodbye", encoding="utf-8")
	walker = _FakeWalker([alpha, beta, gamma])
	streamed_before_exhaust: list[str] = []

	def on_result(result: FileSearchResult):
		assert walker.exhausted is False
		streamed_before_exhaust.append(result.path.name)

	# when
	results = FileSearchUseCase(file_walker=walker).search(
		tmp_path,
		"revenue",
		search_names=False,
		on_result=on_result,
	)

	# then
	assert walker.exhausted is True
	assert streamed_before_exhaust == ["beta.txt"]
	assert [item.path.name for item in results] == ["beta.txt"]


def test_given_streaming_walk_when_searching_then_progress_only_after_listing_completes(tmp_path: Path):
	# given
	paths = [tmp_path / f"f{index}.txt" for index in range(4)]
	for path in paths:
		path.write_text("token\n", encoding="utf-8")
	walker = _FakeWalker(paths)
	progress_calls: list[tuple[int, int]] = []

	def on_progress(current: int, total: int):
		assert walker.exhausted is True
		progress_calls.append((current, total))

	# when
	FileSearchUseCase(file_walker=walker).search(
		tmp_path,
		"token",
		search_names=False,
		on_progress=on_progress,
	)

	# then
	assert progress_calls == [(4, 4)]


def test_given_streaming_walk_when_cancelled_midway_then_keeps_partial_results(tmp_path: Path):
	# given
	paths = [tmp_path / f"f{index}.txt" for index in range(5)]
	for path in paths:
		path.write_text("token\n", encoding="utf-8")
	walker = _FakeWalker(paths)
	seen: list[str] = []

	def cancel_check() -> bool:
		return len(seen) >= 2

	def on_result(result: FileSearchResult):
		seen.append(result.path.name)

	# when / then
	with pytest.raises(SearchCancelled) as raised:
		FileSearchUseCase(file_walker=walker).search(
			tmp_path,
			"token",
			search_names=False,
			on_result=on_result,
			cancel_check=cancel_check,
		)

	assert len(seen) >= 2
	assert len(raised.value.results) >= 2
	assert walker.exhausted is False


def test_given_streaming_search_when_reporting_activity_then_uses_searching_not_listing(tmp_path: Path):
	# given
	(tmp_path / "notes.txt").write_text("needle\n", encoding="utf-8")
	activities: list[ActivityUpdate | None] = []

	# when
	FileSearchUseCase().search(
		tmp_path,
		"needle",
		search_names=False,
		on_activity=activities.append,
	)

	# then
	labels = [activity.label for activity in activities if activity is not None]
	assert "Searching…" in labels
	assert "Listing files…" not in labels
	assert activities[-1] is None
