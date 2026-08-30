"""Ensure a Windows prefix venv gets CUDA PyTorch when an NVIDIA GPU is present.

``uv pip install 'srxy[semantic]'`` (and ``uv sync --extra semantic``) resolve
PyTorch from PyPI as a CPU-only wheel on Windows. Semantic / CLIP / transcription
then silently run on CPU. After installing the semantic extra, reinstall
torch/torchvision/torchaudio from the official PyTorch CUDA wheel index.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from srxy.application.gpu_availability import has_nvidia_gpu


DEFAULT_CUDA_INDEX = "cu130"
FALLBACK_CUDA_INDEX = "cu126"
_TORCH_PACKAGES: tuple[str, ...] = ("torch", "torchvision", "torchaudio")
_CUDA_BUILD_RE = re.compile(r"\+cu\d+", re.IGNORECASE)

RunFn = Callable[..., None]


@dataclass(frozen=True, slots=True)
class TorchProbe:
	version: str
	cuda_available: bool

	@property
	def is_cuda_build(self) -> bool:
		return bool(_CUDA_BUILD_RE.search(self.version))


def cuda_wheel_index_url(cuda_index: str = DEFAULT_CUDA_INDEX) -> str:
	return f"https://download.pytorch.org/whl/{cuda_index}"


def should_ensure_windows_cuda_torch(*, install_semantic: bool, is_windows: bool) -> bool:
	"""Whether the installer should plan/run the CUDA torch step."""
	if not install_semantic or not is_windows:
		return False
	if os.environ.get("SRXY_SKIP_CUDA_TORCH", "").strip().lower() in {"1", "true", "yes", "on"}:
		return False
	# Empty CUDA_VISIBLE_DEVICES is the documented CPU-force; leave the venv alone.
	if (
		os.environ.get("CUDA_VISIBLE_DEVICES", None) is not None
		and os.environ.get("CUDA_VISIBLE_DEVICES", "").strip() == ""
	):
		return False
	return has_nvidia_gpu()


def probe_torch(
	python: Path,
	*,
	env: Mapping[str, str] | None = None,
	run_probe: Callable[..., object] | None = None,
) -> TorchProbe | None:
	"""Return torch version / cuda availability from ``python``, or None on failure."""
	import subprocess

	code = "import torch\nprint(torch.__version__)\nprint('1' if torch.cuda.is_available() else '0')\n"
	runner = run_probe or subprocess.run
	try:
		result = runner(  # noqa: S603
			[str(python), "-c", code],
			capture_output=True,
			text=True,
			check=False,
			env=dict(env) if env is not None else None,
		)
	except OSError:
		return None
	returncode = getattr(result, "returncode", 1)
	stdout = getattr(result, "stdout", "") or ""
	if returncode != 0:
		return None
	lines = [line.strip() for line in str(stdout).splitlines() if line.strip()]
	if len(lines) < 2:
		return None
	return TorchProbe(version=lines[0], cuda_available=lines[1] == "1")


def _pip_install_cuda_torch_cmd(
	uv: Path,
	*,
	cuda_index: str,
) -> list[str]:
	return [
		str(uv),
		"pip",
		"install",
		"--reinstall-package",
		"torch",
		*_TORCH_PACKAGES,
		"--index-url",
		cuda_wheel_index_url(cuda_index),
	]


def ensure_windows_cuda_torch(
	*,
	uv: Path,
	python: Path,
	env: Mapping[str, str],
	run: RunFn,
	cuda_index: str = DEFAULT_CUDA_INDEX,
	fallback_index: str = FALLBACK_CUDA_INDEX,
	probe: Callable[..., TorchProbe | None] | None = None,
) -> str:
	"""Reinstall CUDA torch into the active venv when needed.

	Returns one of: ``skipped``, ``ok``, ``installed``.
	Raises on install failure after fallbacks are exhausted.
	"""
	probe_fn = probe or probe_torch
	status = probe_fn(python, env=env)
	if status is not None and status.is_cuda_build:
		return "ok"

	indexes: Sequence[str] = (cuda_index,)
	if fallback_index and fallback_index != cuda_index:
		indexes = (cuda_index, fallback_index)

	last_error: Exception | None = None
	for index in indexes:
		cmd = _pip_install_cuda_torch_cmd(uv, cuda_index=index)
		try:
			run(cmd, env=dict(env))
		except Exception as exc:  # noqa: BLE001 - try fallback index
			last_error = exc
			continue
		after = probe_fn(python, env=env)
		if after is not None and after.is_cuda_build:
			return "installed"
		last_error = RuntimeError(
			f"CUDA PyTorch install from {cuda_wheel_index_url(index)} finished but "
			f"torch is still not a +cu* build (got {after.version if after else 'unavailable'})."
		)

	if last_error is not None:
		raise last_error
	raise RuntimeError("CUDA PyTorch install failed")


__all__ = [
	"DEFAULT_CUDA_INDEX",
	"FALLBACK_CUDA_INDEX",
	"TorchProbe",
	"cuda_wheel_index_url",
	"ensure_windows_cuda_torch",
	"probe_torch",
	"should_ensure_windows_cuda_torch",
]
