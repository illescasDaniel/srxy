"""Pure text helpers for the domain layer (stdlib only)."""

from __future__ import annotations

import re
from typing import Any


_WORD_PATTERN = re.compile(r"[\w']+", flags=re.UNICODE)
_MIN_QUERY_WORD_LENGTH = 3


def normalize_text(value: Any) -> str:
	if value is None:
		return ""
	return str(value).strip().lower()


def collapse_whitespace(text: str) -> str:
	return " ".join(text.split())


def query_words(text: str) -> list[str]:
	words: list[str] = []
	for match in _WORD_PATTERN.finditer(text):
		word = match.group()
		normalized = normalize_text(word)
		if len(normalized) < _MIN_QUERY_WORD_LENGTH:
			continue
		if any(char.isalpha() for char in normalized):
			words.append(word)
	return words
