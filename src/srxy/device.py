from __future__ import annotations

import os
import sys


_CPU_WARNING_CONTEXTS: set[str] = set()


def _torch_available() -> bool:
	import importlib.util

	return importlib.util.find_spec("torch") is not None


def _auto_torch_device() -> str:
	import torch

	if torch.cuda.is_available():
		return "cuda"
	mps_backend = getattr(torch.backends, "mps", None)
	if mps_backend is not None and mps_backend.is_available():
		return "mps"
	return "cpu"


def _validate_torch_device(requested: str) -> str:
	if not _torch_available():
		return "cpu"

	import torch

	if requested == "cuda":
		if torch.cuda.is_available():
			return "cuda"
		print(
			"warning: SRXY requested CUDA but no GPU is available; using CPU instead.",
			file=sys.stderr,
		)
		return "cpu"
	if requested == "mps":
		mps_backend = getattr(torch.backends, "mps", None)
		if mps_backend is not None and mps_backend.is_available():
			return "mps"
		print(
			"warning: SRXY requested MPS but Apple GPU backend is unavailable; using CPU instead.",
			file=sys.stderr,
		)
		return "cpu"
	return "cpu"


def resolve_torch_device() -> str:
	forced = os.environ.get("SRXY_SEMANTIC_DEVICE", "").strip().lower()
	if forced in {"cpu", "cuda", "mps"}:
		return _validate_torch_device(forced)
	return _auto_torch_device()


def resolve_semantic_image_device() -> str:
	for env_var in ("SRXY_SEMANTIC_IMAGE_DEVICE", "SRXY_SEMANTIC_DEVICE"):
		forced = os.environ.get(env_var, "").strip().lower()
		if forced in {"cpu", "cuda", "mps"}:
			return _validate_torch_device(forced)
	return _auto_torch_device()


def warn_if_cpu_device(device: str, *, context: str):
	if device != "cpu" or context in _CPU_WARNING_CONTEXTS or not _torch_available():
		return

	import torch

	if torch.cuda.is_available():
		return
	mps_backend = getattr(torch.backends, "mps", None)
	if mps_backend is not None and mps_backend.is_available():
		return

	print(
		f"warning: no GPU found; {context} will use CPU (slower). "
		"Set SRXY_SEMANTIC_IMAGE_DEVICE or SRXY_SEMANTIC_DEVICE to override.",
		file=sys.stderr,
	)
	_CPU_WARNING_CONTEXTS.add(context)


def resolve_transcribe_device() -> str:
	for env_var in ("SRXY_TRANSCRIBE_DEVICE", "SRXY_SEMANTIC_DEVICE"):
		forced = os.environ.get(env_var, "").strip().lower()
		if forced in {"cpu", "cuda", "mps"}:
			return _validate_torch_device(forced)
	return _auto_torch_device()


def transcribe_backend_for_device(device: str) -> str:
	if device == "mps":
		return "transformers"
	return "faster-whisper"


def transcribe_compute_type(device: str) -> str:
	if device == "cuda":
		return "float16"
	return "int8"
