from __future__ import annotations

import pytest

from srxy.cli import build_parser
from srxy.file_search import DEFAULT_MAX_FILE_SIZE
from srxy.ocr_text import DEFAULT_OCR_MAX_FILE_SIZE
from srxy.transcribe_text import DEFAULT_TRANSCRIBE_MAX_FILE_SIZE
from srxy.tui.size_limits import (
	SizeLimits,
	bytes_to_mib_text,
	parse_size_limits,
	size_limits_from_args,
	validate_size_limits,
)


pytestmark = pytest.mark.unit


def test_given_default_args_when_building_size_limits_then_uses_mib_defaults():
	# given
	args = build_parser().parse_args(["token"])

	# when
	limits = size_limits_from_args(args)

	# then
	assert limits == SizeLimits(text_mib="100", ocr_mib="50", transcribe_mib="500")


def test_given_zero_text_limit_when_parsing_then_allows_unlimited():
	# given
	limits = SizeLimits(text_mib="0", ocr_mib="50", transcribe_mib="500")

	# when
	max_file_size, max_ocr, max_transcribe = parse_size_limits(limits)

	# then
	assert max_file_size == 0
	assert max_ocr == DEFAULT_OCR_MAX_FILE_SIZE
	assert max_transcribe == DEFAULT_TRANSCRIBE_MAX_FILE_SIZE


def test_given_invalid_text_when_validating_then_raises():
	# given
	limits = SizeLimits(text_mib="abc", ocr_mib="50", transcribe_mib="500")

	# when / then
	with pytest.raises(ValueError, match="Text & documents"):
		validate_size_limits(limits)


def test_given_bytes_when_formatting_mib_then_rounds_cleanly():
	# when / then
	assert bytes_to_mib_text(DEFAULT_MAX_FILE_SIZE, allow_zero=True) == "100"
	assert bytes_to_mib_text(0, allow_zero=True) == "0"


def test_given_cli_size_flags_when_building_size_limits_then_reflects_arguments():
	# given
	args = build_parser().parse_args(
		[
			"token",
			"--max-file-size",
			"0",
			"--max-ocr-file-size",
			str(100 * 1024 * 1024),
			"--max-transcribe-file-size",
			str(250 * 1024 * 1024),
		]
	)

	# when
	limits = size_limits_from_args(args)

	# then
	assert limits == SizeLimits(text_mib="0", ocr_mib="100", transcribe_mib="250")


def test_given_size_limits_when_applying_to_args_then_sets_byte_fields():
	# given
	args = build_parser().parse_args(["token"])
	limits = SizeLimits(text_mib="10", ocr_mib="20", transcribe_mib="30")

	# when
	from srxy.tui.size_limits import apply_size_limits_to_args

	apply_size_limits_to_args(args, limits)

	# then
	assert args.max_file_size == 10 * 1024 * 1024
	assert args.max_ocr_file_size == 20 * 1024 * 1024
	assert args.max_transcribe_file_size == 30 * 1024 * 1024
