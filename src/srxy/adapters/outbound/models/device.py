from __future__ import annotations

import contextlib
import gc
import os
import sys


_CPU_WARNING_CONTEXTS: set[str] = set()


def drop_torch_cache_object(obj: object | None):
	"""Best-effort move a cached model off GPU before dropping the last reference.

	Handles ``nn.Module`` / SentenceTransformer (``.to``), HF pipelines (``.model``),
	and nested wrappers. Safe no-op for non-torch objects and when CUDA is absent.
	"""
	if obj is None:
		return
	seen: set[int] = set()

	def _drop(value: object | None):
		if value is None:
			return
		identity = id(value)
		if identity in seen:
			return
		seen.add(identity)
		inner = getattr(value, "model", None)
		if inner is not None and inner is not value:
			_drop(inner)
		to_fn = getattr(value, "to", None)
		if callable(to_fn):
			with contextlib.suppress(Exception):
				to_fn("cpu")

	if isinstance(obj, tuple):
		for item in obj:
			_drop(item)
	else:
		_drop(obj)


def release_cuda_memory():
	"""Return freed CUDA blocks to the driver after model singletons are cleared.

	``reset_*_model`` helpers only drop Python refs; without ``empty_cache`` the
	caching allocator keeps VRAM reserved and the heavy integration suite OOMs
	once semantic + CLIP + whisper have each been loaded in one process.
	"""
	gc.collect()
	if not _torch_available():
		return
	import torch

	if not torch.cuda.is_available():
		return
	with contextlib.suppress(Exception):
		torch.cuda.synchronize()
	torch.cuda.empty_cache()
	ipc_collect = getattr(torch.cuda, "ipc_collect", None)
	if callable(ipc_collect):
		with contextlib.suppress(Exception):
			ipc_collect()


def _torch_available() -> bool:
	import importlib.util

	# Tests inject a MagicMock via sys.modules; find_spec raises ValueError without __spec__.
	mod = sys.modules.get("torch")
	if mod is not None:
		return True
	try:
		return importlib.util.find_spec("torch") is not None
	except (ImportError, ValueError, ModuleNotFoundError):
		return False


def _auto_torch_device() -> str:
	# Core installs omit [semantic]; treat missing torch as CPU without importing.
	if not _torch_available():
		return "cpu"

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
