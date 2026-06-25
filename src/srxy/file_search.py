from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from srxy.document_text import is_document_path, iter_document_lines
from srxy.matchers.composite import CompositeMatcher
from srxy.models import FileSearchResult, LineMatch, SkippedFile
from srxy.utils import normalize_text


_NOISE_DIR_NAMES = frozenset({"__pycache__", "node_modules"})
_TEXT_SAMPLE_SIZE = 8192


def _is_hidden_path_part(name: str) -> bool:
	return name.startswith(".")


def _should_skip_dirname(
	name: str,
	*,
	skip_hidden_folders: bool,
	skip_noise_folders: bool,
) -> bool:
	if skip_hidden_folders and _is_hidden_path_part(name):
		return True
	if skip_noise_folders and name in _NOISE_DIR_NAMES:
		return True
	return False


def _iter_files(
	root: Path,
	*,
	skip_hidden_folders: bool = True,
	skip_noise_folders: bool = True,
) -> Iterator[Path]:
	if root.is_file():
		yield root
		return
	if not root.is_dir():
		return

	for dirpath, dirnames, filenames in os.walk(root):
		dirnames[:] = [
			name
			for name in dirnames
			if not _should_skip_dirname(
				name,
				skip_hidden_folders=skip_hidden_folders,
				skip_noise_folders=skip_noise_folders,
			)
		]
		current = Path(dirpath)
		for filename in filenames:
			if skip_hidden_folders and _is_hidden_path_part(filename):
				continue
			yield current / filename


def content_location_kind(path: Path) -> str:
	suffix = path.suffix.lower()
	if suffix == ".pdf":
		return "page"
	if suffix == ".docx":
		return "paragraph"
	if suffix == ".xlsx":
		return "row"
	if suffix == ".pptx":
		return "slide"
	return "line"


def suggest_max_file_size(file_size_bytes: int) -> int:
	chunk = 1_048_576
	return max(file_size_bytes + 1, ((file_size_bytes // chunk) + 1) * chunk)


def _file_within_size_limit(path: Path, max_file_size: int | None) -> bool:
	try:
		size = path.stat().st_size
	except OSError:
		return False
	if size == 0:
		return True
	if max_file_size is not None and size > max_file_size:
		return False
	return True


def _is_probably_text(path: Path, max_file_size: int | None) -> bool:
	if not _file_within_size_limit(path, max_file_size):
		return False
	try:
		size = path.stat().st_size
	except OSError:
		return False
	with path.open("rb") as handle:
		sample = handle.read(min(_TEXT_SAMPLE_SIZE, size))
	return b"\x00" not in sample


def _iter_utf8_lines(path: Path, max_file_size: int | None) -> Iterator[tuple[int, str]]:
	bytes_read = 0
	with path.open(encoding="utf-8", errors="ignore") as handle:
		for line_number, raw_line in enumerate(handle, start=1):
			if max_file_size is not None:
				bytes_read += len(raw_line.encode("utf-8", errors="ignore"))
				if bytes_read > max_file_size:
					break
			yield line_number, raw_line.rstrip("\n\r")


def _iter_searchable_lines(path: Path, max_file_size: int | None) -> Iterator[tuple[int, str]]:
	if not _file_within_size_limit(path, max_file_size):
		return
	if is_document_path(path):
		yield from iter_document_lines(path)
		return
	if not _is_probably_text(path, max_file_size):
		return
	yield from _iter_utf8_lines(path, max_file_size)


def _score_name(matcher: CompositeMatcher, query: str, file_path: Path, root: Path) -> float:
	name_score = matcher.score(query, file_path.name)
	try:
		relative_path = file_path.relative_to(root).as_posix()
	except ValueError:
		relative_path = file_path.as_posix()
	path_score = matcher.score(query, relative_path)
	return max(name_score, path_score)


def _score_lines(
	matcher: CompositeMatcher,
	query: str,
	file_path: Path,
	max_file_size: int | None,
	line_threshold: float,
	max_line_matches: int,
) -> tuple[float, list[LineMatch]]:
	matches: list[LineMatch] = []
	bytes_read = 0

	for line_number, raw_line in _iter_searchable_lines(file_path, max_file_size):
		if max_file_size is not None:
			bytes_read += len(raw_line.encode("utf-8", errors="ignore"))
			if bytes_read > max_file_size:
				break

		line_text = normalize_text(raw_line)
		if not line_text:
			continue

		score = matcher.score(query, line_text)
		if score >= line_threshold:
			matches.append(
				LineMatch(
					line_number=line_number,
					text=raw_line,
					score=score,
					location_kind=content_location_kind(file_path),
				)
			)

	matches.sort(key=lambda match: match.score, reverse=True)
	matches = matches[:max_line_matches]
	content_score = matches[0].score if matches else 0.0
	return content_score, matches


def magic_file_search(
	path: Path | str,
	query: str,
	*,
	search_names: bool = True,
	search_contents: bool = True,
	threshold: float = 0.25,
	max_file_size: int | None = 1_048_576,
	max_line_matches: int = 50,
	line_threshold: float | None = None,
	skip_hidden_folders: bool = True,
	skip_noise_folders: bool = True,
	skipped_files: list[SkippedFile] | None = None,
) -> list[FileSearchResult]:
	if not search_names and not search_contents:
		raise ValueError("Enable at least one of search_names or search_contents")

	root = Path(path).expanduser().resolve()
	normalized_query = normalize_text(query)
	if not normalized_query:
		return []
	if not root.exists():
		raise FileNotFoundError(f"Path does not exist: {root}")

	effective_line_threshold = threshold if line_threshold is None else line_threshold
	search_root = root if root.is_dir() else root.parent
	matcher = CompositeMatcher()
	results: list[FileSearchResult] = []

	for file_path in _iter_files(
		root,
		skip_hidden_folders=skip_hidden_folders,
		skip_noise_folders=skip_noise_folders,
	):
		if not file_path.is_file():
			continue

		breakdown: dict[str, float] = {}
		scores: list[float] = []
		line_matches: list[LineMatch] = []

		if search_names:
			name_score = _score_name(matcher, normalized_query, file_path, search_root)
			breakdown["name"] = name_score
			scores.append(name_score)

		if search_contents:
			if max_file_size is not None and not _file_within_size_limit(file_path, max_file_size):
				try:
					size_bytes = file_path.stat().st_size
				except OSError:
					size_bytes = 0
				if skipped_files is not None:
					skipped_files.append(SkippedFile(path=file_path, size_bytes=size_bytes))
			else:
				content_score, line_matches = _score_lines(
					matcher,
					normalized_query,
					file_path,
					max_file_size,
					effective_line_threshold,
					max_line_matches,
				)
				breakdown["content"] = content_score
				scores.append(content_score)

		if not scores:
			continue

		score = max(scores)
		if score < threshold:
			continue
		results.append(
			FileSearchResult(
				path=file_path,
				score=score,
				breakdown=breakdown,
				lines=line_matches,
			)
		)

	results.sort(key=lambda result: result.score, reverse=True)
	return results
