"""Detect a GPU usable for PyTorch-accelerated features — without importing torch.

Importing torch (and initializing CUDA) on a QThread while ``QGuiApplication`` is
running can SIGSEGV. Calling ``nvidia-smi`` via ``subprocess`` is also unsafe
while other QThreads are alive (fork + multithreaded Qt).

GUI probes should use :func:`has_accelerated_gpu_nofork`. The installer may use
:func:`has_accelerated_gpu`, which can call ``nvidia-smi`` before Qt workers start.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
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


def _env_force_gpu() -> bool | None:
	if os.environ.get("SRXY_FORCE_GPU", "").strip().lower() in {"1", "true", "yes", "on"}:
		return True
	if os.environ.get("SRXY_FORCE_NO_GPU", "").strip().lower() in {"1", "true", "yes", "on"}:
		return False
	# Installer-specific aliases (kept for existing docs/scripts).
	if os.environ.get("SRXY_INSTALLER_FORCE_GPU", "").strip().lower() in {"1", "true", "yes", "on"}:
		return True
	if os.environ.get("SRXY_INSTALLER_FORCE_NO_GPU", "").strip().lower() in {"1", "true", "yes", "on"}:
		return False
	return None


def has_apple_mps_gpu() -> bool:
	"""True on Apple Silicon where PyTorch MPS is expected to be available."""
	return sys.platform == "darwin" and platform.machine() == "arm64"


def _has_nvidia_windows_nofork() -> bool:
	"""Detect NVIDIA GPU on Windows without any subprocess or torch import.

	Checks for NVAPI / CUDA DLL presence (driver-installed artefacts) and, as
	a fallback, the kernel-mode driver service registry key.  Both are safe to
	call from Qt worker threads.
	"""
	if sys.platform != "win32":
		return False

	# Fast path: NVAPI and CUDA stub DLLs exist whenever NVIDIA drivers are
	# installed — no subprocess required.
	sysroot = Path(os.environ.get("SystemRoot", r"C:\Windows"))
	system32 = sysroot / "System32"
	if (system32 / "nvapi64.dll").is_file() or (system32 / "nvcuda.dll").is_file():
		return True

	# Fallback: kernel-mode display driver service key (present even when the
	# DLL search path differs, e.g. WOW64-redirected System32).
	try:
		import winreg  # stdlib, safe for QThread contexts — no fork, no subprocess

		with winreg.OpenKey(
			winreg.HKEY_LOCAL_MACHINE,
			r"SYSTEM\CurrentControlSet\Services\nvlddmkm",
		):
			return True
	except (ImportError, OSError):
		pass

	return False


def has_accelerated_gpu_nofork() -> bool:
	"""Qt-safe accelerator probe: no torch import and no subprocess/fork."""
	forced = _env_force_gpu()
	if forced is not None:
		return forced
	return nvidia_device_nodes_present() or _has_nvidia_windows_nofork() or has_apple_mps_gpu()


def has_nvidia_gpu() -> bool:
	"""Best-effort NVIDIA CUDA probe without importing torch.

	May shell out to ``nvidia-smi`` — do not call from a process that already has
	extra QThreads (use :func:`has_accelerated_gpu_nofork` instead).
	"""
	forced = _env_force_gpu()
	if forced is not None:
		return forced
	if nvidia_smi_reports_gpu():
		return True
	return nvidia_device_nodes_present()


def has_accelerated_gpu() -> bool:
	"""True when a PyTorch-compatible accelerator is likely available for AI extras.

	May use ``nvidia-smi`` (subprocess). Prefer :func:`has_accelerated_gpu_nofork`
	once Qt worker threads exist.
	"""
	forced = _env_force_gpu()
	if forced is not None:
		return forced
	return has_nvidia_gpu() or has_apple_mps_gpu()


__all__ = [
	"has_accelerated_gpu",
	"has_accelerated_gpu_nofork",
	"has_apple_mps_gpu",
	"has_nvidia_gpu",
	"nvidia_device_nodes_present",
	"nvidia_smi_available",
	"nvidia_smi_reports_gpu",
	"_has_nvidia_windows_nofork",
]
