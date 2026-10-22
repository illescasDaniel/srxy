"""Domain-level exceptions."""

from enum import StrEnum


class FileQueryParseError(ValueError):
	"""Raised when a boolean file-search query string cannot be parsed."""


class IgnoreReason(StrEnum):
	UNCLOSED_BRACKET = "unclosed_bracket"
	TRAILING_BACKSLASH = "trailing_backslash"
	LINE_TOO_LONG = "line_too_long"
	TOO_MANY_LINES = "too_many_lines"
	MULTILINE = "multiline"  # one CLI --ignore value containing a newline


class IgnorePatternError(ValueError):
	"""Raised when a user ignore pattern is invalid."""

	def __init__(self, *, line_number: int, pattern: str, reason: IgnoreReason):
		super().__init__(f"line {line_number}: {pattern!r} ({reason.value})")
		self.line_number = line_number
		self.pattern = pattern
		self.reason = reason
