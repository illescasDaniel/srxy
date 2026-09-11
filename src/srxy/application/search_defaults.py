"""Light search defaults shared by CLI argparse, GUI, and use cases.

Keep this module free of OCR / semantic / cache imports so GUI cold-start
can load parser defaults without pulling the outbound search stack.
"""

from __future__ import annotations


DEFAULT_MAX_FILE_SIZE = 100 * 1024 * 1024
DEFAULT_SEMANTIC_IMAGE_THRESHOLD = 0.18
DEFAULT_TRANSCRIBE_THRESHOLD = 0.25
DEFAULT_OCR_MAX_FILE_SIZE = 50 * 1024 * 1024
DEFAULT_TRANSCRIBE_MAX_FILE_SIZE = 500 * 1024 * 1024


def suggest_max_file_size(file_size_bytes: int) -> int:
	chunk = 1_048_576
	return max(file_size_bytes + 1, ((file_size_bytes // chunk) + 1) * chunk)


__all__ = [
	"DEFAULT_MAX_FILE_SIZE",
	"DEFAULT_OCR_MAX_FILE_SIZE",
	"DEFAULT_SEMANTIC_IMAGE_THRESHOLD",
	"DEFAULT_TRANSCRIBE_MAX_FILE_SIZE",
	"DEFAULT_TRANSCRIBE_THRESHOLD",
	"suggest_max_file_size",
]
