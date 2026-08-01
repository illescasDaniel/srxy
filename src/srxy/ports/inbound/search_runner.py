"""Inbound port: progressive search runner (in-process or subprocess)."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from typing import Protocol


class SearchRunnerPort(Protocol):
	"""Run a search with progressive events; may use a subprocess for heavy modes."""

	def uses_subprocess(self, args: argparse.Namespace) -> bool: ...

	def run_blocking(
		self,
		args: argparse.Namespace,
		*,
		on_event: Callable[[object], None],
		cancel_check: Callable[[], bool] | None = None,
	): ...
