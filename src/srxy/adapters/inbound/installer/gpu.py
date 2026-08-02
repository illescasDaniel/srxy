"""Detect a GPU usable for PyTorch-accelerated features (installer probe).

Linux/Windows today: NVIDIA CUDA via nvidia-smi / device nodes (no torch import).
macOS Apple MPS can be added later when the macOS installer lands.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def nvidia_smi_available() -> bool:
	return shutil.which("nvidia-smi") is not None


def nvidia_device_nodes_present() -> bool:
	return Path("/dev/nvidia0").exists() or Path("/proc/driver/nvidia/version").is_file()


def nvidia_smi_reports_gpu() -> bool:
	binary = shutil.which("nvidia-smi")
	if binary is None:
		return False
	try:
		result = subprocess.run(  # noqa: S603
			[binary, "-L"],
			capture_output=True,
			text=True,
			timeout=5,
			check=False,
		)
	except (OSError, subprocess.TimeoutExpired):
		return False
	if result.returncode != 0:
		return False
	return "GPU" in (result.stdout or "")


def has_nvidia_gpu() -> bool:
	"""Best-effort NVIDIA CUDA probe without importing torch."""
	if os.environ.get("SRXY_INSTALLER_FORCE_GPU", "").strip().lower() in {"1", "true", "yes", "on"}:
		return True
	if os.environ.get("SRXY_INSTALLER_FORCE_NO_GPU", "").strip().lower() in {"1", "true", "yes", "on"}:
		return False
	if nvidia_smi_reports_gpu():
		return True
	return nvidia_device_nodes_present()


def has_accelerated_gpu() -> bool:
	"""True when a PyTorch-compatible accelerator is available for AI extras.

	Currently NVIDIA CUDA on Linux. Apple MPS will plug in here for macOS.
	"""
	return has_nvidia_gpu()


def no_gpu_semantic_message() -> str:
	return (
		"No usable GPU found. AI extras (similar meaning, pictures, and spoken words) "
		"need a GPU, so those options are turned off. You can still install srxy for "
		"names, documents, and text in images."
	)


__all__ = [
	"has_accelerated_gpu",
	"has_nvidia_gpu",
	"no_gpu_semantic_message",
	"nvidia_device_nodes_present",
	"nvidia_smi_available",
	"nvidia_smi_reports_gpu",
]
