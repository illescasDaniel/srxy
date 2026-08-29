"""Human-readable warnings for files skipped during search."""

from __future__ import annotations

from srxy.application.search_defaults import suggest_max_file_size
from srxy.domain.models import SkippedFile


def format_skipped_file_warning(skipped: SkippedFile, max_file_size: int | None) -> str:
	if skipped.reason == "ocr_too_large":
		from srxy.adapters.outbound.ocr.ocr_text import ocr_max_file_size

		limit = ocr_max_file_size()
		limit_label = f"{limit:,}" if limit is not None else "limit"
		return (
			f"warning: skipped OCR in {skipped.path.as_posix()} "
			f"({skipped.size_bytes:,} bytes > --max-ocr-file-size {limit_label})\n"
			f"  hint: increase --max-ocr-file-size or unset SRXY_OCR_MAX_FILE_SIZE"
		)
	if skipped.reason == "transcribe_too_large":
		from srxy.adapters.outbound.transcribe.transcribe_text import transcribe_max_file_size

		limit = transcribe_max_file_size()
		limit_label = f"{limit:,}" if limit is not None else "limit"
		return (
			f"warning: skipped transcription in {skipped.path.as_posix()} "
			f"({skipped.size_bytes:,} bytes > --max-transcribe-file-size {limit_label})\n"
			f"  hint: increase --max-transcribe-file-size or unset SRXY_TRANSCRIBE_MAX_FILE_SIZE"
		)
	if skipped.reason == "transcribe_no_speech":
		return f"warning: skipped transcription in {skipped.path.as_posix()} (no speech detected after retry)"
	if skipped.reason == "transcribe_failed":
		return f"warning: skipped transcription in {skipped.path.as_posix()} (transcription failed)"

	suggested = suggest_max_file_size(skipped.size_bytes)
	return (
		f"warning: skipped content search in {skipped.path.as_posix()} "
		f"({skipped.size_bytes:,} bytes > --max-file-size {max_file_size:,})\n"
		f"  hint: rerun with --max-file-size {suggested}"
	)


def format_skipped_file_warnings(skipped_files: list[SkippedFile], max_file_size: int | None) -> str:
	if not skipped_files:
		return ""

	lines: list[str] = []
	for skipped in skipped_files:
		lines.append(format_skipped_file_warning(skipped, max_file_size))
	return "\n".join(lines)


__all__ = ["format_skipped_file_warning", "format_skipped_file_warnings"]
