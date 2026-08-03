from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable
from typing import Any, Protocol

from srxy.adapters.inbound.tui.modals import DownloadConfirmModal, DownloadProgressModal
from srxy.adapters.outbound.models.model_store import (
	download_semantic_image_model,
	download_semantic_text_model,
	download_transcribe_model,
	ensure_semantic_image_model,
	ensure_semantic_text_model,
	ensure_transcribe_model,
	is_model_installed,
	semantic_image_model_dir,
	semantic_image_model_missing_message,
	semantic_text_model_dir,
	semantic_text_model_missing_message,
	transcribe_model_missing_message,
)
from srxy.application.deps_preflight import deps_only_preflight
from srxy.application.model_preflight import (
	download_progress_label,
	format_download_prompt,
	semantic_image_model_label,
	semantic_text_model_label,
	transcribe_model_download_info,
)


class TuiPreflightApp(Protocol):
	async def push_screen_wait(self, screen: DownloadConfirmModal) -> bool: ...

	def push_screen(self, screen: DownloadProgressModal, *, wait_for_dismiss: bool = False) -> object: ...

	def pop_screen(self) -> None: ...

	def call_from_thread(self, callback: Callable[..., object], *args: object, **kwargs: object) -> None: ...


async def run_tui_preflight(app: Any, args: argparse.Namespace) -> str | None:
	error = deps_only_preflight(args)
	if error is not None:
		return error

	if not await _ensure_transcribe_model_tui(app, args):
		return transcribe_model_missing_message()

	if (args.semantic or args.semantic_all) and not await _ensure_semantic_text_model_tui(app):
		return semantic_text_model_missing_message()

	if (args.semantic_image or args.semantic_all) and not await _ensure_semantic_image_model_tui(app):
		return semantic_image_model_missing_message()

	return None


async def _run_download_with_progress(
	app: TuiPreflightApp,
	label: str,
	download_fn: Callable[..., None],
):
	modal = DownloadProgressModal(label)
	app.push_screen(modal, wait_for_dismiss=False)

	def on_progress(current: int, total: int, message: str):
		app.call_from_thread(modal.update_progress, current, total, message)

	try:
		await asyncio.to_thread(download_fn, on_progress=on_progress)
	finally:
		app.pop_screen()


async def _ensure_semantic_text_model_tui(app: TuiPreflightApp) -> bool:
	if ensure_semantic_text_model(interactive=False):
		return True
	label = semantic_text_model_label()
	if not await app.push_screen_wait(DownloadConfirmModal(format_download_prompt(label, semantic_text_model_dir()))):
		return False
	await _run_download_with_progress(app, download_progress_label(label), download_semantic_text_model)
	return True


async def _ensure_semantic_image_model_tui(app: TuiPreflightApp) -> bool:
	if ensure_semantic_image_model(interactive=False):
		return True
	label = semantic_image_model_label()
	if not await app.push_screen_wait(DownloadConfirmModal(format_download_prompt(label, semantic_image_model_dir()))):
		return False
	await _run_download_with_progress(app, download_progress_label(label), download_semantic_image_model)
	return True


async def _ensure_transcribe_model_tui(app: TuiPreflightApp, args: argparse.Namespace) -> bool:
	from srxy.adapters.outbound.transcribe.transcribe_text import transcribe_requested

	if not transcribe_requested(args.transcribe or args.semantic_all):
		return True
	if ensure_transcribe_model(interactive=False):
		return True
	label, size_hint, target = transcribe_model_download_info()
	if is_model_installed(target):
		return True
	if not await app.push_screen_wait(DownloadConfirmModal(format_download_prompt(label, target, size_hint=size_hint))):
		return False
	await _run_download_with_progress(app, download_progress_label(label), download_transcribe_model)
	return True
