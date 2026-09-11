"""Shared user-facing search status messages (CLI / TUI / GUI)."""

from __future__ import annotations

from pathlib import Path


def format_no_matches_message(query: str, path: Path | str) -> str:
	from srxy.domain.file_query import format_query_for_display

	return f'No matches for "{format_query_for_display(query)}" in {Path(path).expanduser()}'


__all__ = ["format_no_matches_message"]
