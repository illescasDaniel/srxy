from __future__ import annotations

import argparse
import json
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from srxy.adapters.outbound.content.text_extractor import DefaultTextExtractor
from srxy.adapters.outbound.worker.search_worker import args_to_payload
from srxy.application.search_filters import ignore_spec_from_args
from srxy.application.use_cases.search_files import FileSearchUseCase, magic_file_search
from srxy.domain.ignore_rules import IgnoreSpec
from srxy.domain.models import SkippedFile
from srxy.domain.progress import ActivityCallback
from srxy.domain.text_unit import TextUnit


pytestmark = pytest.mark.unit

_IGNORED_FILE_COUNT = 40


class _SpyExtractor(DefaultTextExtractor):
	"""Yields one matching line for every file and records which paths were read."""

	def __init__(self):
		self.paths: list[Path] = []

	def iter_units(
		self,
		path: Path,
		max_file_size: int | None,
		*,
		search_docs_tags: bool = True,
		ocr: bool | None = None,
		transcribe: bool | None = None,
		skipped_files: list[SkippedFile] | None = None,
		on_activity: ActivityCallback | None = None,
	) -> Iterator[TextUnit]:
		_ = (max_file_size, search_docs_tags, ocr, transcribe, skipped_files, on_activity)
		self.paths.append(path)
		yield TextUnit(line_number=1, text="axolotl habitat", location_kind="line")


class _RecordingWalker:
	"""Fake FileWalkerPort over a fixed path list; drops any path under a folder named by an ignore pattern."""

	def __init__(self, paths: list[Path]):
		self._paths = paths
		self.calls: list[tuple[bool, IgnoreSpec | None]] = []
		self._lock = threading.Lock()

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
		include_directories: bool = False,
		cancel_check: Callable[[], bool] | None = None,
		skipped_files: list[SkippedFile] | None = None,
		ignore: IgnoreSpec | None = None,
	) -> Iterator[Path]:
		_ = (
			skip_hidden_folders,
			skip_noise_folders,
			skip_noise_files,
			match_skipped_names,
			include_archives,
			include_subdirectories,
			include_directories,
			cancel_check,
			skipped_files,
		)
		is_probe = threading.current_thread().name == "srxy-file-count-probe"
		with self._lock:
			self.calls.append((is_probe, ignore))
		folders = {p.rstrip("/") for p in (ignore.patterns if ignore is not None else ())}
		for path in self._paths:
			if folders.intersection(path.relative_to(root).parts[:-1]):
				continue
			yield path

	def collect_files(self, root: Path, **kwargs: Any) -> list[Path]:
		return list(self.iter_files(root, **kwargs))

	def is_searchable(self, path: Path) -> bool:
		_ = path
		return True

	def is_archive_member(self, path: Path) -> bool:
		_ = path
		return False


class _LegacyWalker:
	"""A 1.7-era walker whose methods do not know about ``ignore`` at all."""

	def __init__(self, paths: list[Path]):
		self._paths = paths
		self.calls = 0

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
		include_directories: bool = False,
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
			include_directories,
			cancel_check,
			skipped_files,
		)
		self.calls += 1
		yield from self._paths

	def collect_files(self, root: Path, **kwargs: Any) -> list[Path]:
		return list(self.iter_files(root, **kwargs))

	def is_searchable(self, path: Path) -> bool:
		_ = path
		return True

	def is_archive_member(self, path: Path) -> bool:
		_ = path
		return False


def _make_tree(root: Path) -> tuple[list[Path], list[Path]]:
	"""Return (kept, ignored) paths; ignored ones live under ``build/``."""
	kept = [root / "a.txt", root / "src" / "b.txt"]
	ignored = [root / "build" / f"gen{i}.txt" for i in range(_IGNORED_FILE_COUNT)]
	for path in [*kept, *ignored]:
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text("axolotl habitat", encoding="utf-8")
	return kept, ignored


def _search_args(path: Path) -> argparse.Namespace:
	from srxy.adapters.inbound.cli.cli import build_parser

	return build_parser().parse_args(["axolotl", str(path), "--cli"])


def test_given_ignored_folder_when_searching_then_progress_total_excludes_ignored_files(tmp_path: Path):
	# given
	kept, _ignored = _make_tree(tmp_path)
	progress: list[tuple[int, int]] = []

	# when
	magic_file_search(
		tmp_path,
		"axolotl",
		search_names=False,
		search_folders=False,
		threshold=0.3,
		max_workers=1,
		on_progress=lambda done, total: progress.append((done, total)),
		ignore=IgnoreSpec(patterns=("build/",)),
	)

	# then
	assert progress
	assert {total for _done, total in progress} == {len(kept)}
	assert progress[-1] == (len(kept), len(kept))


def test_given_ignored_folder_when_searching_then_extractor_never_sees_ignored_paths(tmp_path: Path):
	# given
	kept, ignored = _make_tree(tmp_path)
	spy = _SpyExtractor()

	# when
	FileSearchUseCase(text_extractor=spy).search(
		tmp_path,
		"axolotl",
		search_names=False,
		search_folders=False,
		threshold=0.3,
		max_workers=1,
		ignore=IgnoreSpec(patterns=("build/",)),
	)

	# then
	assert sorted(spy.paths) == sorted(kept)
	assert not set(spy.paths) & set(ignored)


def test_given_ignored_folder_when_searching_then_results_never_contain_ignored_paths(tmp_path: Path):
	# given
	kept, ignored = _make_tree(tmp_path)
	streamed: list[Path] = []

	# when
	results = magic_file_search(
		tmp_path,
		"axolotl",
		search_names=True,
		search_folders=True,
		threshold=0.3,
		max_workers=1,
		on_result=lambda result: streamed.append(result.path),
		ignore=IgnoreSpec(patterns=("build/",)),
	)

	# then
	found = {result.path for result in results}
	assert found == set(kept)
	assert not (found | set(streamed)) & (set(ignored) | {tmp_path / "build"})


def test_given_ignored_folder_and_process_pool_allowed_when_searching_then_ignored_paths_are_not_submitted(
	tmp_path: Path,
):
	# given
	kept, ignored = _make_tree(tmp_path)

	# when
	results = magic_file_search(
		tmp_path,
		"axolotl",
		search_names=False,
		search_folders=False,
		threshold=0.3,
		allow_process_pool=True,
		ignore=IgnoreSpec(patterns=("build/",)),
	)

	# then
	found = {result.path for result in results}
	assert found == set(kept)
	assert not found & set(ignored)


def test_given_ignore_spec_when_searching_then_probe_and_listing_walks_receive_the_same_spec(tmp_path: Path):
	# given
	kept, ignored = _make_tree(tmp_path)
	walker = _RecordingWalker([*kept, *ignored])
	spec = IgnoreSpec(patterns=("build/",), respect_gitignore=True)
	progress: list[tuple[int, int]] = []

	# when
	FileSearchUseCase(text_extractor=_SpyExtractor(), file_walker=walker).search(
		tmp_path,
		"axolotl",
		search_names=False,
		search_folders=False,
		threshold=0.3,
		max_workers=1,
		on_progress=lambda done, total: progress.append((done, total)),
		ignore=spec,
	)

	# then
	assert {is_probe for is_probe, _ in walker.calls} == {True, False}
	assert all(received == spec for _is_probe, received in walker.calls)
	assert progress[-1] == (len(kept), len(kept))


def test_given_no_ignore_when_searching_then_walker_without_ignore_parameter_still_works(tmp_path: Path):
	# given
	kept, ignored = _make_tree(tmp_path)
	walker = _LegacyWalker([*kept, *ignored])
	spy = _SpyExtractor()

	# when
	results = FileSearchUseCase(text_extractor=spy, file_walker=walker).search(
		tmp_path, "axolotl", search_names=False, search_folders=False, threshold=0.3, max_workers=1
	)

	# then
	assert walker.calls >= 2  # probe + listing, called exactly as in 1.7
	assert {result.path for result in results} == {*kept, *ignored}


@pytest.mark.parametrize("empty", [None, IgnoreSpec()])
def test_given_empty_ignore_when_searching_then_every_file_is_searched_as_in_1_7(
	tmp_path: Path, empty: IgnoreSpec | None
):
	# given
	kept, ignored = _make_tree(tmp_path)
	spy = _SpyExtractor()

	# when
	FileSearchUseCase(text_extractor=spy).search(
		tmp_path,
		"axolotl",
		search_names=False,
		search_folders=False,
		threshold=0.3,
		max_workers=1,
		ignore=empty,
	)

	# then
	assert sorted(spy.paths) == sorted([*kept, *ignored])


def test_given_ignored_folder_when_searching_names_then_ignored_file_names_never_match(tmp_path: Path):
	# given
	(tmp_path / "build").mkdir()
	(tmp_path / "build" / "quokka_notes.txt").write_text("x", encoding="utf-8")
	(tmp_path / "build" / "nested").mkdir()
	(tmp_path / "build" / "nested" / "quokka_more.txt").write_text("x", encoding="utf-8")
	(tmp_path / "quokka_keep.txt").write_text("x", encoding="utf-8")
	(tmp_path / "quokka_debug.log").write_text("x", encoding="utf-8")

	# when
	results = magic_file_search(
		tmp_path,
		"quokka",
		search_names=True,
		search_folders=True,
		search_contents=False,
		threshold=0.3,
		match_skipped_names=True,
		max_workers=1,
		ignore=IgnoreSpec(patterns=("build/", "*.log")),
	)

	# then
	assert {result.path for result in results} == {tmp_path / "quokka_keep.txt"}


def test_given_ignore_args_when_executing_search_then_use_case_gets_equivalent_ignore_spec(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	from srxy.application import search_runner
	from srxy.application.use_cases import search_files

	captured: dict[str, Any] = {}

	def fake_search(*_args: Any, **kwargs: Any):
		captured.update(kwargs)
		return []

	monkeypatch.setattr(search_files, "magic_file_search", fake_search)
	args = _search_args(tmp_path)
	args.ignore = ["build/", "*.log", "!keep.log"]
	args.respect_gitignore = True

	# when
	search_runner.execute_search(args)

	# then
	assert captured["ignore"] == IgnoreSpec(patterns=("build/", "*.log", "!keep.log"), respect_gitignore=True)


def test_given_no_ignore_args_when_executing_search_then_use_case_gets_no_ignore(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	from srxy.application import search_runner
	from srxy.application.use_cases import search_files

	captured: dict[str, Any] = {}

	def fake_search(*_args: Any, **kwargs: Any):
		captured.update(kwargs)
		return []

	monkeypatch.setattr(search_files, "magic_file_search", fake_search)
	args = _search_args(tmp_path)
	args.ignore = []
	args.respect_gitignore = False

	# when
	search_runner.execute_search(args)

	# then
	assert not captured.get("ignore")


def test_given_ignore_args_when_round_tripping_worker_payload_then_same_ignore_spec(tmp_path: Path):
	# given
	args = _search_args(tmp_path)
	args.ignore = ["build/", "# not a comment\\#x", "!keep.log", "naïve*"]
	args.respect_gitignore = True
	expected = IgnoreSpec(patterns=("build/", "# not a comment\\#x", "!keep.log", "naïve*"), respect_gitignore=True)

	# when
	line = json.dumps(args_to_payload(args), ensure_ascii=False)
	revived = argparse.Namespace(**json.loads(line))

	# then
	assert ignore_spec_from_args(args) == expected
	assert ignore_spec_from_args(revived) == expected


def test_given_args_without_ignore_fields_when_building_spec_then_none():
	# given
	args = argparse.Namespace()

	# when
	spec = ignore_spec_from_args(args)

	# then
	assert spec is None
