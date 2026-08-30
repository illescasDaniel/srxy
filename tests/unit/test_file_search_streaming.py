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


def test_given_heavy_thread_pool_when_listing_finishes_then_progress_includes_zero_of_total(
	tmp_path: Path,
):
	"""Catch-up must emit 0/N so the UI can show counts before slow OCR returns."""
	import threading
	from unittest.mock import patch

	paths = [tmp_path / "a.png", tmp_path / "b.png"]
	for path in paths:
		path.write_bytes(b"png")
	walker = _FakeWalker(paths)
	progress_calls: list[tuple[int, int]] = []
	release = threading.Event()

	def on_progress(current: int, total: int):
		progress_calls.append((current, total))
		if current == 0 and total == 2:
			release.set()

	def blocked_score(*_args, **_kwargs) -> float:
		if not release.wait(timeout=5):
			raise TimeoutError("progress catch-up never released workers")
		return 0.0

	with (
		patch("srxy.adapters.outbound.content.image_similarity.is_semantic_image_active", return_value=True),
		patch("srxy.application.use_cases.search_files.encode_semantic_image_query", return_value=[1.0, 0.0]),
		patch("srxy.application.use_cases.search_files.score_image", side_effect=blocked_score),
	):
		FileSearchUseCase(file_walker=walker).search(
			tmp_path,
			"sunset",
			search_names=False,
			search_contents=True,
			search_docs_tags=False,
			semantic_image=True,
			on_progress=on_progress,
			max_workers=2,
		)

	assert progress_calls[0] == (0, 2)
	assert progress_calls[-1] == (2, 2)


def test_given_heavy_thread_pool_when_scoring_images_then_emits_per_file_clip_activity(
	tmp_path: Path,
):
	from unittest.mock import patch

	(tmp_path / "left.png").write_bytes(b"png")
	(tmp_path / "right.png").write_bytes(b"png")
	activities: list[ActivityUpdate | None] = []

	with (
		patch("srxy.adapters.outbound.content.image_similarity.is_semantic_image_active", return_value=True),
		patch("srxy.application.use_cases.search_files.encode_semantic_image_query", return_value=[1.0, 0.0]),
		patch("srxy.application.use_cases.search_files.score_image", return_value=0.5),
	):
		FileSearchUseCase().search(
			tmp_path,
			"sunset",
			search_names=False,
			search_contents=True,
			search_docs_tags=False,
			semantic_image=True,
			on_activity=activities.append,
			max_workers=2,
		)

	labels = {activity.label for activity in activities if activity is not None}
	assert "CLIP · left.png" in labels or "CLIP · right.png" in labels
	assert activities[-1] is None


def test_given_heavy_pool_when_mixed_light_and_heavy_then_text_result_not_blocked_by_image(
	tmp_path: Path,
):
	"""Plain-text files must score inline — never FIFO-queued behind in-flight CLIP/OCR."""
	import threading
	from unittest.mock import patch

	image_path = tmp_path / "photo.png"
	text_path = tmp_path / "notes.txt"
	image_path.write_bytes(b"png")
	text_path.write_text("needle in haystack\n", encoding="utf-8")
	# Heavy file first so a FIFO-all-files pool would stall the text file.
	walker = _FakeWalker([image_path, text_path])
	release = threading.Event()
	text_seen = threading.Event()
	seen: list[str] = []

	def on_result(result: FileSearchResult):
		seen.append(result.path.name)
		if result.path.name == "notes.txt":
			text_seen.set()

	def blocked_score(*_args, **_kwargs) -> float:
		# Wait until the light file has already produced a result — proves
		# text search did not sit behind this heavy future in the pool queue.
		if not text_seen.wait(timeout=5):
			raise TimeoutError("light text result never arrived while CLIP was blocked")
		release.set()
		return 0.9

	with (
		patch("srxy.adapters.outbound.content.image_similarity.is_semantic_image_active", return_value=True),
		patch("srxy.application.use_cases.search_files.encode_semantic_image_query", return_value=[1.0, 0.0]),
		patch("srxy.application.use_cases.search_files.score_image", side_effect=blocked_score),
	):
		results = FileSearchUseCase(file_walker=walker).search(
			tmp_path,
			"needle",
			search_names=False,
			search_contents=True,
			search_docs_tags=True,
			semantic_image=True,
			on_result=on_result,
			max_workers=2,
			threshold=0.3,
			semantic_image_threshold=0.3,
		)

	assert "notes.txt" in seen
	assert seen[0] == "notes.txt"
	assert release.is_set()
	assert any(result.path.name == "notes.txt" for result in results)
