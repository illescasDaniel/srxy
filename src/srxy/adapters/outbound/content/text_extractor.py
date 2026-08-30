"""Default text extractor — owns searchable line sources."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from srxy.domain.models import SkippedFile
from srxy.domain.progress import ActivityCallback
from srxy.domain.text_unit import TextUnit


class DefaultTextExtractor:
	"""TextExtractorPort backed by local line sources (docs, OCR, transcript, tags)."""

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
		from srxy.adapters.outbound.content import line_sources

		for line_number, text, location_kind in line_sources.iter_searchable_lines(
			path,
			max_file_size,
			search_docs_tags=search_docs_tags,
			ocr=ocr,
			transcribe=transcribe,
			skipped_files=skipped_files,
			on_activity=on_activity,
		):
			yield TextUnit(line_number=line_number, text=text, location_kind=location_kind)

	def effective_max_file_size(
		self,
		path: Path,
		max_file_size: int | None,
		*,
		ocr: bool | None = None,
	) -> int | None:
		from srxy.adapters.outbound.content import line_sources

		return line_sources.effective_max_file_size(path, max_file_size, ocr=ocr)

	def can_search_without_reading_body(self, path: Path) -> bool:
		from srxy.adapters.outbound.content import line_sources

		return line_sources.can_search_without_reading_body(path)

	def within_size_limit(self, path: Path, max_file_size: int | None) -> bool:
		from srxy.adapters.outbound.content import line_sources

		return line_sources.file_within_size_limit(path, max_file_size)

	def size_bytes(self, path: Path) -> int:
		from srxy.adapters.outbound.content import line_sources

		return line_sources.size_bytes(path)

	def ocr_active(self, ocr: bool | None) -> bool:
		from srxy.adapters.outbound.ocr.ocr_text import is_ocr_active

		return is_ocr_active(ocr)

	def transcribe_active(self, transcribe: bool | None) -> bool:
		from srxy.adapters.outbound.transcribe.transcribe_text import is_transcribe_active

		return is_transcribe_active(transcribe)

	def ocr_requested(self, ocr: bool | None) -> bool:
		from srxy.adapters.outbound.ocr.ocr_text import ocr_requested

		return ocr_requested(ocr)

	def transcribe_requested(self, transcribe: bool | None) -> bool:
		from srxy.adapters.outbound.transcribe.transcribe_text import transcribe_requested

		return transcribe_requested(transcribe)

	def ocr_candidate_path(self, path: Path) -> bool:
		from srxy.adapters.outbound.ocr.ocr_text import is_ocr_image_path

		return is_ocr_image_path(path)

	def transcribe_candidate_path(self, path: Path) -> bool:
		from srxy.adapters.outbound.transcribe.transcribe_text import is_transcribe_path

		return is_transcribe_path(path)
