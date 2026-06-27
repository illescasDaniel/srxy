from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from pathlib import Path

from srxy.cache import get_file_content_hash, reset_run_file_hashes
from srxy.document_text import is_document_path, iter_document_lines
from srxy.matchers.composite import CompositeMatcher
from srxy.media_metadata import is_media_path, iter_media_metadata_lines
from srxy.models import FileSearchResult, LineMatch, SkippedFile
from srxy.ocr_text import (
	is_ocr_active,
	is_ocr_image_path,
	iter_image_ocr_lines,
	ocr_max_file_size,
)
from srxy.semantic_image import (
	DEFAULT_SEMANTIC_IMAGE_THRESHOLD,
	encode_semantic_image_query,
	is_semantic_image_active,
	is_semantic_image_path,
	score_image,
	semantic_image_requested,
)
from srxy.transcribe_text import (
	DEFAULT_TRANSCRIBE_THRESHOLD,
	is_transcribe_active,
	is_transcribe_path,
	iter_transcript_lines,
	transcribe_max_file_size,
)
from srxy.utils import normalize_text
from srxy.windows_metadata import has_windows_tags, iter_windows_metadata_lines
from srxy.xattr_metadata import has_searchable_xattrs, iter_xattr_metadata_lines


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


def _collect_files(
	root: Path,
	*,
	skip_hidden_folders: bool = True,
	skip_noise_folders: bool = True,
) -> list[Path]:
	return list(
		_iter_files(
			root,
			skip_hidden_folders=skip_hidden_folders,
			skip_noise_folders=skip_noise_folders,
		)
	)


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


def _effective_max_file_size(path: Path, max_file_size: int | None, *, ocr: bool | None = None) -> int | None:
	if max_file_size is None or is_media_path(path):
		return None
	if is_document_path(path) and is_ocr_active(ocr):
		return ocr_max_file_size()
	return max_file_size


def _can_search_without_reading_body(path: Path) -> bool:
	return is_media_path(path) or has_searchable_xattrs(path) or has_windows_tags(path)


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


def _iter_body_searchable_lines(
	path: Path,
	max_file_size: int | None,
	*,
	ocr: bool | None = None,
) -> Iterator[tuple[int, str]]:
	content_byte_limit = _effective_max_file_size(path, max_file_size, ocr=ocr)
	if is_media_path(path):
		return
	if not _file_within_size_limit(path, content_byte_limit):
		return
	if is_document_path(path):
		yield from iter_document_lines(path, ocr=ocr)
		return
	if not _is_probably_text(path, content_byte_limit):
		return
	yield from _iter_utf8_lines(path, content_byte_limit)


def _append_ocr_skip(path: Path, skipped_files: list[SkippedFile] | None):
	if skipped_files is None:
		return
	try:
		size_bytes = path.stat().st_size
	except OSError:
		size_bytes = 0
	skipped_files.append(SkippedFile(path=path, size_bytes=size_bytes, reason="ocr_too_large"))


def _append_transcribe_skip(path: Path, skipped_files: list[SkippedFile] | None):
	if skipped_files is None:
		return
	try:
		size_bytes = path.stat().st_size
	except OSError:
		size_bytes = 0
	skipped_files.append(SkippedFile(path=path, size_bytes=size_bytes, reason="transcribe_too_large"))


def _iter_searchable_lines(
	path: Path,
	max_file_size: int | None,
	*,
	ocr: bool | None = None,
	transcribe: bool | None = None,
	skipped_files: list[SkippedFile] | None = None,
	on_activity: Callable[[str | None], None] | None = None,
) -> Iterator[tuple[int, str, str]]:
	if is_media_path(path):
		for line_number, raw_line in iter_media_metadata_lines(path):
			yield line_number, raw_line, "tag"
		if is_ocr_active(ocr) and is_ocr_image_path(path):
			ocr_byte_limit = ocr_max_file_size()
			if ocr_byte_limit is not None and not _file_within_size_limit(path, ocr_byte_limit):
				_append_ocr_skip(path, skipped_files)
			else:
				if on_activity is not None:
					on_activity(f"OCR · {path.name}")
				try:
					for line_number, raw_line in iter_image_ocr_lines(path):
						yield line_number, raw_line, "ocr"
				finally:
					if on_activity is not None:
						on_activity(None)
		if is_transcribe_active(transcribe) and is_transcribe_path(path):
			transcribe_byte_limit = transcribe_max_file_size()
			if transcribe_byte_limit is not None and not _file_within_size_limit(path, transcribe_byte_limit):
				_append_transcribe_skip(path, skipped_files)
			else:
				if on_activity is not None:
					on_activity(f"Transcribe · {path.name}")
				try:
					for line_number, raw_line in iter_transcript_lines(path):
						yield line_number, raw_line, "transcript"
				finally:
					if on_activity is not None:
						on_activity(None)
	else:
		body_kind = content_location_kind(path)
		for line_number, raw_line in _iter_body_searchable_lines(path, max_file_size, ocr=ocr):
			yield line_number, raw_line, body_kind

	for line_number, raw_line in iter_xattr_metadata_lines(path):
		yield line_number, raw_line, "tag"
	for line_number, raw_line in iter_windows_metadata_lines(path):
		yield line_number, raw_line, "tag"


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
	transcribe_threshold: float = DEFAULT_TRANSCRIBE_THRESHOLD,
	*,
	ocr: bool | None = None,
	transcribe: bool | None = None,
	skipped_files: list[SkippedFile] | None = None,
	on_activity: Callable[[str | None], None] | None = None,
) -> tuple[float, list[LineMatch]]:
	matches: list[LineMatch] = []
	bytes_read = 0
	content_byte_limit = _effective_max_file_size(file_path, max_file_size, ocr=ocr)

	for line_number, raw_line, location_kind in _iter_searchable_lines(
		file_path,
		max_file_size,
		ocr=ocr,
		transcribe=transcribe,
		skipped_files=skipped_files,
		on_activity=on_activity,
	):
		if content_byte_limit is not None and location_kind not in {"tag", "ocr", "transcript"}:
			bytes_read += len(raw_line.encode("utf-8", errors="ignore"))
			if bytes_read > content_byte_limit:
				break

		line_text = normalize_text(raw_line)
		if not line_text:
			continue

		score = matcher.score(query, line_text)
		effective_threshold = transcribe_threshold if location_kind == "transcript" else line_threshold
		if score >= effective_threshold:
			matches.append(
				LineMatch(
					line_number=line_number,
					text=raw_line,
					score=score,
					location_kind=location_kind,
				)
			)

	matches.sort(key=lambda match: match.score, reverse=True)
	matches = matches[:max_line_matches]
	content_score = matches[0].score if matches else 0.0
	return content_score, matches


def _search_single_file(
	file_path: Path,
	*,
	matcher: CompositeMatcher,
	normalized_query: str,
	search_root: Path,
	search_names: bool,
	search_contents: bool,
	threshold: float,
	max_file_size: int | None,
	effective_line_threshold: float,
	max_line_matches: int,
	skipped_files: list[SkippedFile] | None,
	ocr: bool | None = None,
	transcribe: bool | None = None,
	semantic_image: bool | None = None,
	query_image_embedding: object | None = None,
	semantic_image_threshold: float = DEFAULT_SEMANTIC_IMAGE_THRESHOLD,
	transcribe_threshold: float = DEFAULT_TRANSCRIBE_THRESHOLD,
	on_activity: Callable[[str | None], None] | None = None,
) -> FileSearchResult | None:
	if not file_path.is_file():
		return None

	breakdown: dict[str, float] = {}
	scores: list[float] = []
	line_matches: list[LineMatch] = []

	if search_names:
		name_score = _score_name(matcher, normalized_query, file_path, search_root)
		breakdown["name"] = name_score
		scores.append(name_score)

	if search_contents:
		content_byte_limit = _effective_max_file_size(file_path, max_file_size, ocr=ocr)
		exceeds_size_limit = content_byte_limit is not None and not _file_within_size_limit(
			file_path, content_byte_limit
		)
		if exceeds_size_limit and not _can_search_without_reading_body(file_path):
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
				transcribe_threshold,
				ocr=ocr,
				transcribe=transcribe,
				skipped_files=skipped_files,
				on_activity=on_activity,
			)
			breakdown["content"] = content_score
			scores.append(content_score)

	if is_semantic_image_active(semantic_image) and is_semantic_image_path(file_path):
		semantic_image_score = 0.0
		if on_activity is not None:
			on_activity(f"CLIP · {file_path.name}")
		try:
			file_hash = get_file_content_hash(file_path)
			semantic_image_score = score_image(
				normalized_query,
				file_path,
				file_hash=file_hash,
				query_embedding=query_image_embedding,
			)
		finally:
			if on_activity is not None:
				on_activity(None)
		if semantic_image_score > 0.0:
			breakdown["semantic_image"] = semantic_image_score
			scores.append(semantic_image_score)

	if not scores:
		return None

	score = max(scores)
	cutoff = threshold
	semantic_score = breakdown.get("semantic_image")
	if semantic_score is not None and semantic_score >= score:
		cutoff = semantic_image_threshold
	content_score = breakdown.get("content")
	if (
		content_score is not None
		and content_score >= score
		and line_matches
		and line_matches[0].location_kind == "transcript"
	):
		cutoff = transcribe_threshold
	if score < cutoff:
		return None
	return FileSearchResult(
		path=file_path,
		score=score,
		breakdown=breakdown,
		lines=line_matches,
	)


def magic_file_search(
	path: Path | str,
	query: str,
	*,
	search_names: bool = True,
	search_contents: bool = True,
	threshold: float = 0.35,
	max_file_size: int | None = None,
	max_line_matches: int = 50,
	line_threshold: float | None = None,
	skip_hidden_folders: bool = True,
	skip_noise_folders: bool = True,
	skipped_files: list[SkippedFile] | None = None,
	ocr: bool | None = None,
	transcribe: bool | None = None,
	semantic_image: bool | None = None,
	semantic_image_threshold: float = DEFAULT_SEMANTIC_IMAGE_THRESHOLD,
	transcribe_threshold: float = DEFAULT_TRANSCRIBE_THRESHOLD,
	limit: int | None = None,
	on_progress: Callable[[int, int], None] | None = None,
	on_activity: Callable[[str | None], None] | None = None,
	on_result: Callable[[FileSearchResult], None] | None = None,
) -> list[FileSearchResult]:
	if not search_names and not search_contents and not semantic_image_requested(semantic_image):
		raise ValueError("Enable at least one of search_names, search_contents, or semantic_image")

	root = Path(path).expanduser().resolve()
	normalized_query = normalize_text(query)
	if not normalized_query:
		return []
	if not root.exists():
		raise FileNotFoundError(f"Path does not exist: {root}")

	reset_run_file_hashes()
	effective_line_threshold = threshold if line_threshold is None else line_threshold
	search_root = root if root.is_dir() else root.parent
	matcher = CompositeMatcher()
	results: list[FileSearchResult] = []
	query_image_embedding: object | None = None
	if is_semantic_image_active(semantic_image):
		if on_activity is not None:
			on_activity("Encoding image query…")
		try:
			query_image_embedding = encode_semantic_image_query(normalized_query)
		finally:
			if on_activity is not None:
				on_activity(None)
	files = _collect_files(
		root,
		skip_hidden_folders=skip_hidden_folders,
		skip_noise_folders=skip_noise_folders,
	)
	total_files = len(files)

	for index, file_path in enumerate(files, start=1):
		if on_activity is not None:
			on_activity(f"Scanning · {file_path.name}")
		try:
			result = _search_single_file(
				file_path,
				matcher=matcher,
				normalized_query=normalized_query,
				search_root=search_root,
				search_names=search_names,
				search_contents=search_contents,
				threshold=threshold,
				max_file_size=max_file_size,
				effective_line_threshold=effective_line_threshold,
				max_line_matches=max_line_matches,
				skipped_files=skipped_files,
				ocr=ocr,
				transcribe=transcribe,
				semantic_image=semantic_image,
				query_image_embedding=query_image_embedding,
				semantic_image_threshold=semantic_image_threshold,
				transcribe_threshold=transcribe_threshold,
				on_activity=on_activity,
			)
		finally:
			if on_activity is not None:
				on_activity(None)
		if on_progress is not None:
			on_progress(index, total_files)
		if result is None:
			continue
		results.append(result)
		if on_result is not None:
			on_result(result)

	results.sort(key=lambda result: result.score, reverse=True)
	if limit is not None:
		results = results[:limit]
	return results
