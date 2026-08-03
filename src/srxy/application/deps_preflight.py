"""Hard dependency checks shared by GUI and TUI (no model download prompts)."""

from __future__ import annotations

import argparse

from srxy.adapters.inbound.cli.cli import apply_args_to_env
from srxy.adapters.outbound.ocr.ocr_text import is_ocr_available, ocr_unavailable_message
from srxy.adapters.outbound.semantic.semantic_image import (
	is_semantic_image_available,
	semantic_image_unavailable_message,
)
from srxy.adapters.outbound.transcribe.transcribe_text import (
	ffmpeg_available,
	ffmpeg_unavailable_message,
	transcribe_deps_installed,
	transcribe_unavailable_message,
)
from srxy.application.matching.semantic import (
	semantic_deps_unavailable_message,
	sentence_transformers_installed,
)


def deps_only_preflight(args: argparse.Namespace) -> str | None:
	apply_args_to_env(args)
	if bool(args.ocr or args.semantic_all) and not is_ocr_available():
		return ocr_unavailable_message()
	if bool(args.transcribe or args.semantic_all) and not transcribe_deps_installed():
		return transcribe_unavailable_message()
	if bool(args.transcribe or args.semantic_all) and not ffmpeg_available():
		return ffmpeg_unavailable_message()
	if bool(args.semantic or args.semantic_all) and not sentence_transformers_installed():
		return semantic_deps_unavailable_message()
	if bool(args.semantic_image or args.semantic_all) and not is_semantic_image_available():
		return semantic_image_unavailable_message()
	return None


__all__ = ["deps_only_preflight"]
