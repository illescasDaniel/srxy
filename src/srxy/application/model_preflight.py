"""Shared model-download prompts and pending-download discovery for GUI/TUI."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from srxy.adapters.outbound.models.model_store import (
	download_semantic_image_model,
	download_semantic_text_model,
	download_transcribe_model,
	ensure_semantic_image_model,
	ensure_semantic_text_model,
	ensure_transcribe_model,
	is_model_installed,
	semantic_image_model_dir,
	semantic_text_model_dir,
	transcribe_faster_whisper_model_dir,
	transcribe_transformers_model_dir,
)
from srxy.i18n import tr


@dataclass(frozen=True, slots=True)
class PendingModelDownload:
	kind: str  # semantic_text | semantic_image | transcribe
	label: str
	prompt: str


def semantic_text_model_label() -> str:
	return tr("model.label.semantic_text")


def semantic_image_model_label() -> str:
	return tr("model.label.semantic_image")


def transcribe_model_download_info() -> tuple[str, str, Path]:
	from srxy.adapters.outbound.models.device import resolve_transcribe_device, transcribe_backend_for_device

	device = resolve_transcribe_device()
	backend = transcribe_backend_for_device(device)
	if backend == "transformers":
		return tr("model.label.transcribe_transformers"), "~290 MB", transcribe_transformers_model_dir()
	return tr("model.label.transcribe_faster_whisper"), "~150 MB", transcribe_faster_whisper_model_dir()


def format_download_prompt(label: str, target_dir: Path, *, size_hint: str = "") -> str:
	if size_hint:
		return tr("model.download_prompt_with_size", label=label, path=target_dir, size_hint=size_hint)
	return tr("model.download_prompt", label=label, path=target_dir)


def download_progress_label(label: str) -> str:
	return tr("status.downloading", label=label)


def list_pending_model_downloads(args: argparse.Namespace) -> list[PendingModelDownload]:
	"""Return models that are requested but not yet installed.

	Does not fail on missing optional deps — callers should probe capabilities
	first. Uses ensure_* with interactive=False (or is_model_installed).
	"""
	pending: list[PendingModelDownload] = []
	want_semantic = bool(getattr(args, "semantic", False) or getattr(args, "semantic_all", False))
	want_semantic_image = bool(getattr(args, "semantic_image", False) or getattr(args, "semantic_all", False))
	want_transcribe = bool(getattr(args, "transcribe", False) or getattr(args, "semantic_all", False))

	if want_semantic and not ensure_semantic_text_model(interactive=False):
		label = semantic_text_model_label()
		pending.append(
			PendingModelDownload(
				kind="semantic_text",
				label=label,
				prompt=format_download_prompt(label, semantic_text_model_dir()),
			)
		)

	if want_semantic_image and not ensure_semantic_image_model(interactive=False):
		label = semantic_image_model_label()
		pending.append(
			PendingModelDownload(
				kind="semantic_image",
				label=label,
				prompt=format_download_prompt(label, semantic_image_model_dir()),
			)
		)

	if want_transcribe and not ensure_transcribe_model(interactive=False):
		label, size_hint, target = transcribe_model_download_info()
		if not is_model_installed(target):
			pending.append(
				PendingModelDownload(
					kind="transcribe",
					label=label,
					prompt=format_download_prompt(label, target, size_hint=size_hint),
				)
			)

	return pending


def download_fn_for_kind(kind: str) -> Callable[..., None]:
	if kind == "semantic_text":
		return download_semantic_text_model
	if kind == "semantic_image":
		return download_semantic_image_model
	if kind == "transcribe":
		return download_transcribe_model
	raise ValueError(f"Unknown model download kind: {kind!r}")


__all__ = [
	"PendingModelDownload",
	"download_fn_for_kind",
	"download_progress_label",
	"format_download_prompt",
	"list_pending_model_downloads",
	"semantic_image_model_label",
	"semantic_text_model_label",
	"transcribe_model_download_info",
]
