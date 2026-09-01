"""Line-oriented content sources for searchable files."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from srxy.adapters.outbound.archive.archive_search import (
	is_archive_member_path,
	iter_archive_member_lines,
)
from srxy.adapters.outbound.content.content_kind import (
	is_ocr_image_logical_suffix,
	is_transcribe_logical_suffix,
	resolve_content_route,
	route_after_document_failure,
)
from srxy.adapters.outbound.documents.document_text import (
	DocumentExtractError,
	is_document_path,
	iter_document_lines,
	iter_document_metadata_lines,
)
from srxy.adapters.outbound.metadata.media_metadata import is_media_path, iter_media_metadata_lines
from srxy.adapters.outbound.metadata.windows_metadata import (
	has_windows_searchable_metadata,
	iter_windows_metadata_lines,
)
from srxy.adapters.outbound.metadata.xattr_metadata import has_searchable_xattrs, iter_xattr_metadata_lines
from srxy.adapters.outbound.ocr.ocr_text import (
	is_ocr_active,
	is_ocr_image_path,
	iter_image_ocr_lines,
	ocr_max_file_size,
)
from srxy.adapters.outbound.transcribe.transcribe_text import (
	is_transcribe_active,
	is_transcribe_path,
	iter_transcript_lines,
	transcribe_max_file_size,
)
from srxy.domain.models import SkippedFile
from srxy.domain.progress import ActivityCallback, clear_activity, emit_activity


_TEXT_SAMPLE_SIZE = 8192


def effective_max_file_size(path: Path, max_file_size: int | None, *, ocr: bool | None = None) -> int | None:
	if max_file_size is None or is_media_path(path):
		return None
	if is_document_path(path) and is_ocr_active(ocr):
		return ocr_max_file_size()
	return max_file_size


def can_search_without_reading_body(path: Path) -> bool:
	return is_media_path(path) or has_searchable_xattrs(path) or has_windows_searchable_metadata(path)


def file_within_size_limit(path: Path, max_file_size: int | None) -> bool:
	if is_archive_member_path(path):
		from srxy.adapters.outbound.archive.archive_search import archive_member_size_bytes

		size = archive_member_size_bytes(path)
		if size is None:
			return False
		if size == 0:
			return True
		if max_file_size is not None and size > max_file_size:
			return False
		return True
	try:
		size = path.stat().st_size
	except OSError:
		return False
	if size == 0:
		return True
	if max_file_size is not None and size > max_file_size:
		return False
	return True


def size_bytes(path: Path) -> int:
	if is_archive_member_path(path):
		from srxy.adapters.outbound.archive.archive_search import archive_member_size_bytes

		return archive_member_size_bytes(path) or 0
	try:
		return path.stat().st_size
	except OSError:
		return 0


def _is_probably_text(path: Path, max_file_size: int | None) -> bool:
	if is_archive_member_path(path):
		from srxy.adapters.outbound.archive.archive_search import read_archive_member_bytes

		if not file_within_size_limit(path, max_file_size):
			return False
		sample = read_archive_member_bytes(path, max_bytes=_TEXT_SAMPLE_SIZE)
		return sample is not None and b"\x00" not in sample
	if not file_within_size_limit(path, max_file_size):
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


def _yield_media_units(
	path: Path,
	*,
	logical_suffix: str,
	search_docs_tags: bool,
	ocr: bool | None,
	transcribe: bool | None,
	skipped_files: list[SkippedFile] | None,
	on_activity: ActivityCallback | None,
) -> Iterator[tuple[int, str, str]]:
	if search_docs_tags:
		for line_number, raw_line in iter_media_metadata_lines(path, logical_suffix=logical_suffix):
			yield line_number, raw_line, "tag"
	ocr_path = is_ocr_image_path(path) or is_ocr_image_logical_suffix(logical_suffix)
	if is_ocr_active(ocr) and ocr_path:
		ocr_byte_limit = ocr_max_file_size()
		if ocr_byte_limit is not None and not file_within_size_limit(path, ocr_byte_limit):
			_append_ocr_skip(path, skipped_files)
		else:
			emit_activity(on_activity, f"OCR · {path.name}")
			try:
				for line_number, raw_line in iter_image_ocr_lines(path, skipped_files=skipped_files):
					yield line_number, raw_line, "ocr"
			finally:
				clear_activity(on_activity)
	transcribe_path = is_transcribe_path(path) or is_transcribe_logical_suffix(logical_suffix)
	if is_transcribe_active(transcribe) and transcribe_path:
		transcribe_byte_limit = transcribe_max_file_size()
		if transcribe_byte_limit is not None and not file_within_size_limit(path, transcribe_byte_limit):
			_append_transcribe_skip(path, skipped_files)
		else:
			emit_activity(on_activity, f"Transcribe · {path.name}")
			try:
				for line_number, raw_line in iter_transcript_lines(
					path, on_activity=on_activity, skipped_files=skipped_files
				):
					yield line_number, raw_line, "transcript"
			finally:
				clear_activity(on_activity)


def _yield_document_units(
	path: Path,
	*,
	logical_suffix: str,
	ocr: bool | None,
	on_activity: ActivityCallback | None,
) -> Iterator[tuple[int, str, str]]:
	yield from iter_document_lines(path, ocr=ocr, on_activity=on_activity, logical_suffix=logical_suffix)


def _iter_body_searchable_lines(
	path: Path,
	max_file_size: int | None,
	*,
	ocr: bool | None = None,
	on_activity: ActivityCallback | None = None,
) -> Iterator[tuple[int, str, str]]:
	if is_archive_member_path(path):
		content_byte_limit = max_file_size
		if not file_within_size_limit(path, content_byte_limit):
			return
		for line_number, raw_line in iter_archive_member_lines(path, content_byte_limit):
			yield line_number, raw_line, "line"
		return
	content_byte_limit = effective_max_file_size(path, max_file_size, ocr=ocr)
	if is_media_path(path):
		return
	if not file_within_size_limit(path, content_byte_limit):
		return
	if is_document_path(path):
		try:
			yield from iter_document_lines(path, ocr=ocr, on_activity=on_activity)
		except DocumentExtractError:
			return
		return
	if not _is_probably_text(path, content_byte_limit):
		return
	for line_number, raw_line in _iter_utf8_lines(path, content_byte_limit):
		yield line_number, raw_line, "line"


def _append_ocr_skip(path: Path, skipped_files: list[SkippedFile] | None, *, reason: str = "ocr_too_large"):
	if skipped_files is None:
		return
	skipped_files.append(SkippedFile(path=path, size_bytes=size_bytes(path), reason=reason))


def append_ocr_skip(path: Path, skipped_files: list[SkippedFile] | None, *, reason: str = "ocr_too_large"):
	_append_ocr_skip(path, skipped_files, reason=reason)


def _append_transcribe_skip(
	path: Path, skipped_files: list[SkippedFile] | None, *, reason: str = "transcribe_too_large"
):
	if skipped_files is None:
		return
	skipped_files.append(SkippedFile(path=path, size_bytes=size_bytes(path), reason=reason))


def append_transcribe_skip(
	path: Path, skipped_files: list[SkippedFile] | None, *, reason: str = "transcribe_too_large"
):
	_append_transcribe_skip(path, skipped_files, reason=reason)


def iter_searchable_lines(
	path: Path,
	max_file_size: int | None,
	*,
	search_docs_tags: bool = True,
	ocr: bool | None = None,
	transcribe: bool | None = None,
	skipped_files: list[SkippedFile] | None = None,
	on_activity: ActivityCallback | None = None,
) -> Iterator[tuple[int, str, str]]:
	if is_archive_member_path(path):
		if search_docs_tags:
			yield from _iter_body_searchable_lines(path, max_file_size, ocr=ocr, on_activity=on_activity)
		return

	route = resolve_content_route(path)
	content_byte_limit = effective_max_file_size(path, max_file_size, ocr=ocr)

	if route.as_document:
		try:
			if search_docs_tags or is_ocr_active(ocr):
				for line_number, raw_line, location_kind in _yield_document_units(
					path, logical_suffix=route.logical_suffix, ocr=ocr, on_activity=on_activity
				):
					if not search_docs_tags and location_kind != "ocr":
						continue
					yield line_number, raw_line, location_kind
		except DocumentExtractError:
			route = route_after_document_failure(path)

	if route.as_media:
		yield from _yield_media_units(
			path,
			logical_suffix=route.logical_suffix,
			search_docs_tags=search_docs_tags,
			ocr=ocr,
			transcribe=transcribe,
			skipped_files=skipped_files,
			on_activity=on_activity,
		)
	elif route.body_text and (search_docs_tags or is_ocr_active(ocr)):
		if search_docs_tags and file_within_size_limit(path, content_byte_limit):
			for line_number, raw_line in _iter_utf8_lines(path, content_byte_limit):
				yield line_number, raw_line, "line"

	if search_docs_tags:
		for line_number, raw_line in iter_xattr_metadata_lines(path):
			yield line_number, raw_line, "tag"
		for line_number, raw_line in iter_document_metadata_lines(path):
			yield line_number, raw_line, "tag"
		for line_number, raw_line in iter_windows_metadata_lines(path):
			yield line_number, raw_line, "tag"
