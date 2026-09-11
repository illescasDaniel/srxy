"""Probe optional GUI feature availability (OCR, semantic, transcribe)."""

from __future__ import annotations

import functools
import importlib.util
import shutil
from dataclasses import asdict, dataclass

from srxy.application.gpu_availability import has_accelerated_gpu_nofork
from srxy.application.matching.semantic import sentence_transformers_installed


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
	# No torch import and no subprocess: both are unsafe alongside Qt QThreads
	# (CUDA/Qt races; fork-while-multithreaded).
	return has_accelerated_gpu_nofork()


def _light_ocr_available() -> bool:
	"""OCR availability without importing the OCR adapter graph."""
	if importlib.util.find_spec("pytesseract") is None:
		return False
	from srxy.application.install_paths import resolve_tesseract_binary

	if resolve_tesseract_binary() is not None:
		return True
	return shutil.which("tesseract") is not None


def _light_ffmpeg_available() -> bool:
	from srxy.application.install_paths import resolve_ffmpeg_binary

	if resolve_ffmpeg_binary() is not None:
		return True
	return shutil.which("ffmpeg") is not None


def _light_transcribe_deps_installed() -> bool:
	return (
		importlib.util.find_spec("faster_whisper") is not None and importlib.util.find_spec("transformers") is not None
	)


def default_capabilities() -> Capabilities:
	"""Fast capability snapshot without a GPU probe or heavy adapter imports."""
	semantic_deps = sentence_transformers_installed()
	ocr = _light_ocr_available()
	ffmpeg = _light_ffmpeg_available()
	transcribe_deps = _light_transcribe_deps_installed()
	return Capabilities(
		semantic_deps=semantic_deps,
		has_gpu=False,
		ocr=ocr,
		ffmpeg=ffmpeg,
		transcribe_deps=transcribe_deps,
		semantic_enabled=False,
		semantic_image_enabled=False,
		transcribe_enabled=False,
		ocr_enabled=ocr,
	)


@functools.lru_cache(maxsize=1)
def probe_capabilities() -> Capabilities:
	from srxy.adapters.outbound.ocr.ocr_text import is_ocr_available
	from srxy.adapters.outbound.transcribe.transcribe_text import (
		ffmpeg_available,
		transcribe_deps_installed,
	)

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
			from srxy.application.matching.semantic import semantic_deps_unavailable_message

			return semantic_deps_unavailable_message()
		if not caps.has_gpu:
			return tr("unavailable.semantic_gpu")
		return ""
	if feature == "semantic_image":
		if not caps.semantic_deps:
			from srxy.application.matching.semantic import semantic_deps_unavailable_message

			return semantic_deps_unavailable_message()
		if not caps.has_gpu:
			return tr("unavailable.semantic_image_gpu")
		return ""
	if feature == "ocr":
		if not caps.ocr:
			from srxy.adapters.outbound.ocr.ocr_text import ocr_unavailable_message

			return ocr_unavailable_message()
		return ""
	if feature == "transcribe":
		if not caps.transcribe_deps:
			from srxy.adapters.outbound.transcribe.transcribe_text import (
				transcribe_unavailable_message,
			)

			return transcribe_unavailable_message()
		if not caps.ffmpeg:
			from srxy.adapters.outbound.transcribe.transcribe_text import (
				ffmpeg_unavailable_message,
			)

			return ffmpeg_unavailable_message()
		if not caps.has_gpu:
			return tr("unavailable.transcribe_gpu")
		return ""
	return ""


__all__ = [
	"Capabilities",
	"capabilities_to_dict",
	"default_capabilities",
	"probe_capabilities",
	"unavailable_reason",
]
