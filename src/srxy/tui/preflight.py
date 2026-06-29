from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from srxy.cli import apply_args_to_env
from srxy.matchers.semantic import (
	semantic_env_enabled,
	sentence_transformers_installed,
)
from srxy.model_store import (
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
	transcribe_faster_whisper_model_dir,
	transcribe_model_missing_message,
	transcribe_transformers_model_dir,
)
from srxy.ocr_text import is_ocr_available, ocr_requested, ocr_unavailable_message
from srxy.semantic_image import (
	is_semantic_image_available,
	semantic_image_requested,
	semantic_image_unavailable_message,
)
from srxy.transcribe_text import (
	ffmpeg_available,
	ffmpeg_unavailable_message,
	transcribe_deps_installed,
	transcribe_requested,
	transcribe_unavailable_message,
)
from srxy.tui.modals import DownloadConfirmModal, DownloadProgressModal


class TuiPreflightApp(Protocol):
	async def push_screen_wait(self, screen: DownloadConfirmModal) -> bool: ...

	def push_screen(self, screen: DownloadProgressModal, *, wait_for_dismiss: bool = False) -> object: ...

	def pop_screen(self) -> None: ...

	def call_from_thread(self, callback: Callable[..., object], *args: object, **kwargs: object) -> None: ...


async def run_tui_preflight(app: Any, args: argparse.Namespace) -> str | None:
	apply_args_to_env(args)

	if ocr_requested(args.ocr or args.semantic_all) and not is_ocr_available():
		return ocr_unavailable_message()

	if transcribe_requested(args.transcribe or args.semantic_all) and not transcribe_deps_installed():
		return transcribe_unavailable_message()
	if transcribe_requested(args.transcribe or args.semantic_all) and not ffmpeg_available():
		return ffmpeg_unavailable_message()
	if transcribe_requested(args.transcribe or args.semantic_all) and not await _ensure_transcribe_model_tui(app):
		return transcribe_model_missing_message()

	if semantic_env_enabled() and (args.semantic or args.semantic_all):
		if not sentence_transformers_installed():
			return "Semantic matching requires the optional dependency: pip install 'srxy[semantic]'"
		if not await _ensure_semantic_text_model_tui(app):
			return semantic_text_model_missing_message()

	if semantic_image_requested(args.semantic_image or args.semantic_all):
		if not is_semantic_image_available():
			return semantic_image_unavailable_message()
		if not await _ensure_semantic_image_model_tui(app):
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
	if not await app.push_screen_wait(
		DownloadConfirmModal(_download_prompt("Semantic text model", semantic_text_model_dir()))
	):
		return False
	await _run_download_with_progress(app, "Downloading semantic text model…", download_semantic_text_model)
	return True


async def _ensure_semantic_image_model_tui(app: TuiPreflightApp) -> bool:
	if ensure_semantic_image_model(interactive=False):
		return True
	if not await app.push_screen_wait(
		DownloadConfirmModal(_download_prompt("Semantic image model", semantic_image_model_dir()))
	):
		return False
	await _run_download_with_progress(app, "Downloading semantic image model…", download_semantic_image_model)
	return True


async def _ensure_transcribe_model_tui(app: TuiPreflightApp) -> bool:
	if ensure_transcribe_model(interactive=False):
		return True
	from srxy.device import resolve_transcribe_device, transcribe_backend_for_device

	device = resolve_transcribe_device()
	backend = transcribe_backend_for_device(device)
	if backend == "transformers":
		target = transcribe_transformers_model_dir()
		label = "Transcription model (transformers)"
		size_hint = "~290 MB"
	else:
		target = transcribe_faster_whisper_model_dir()
		label = "Transcription model (faster-whisper)"
		size_hint = "~150 MB"
	if is_model_installed(target):
		return True
	if not await app.push_screen_wait(DownloadConfirmModal(_download_prompt(label, target, size_hint=size_hint))):
		return False
	await _run_download_with_progress(app, f"Downloading {label}…", download_transcribe_model)
	return True


def _download_prompt(label: str, target_dir: Path, *, size_hint: str = "") -> str:
	hint = f" ({size_hint})" if size_hint else ""
	return f"{label} is not cached at {target_dir}.\nDownload{hint}?"
