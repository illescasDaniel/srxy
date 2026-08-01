"""Typed text units extracted from files for matching."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextUnit:
	"""One searchable text surface from a file (line, OCR block, tag, …)."""

	line_number: int
	text: str
	location_kind: str = "line"
