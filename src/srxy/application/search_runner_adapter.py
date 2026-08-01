"""Search runner adapters — in-process session vs subprocess worker."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any

from srxy.application.search_session import SearchSession


class AdaptiveSearchRunner:
	"""Delegates to ``SearchSession`` or the JSON subprocess worker."""

	def __init__(self, search_session: SearchSession):
		self._search_session = search_session

	def uses_subprocess(self, args: argparse.Namespace) -> bool:
		return self._search_session.uses_subprocess(args)

	def run_blocking(
		self,
		args: argparse.Namespace,
		*,
		on_event: Callable[[object], None],
		cancel_check: Callable[[], bool] | None = None,
	):
		self._search_session.run_blocking(args, on_event=on_event, cancel_check=cancel_check)

	def iter_subprocess_events(
		self,
		args: argparse.Namespace,
		*,
		cancel_check: Callable[[], bool] | None = None,
		on_process: Callable[[asyncio.subprocess.Process], None] | None = None,
	) -> AsyncIterator[dict[str, Any]]:
		from srxy.adapters.outbound.worker.search_worker import iter_subprocess_search_events

		return iter_subprocess_search_events(args, cancel_check=cancel_check, on_process=on_process)
