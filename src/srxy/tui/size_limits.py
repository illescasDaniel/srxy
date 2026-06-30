from __future__ import annotations

import argparse
from dataclasses import dataclass

from srxy.file_search import DEFAULT_MAX_FILE_SIZE
from srxy.ocr_text import DEFAULT_OCR_MAX_FILE_SIZE
from srxy.transcribe_text import DEFAULT_TRANSCRIBE_MAX_FILE_SIZE


_MIB = 1024 * 1024


@dataclass(frozen=True, slots=True)
class SizeLimits:
	text_mib: str
	ocr_mib: str
	transcribe_mib: str


def bytes_to_mib_text(value: int, *, allow_zero: bool = False) -> str:
	if allow_zero and value == 0:
		return "0"
	mib = value / _MIB
	if mib == int(mib):
		return str(int(mib))
	return f"{mib:.1f}".rstrip("0").rstrip(".")


def size_limits_from_args(args: argparse.Namespace) -> SizeLimits:
	text_bytes = args.max_file_size if args.max_file_size is not None else DEFAULT_MAX_FILE_SIZE
	ocr_bytes = args.max_ocr_file_size if args.max_ocr_file_size is not None else DEFAULT_OCR_MAX_FILE_SIZE
	transcribe_bytes = (
		args.max_transcribe_file_size if args.max_transcribe_file_size is not None else DEFAULT_TRANSCRIBE_MAX_FILE_SIZE
	)
	return SizeLimits(
		text_mib=bytes_to_mib_text(text_bytes, allow_zero=True),
		ocr_mib=bytes_to_mib_text(ocr_bytes),
		transcribe_mib=bytes_to_mib_text(transcribe_bytes),
	)


def _parse_mib_field(raw: str, *, field_name: str, allow_zero: bool = False) -> int:
	text = raw.strip()
	if not text:
		raise ValueError(f"{field_name} is required")
	try:
		mib = float(text)
	except ValueError as error:
		raise ValueError(f"{field_name} must be a number of MiB") from error
	if allow_zero and mib == 0:
		return 0
	if mib < 1:
		raise ValueError(f"{field_name} must be at least 1 MiB (use 0 for unlimited text/docs only)")
	if mib * _MIB > 2**63 - 1:
		raise ValueError(f"{field_name} is too large")
	return int(mib * _MIB)


def parse_size_limits(limits: SizeLimits) -> tuple[int, int, int]:
	return (
		_parse_mib_field(limits.text_mib, field_name="Text & documents", allow_zero=True),
		_parse_mib_field(limits.ocr_mib, field_name="OCR"),
		_parse_mib_field(limits.transcribe_mib, field_name="Transcribe"),
	)


def validate_size_limits(limits: SizeLimits):
	parse_size_limits(limits)
