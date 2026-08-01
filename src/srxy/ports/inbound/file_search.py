"""Inbound port: file search use case."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from typing import Protocol

from srxy.domain.models import FileSearchResult, SkippedFile
from srxy.domain.progress import ActivityCallback


class FileSearchPort(Protocol):
	"""Run a file search with optional progressive callbacks."""

	def execute(
		self,
		args: argparse.Namespace,
		*,
		skipped_files: list[SkippedFile] | None = None,
		on_progress: Callable[[int, int], None] | None = None,
		on_activity: ActivityCallback | None = None,
		on_result: Callable[[FileSearchResult], None] | None = None,
	) -> tuple[list[FileSearchResult], list[SkippedFile]]: ...
