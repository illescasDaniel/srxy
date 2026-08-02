"""Probe optional GUI feature availability (OCR, semantic, transcribe)."""

from __future__ import annotations

import importlib.util
from dataclasses import asdict, dataclass

from srxy.adapters.outbound.models.device import resolve_torch_device
from srxy.adapters.outbound.ocr.ocr_text import is_ocr_available, ocr_unavailable_message
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


@dataclass(frozen=True, slots=True)
class Capabilities:
	semantic_deps: bool
	has_gpu: bool
	ocr: bool
	ffmpeg: bool
	transcribe_deps: bool
	semantic_enabled: bool
	semantic_image_enabled: bool
	transcribe_enabled: bool
	ocr_enabled: bool


def _probe_has_gpu() -> bool:
	if importlib.util.find_spec("torch") is None:
		return False
	return resolve_torch_device() in {"cuda", "mps"}


def probe_capabilities() -> Capabilities:
	semantic_deps = sentence_transformers_installed()
	has_gpu = _probe_has_gpu()
	ocr = is_ocr_available()
	ffmpeg = ffmpeg_available()
	transcribe_deps = transcribe_deps_installed()
	return Capabilities(
		semantic_deps=semantic_deps,
		has_gpu=has_gpu,
		ocr=ocr,
		ffmpeg=ffmpeg,
		transcribe_deps=transcribe_deps,
		semantic_enabled=semantic_deps and has_gpu,
		semantic_image_enabled=semantic_deps and has_gpu,
		transcribe_enabled=transcribe_deps and ffmpeg and has_gpu,
		ocr_enabled=ocr,
	)


def capabilities_to_dict(caps: Capabilities) -> dict[str, bool]:
	return asdict(caps)


def unavailable_reason(feature: str, caps: Capabilities) -> str:
	from srxy.i18n import tr

	if feature == "semantic":
		if not caps.semantic_deps:
			return semantic_deps_unavailable_message()
		if not caps.has_gpu:
			return tr("unavailable.semantic_gpu")
		return ""
	if feature == "semantic_image":
		if not caps.semantic_deps:
			return semantic_deps_unavailable_message()
		if not caps.has_gpu:
			return tr("unavailable.semantic_image_gpu")
		return ""
	if feature == "ocr":
		if not caps.ocr:
			return ocr_unavailable_message()
		return ""
	if feature == "transcribe":
		if not caps.transcribe_deps:
			return transcribe_unavailable_message()
		if not caps.ffmpeg:
			return ffmpeg_unavailable_message()
		if not caps.has_gpu:
			return tr("unavailable.transcribe_gpu")
		return ""
	return ""


__all__ = [
	"Capabilities",
	"capabilities_to_dict",
	"probe_capabilities",
	"unavailable_reason",
]
