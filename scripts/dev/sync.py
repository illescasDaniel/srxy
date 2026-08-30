#!/usr/bin/env python3
"""Platform-aware ``uv sync`` for srxy checkouts.

Picks the ``[semantic]`` extra only when a GPU is available:

- Linux / Windows + NVIDIA → ``--extra semantic`` (skip with ``SRXY_SKIP_CUDA_TORCH=1``
  or empty ``CUDA_VISIBLE_DEVICES``)
- macOS Apple Silicon (MPS) → ``--extra semantic``
- No GPU → no semantic extra (core + optional groups only)
- Windows + NVIDIA: after sync, ``ensure-windows-cuda-torch.ps1`` as a safety net
  (``pywin32`` is a core Windows dependency)

CI does **not** use this script — workflows run ``uv sync --frozen`` (no semantic extras).

Modes (Taskipy: ``sync`` / ``sync-dev`` / ``sync-uploader``):

- runtime (default): project + extras, no default/dev groups (no pytest, ruff, …)
- ``--dev``: default ``dev`` group + extras
- ``--uploader``: default ``dev`` group + extras + ``uploader`` (twine)
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path


MODE_RUNTIME = "runtime"
MODE_DEV = "dev"
MODE_UPLOADER = "uploader"

_REPO_ROOT = Path(__file__).resolve().parents[2]

_USAGE = """\
Platform-aware uv sync for this checkout.

  uv run task sync            runtime extras (no pytest / ruff / taskipy)
  uv run task sync-dev        default for agents and local development
  uv run task sync-uploader   dev + twine (PyPI upload)

Same script:

  python scripts/dev/sync.py
  python scripts/dev/sync.py --dev
  python scripts/dev/sync.py --uploader

Linux / Windows + NVIDIA → --extra semantic
macOS Apple Silicon → --extra semantic
No GPU → no semantic extra (core only)

CI uses bare ``uv sync --frozen`` (no semantic extras).

Extra flags after the mode are forwarded to uv sync, e.g.
  python scripts/dev/sync.py --dev --offline --reinstall-package srxy
"""


def repo_root() -> Path:
	return _REPO_ROOT


def is_cuda_forced_off(environ: Mapping[str, str] | None = None) -> bool:
	env = os.environ if environ is None else environ
	if env.get("SRXY_SKIP_CUDA_TORCH", "").strip() == "1":
		return True
	# Empty CUDA_VISIBLE_DEVICES is the project's documented CPU-force for gates.
	if "CUDA_VISIBLE_DEVICES" in env and env.get("CUDA_VISIBLE_DEVICES", "").strip() == "":
		return True
	return False


def nvidia_gpu_present(*, environ: Mapping[str, str] | None = None) -> bool:
	if is_cuda_forced_off(environ):
		return False
	binary = shutil.which("nvidia-smi") or shutil.which("nvidia-smi.exe")
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
	return result.returncode == 0


def apple_mps_likely(*, system: str, machine: str) -> bool:
	"""True on Apple Silicon where PyTorch MPS is expected."""
	arch = machine.lower()
	return system == "darwin" and arch in {"arm64", "aarch64"}


def resolve_extras(
	*,
	system: str | None = None,
	machine: str | None = None,
	nvidia: bool | None = None,
	environ: Mapping[str, str] | None = None,
) -> list[str]:
	"""Return uv ``--extra`` names for this platform (empty when no GPU)."""
	plat = sys.platform if system is None else system
	arch = platform.machine() if machine is None else machine
	cuda_off = is_cuda_forced_off(environ)
	if nvidia is None:
		nvidia = False if cuda_off else nvidia_gpu_present(environ=environ)
	use_nvidia = bool(nvidia) and not cuda_off

	if apple_mps_likely(system=plat, machine=arch) and not cuda_off:
		return ["semantic"]
	if (plat.startswith("linux") or plat == "win32") and use_nvidia:
		return ["semantic"]
	return []


def build_uv_sync_command(
	mode: str,
	extras: Sequence[str],
	passthrough: Sequence[str] = (),
) -> list[str]:
	cmd = ["uv", "sync"]
	if mode == MODE_RUNTIME:
		cmd.append("--no-default-groups")
	for extra in extras:
		cmd.extend(["--extra", extra])
	if mode == MODE_UPLOADER:
		cmd.extend(["--group", "uploader"])
	cmd.extend(passthrough)
	return cmd


def windows_ensure_command(repo: Path | None = None) -> list[str] | None:
	root = _REPO_ROOT if repo is None else repo
	script = root / "scripts" / "dev" / "ensure-windows-cuda-torch.ps1"
	if not script.is_file():
		return None
	shell = shutil.which("pwsh") or shutil.which("powershell") or shutil.which("powershell.exe")
	if shell is None:
		return None
	return [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]


def _strip_separator(argv: Sequence[str]) -> list[str]:
	return [a for a in argv if a != "--"]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		prog="sync.py",
		description=_USAGE,
		formatter_class=argparse.RawDescriptionHelpFormatter,
	)
	mode = parser.add_mutually_exclusive_group()
	mode.add_argument(
		"--dev",
		action="store_true",
		help="include the default dev group (pytest, ruff, taskipy, …)",
	)
	mode.add_argument(
		"--uploader",
		action="store_true",
		help="dev group plus the uploader group (twine)",
	)
	parser.add_argument(
		"--dry-run",
		action="store_true",
		help="print the uv (and Windows ensure) command without running it",
	)
	parser.add_argument(
		"--skip-ensure",
		action="store_true",
		help="skip ensure-windows-cuda-torch.ps1 even on Windows",
	)
	args, unknown = parser.parse_known_args(argv)
	if args.dev:
		args.mode = MODE_DEV
	elif args.uploader:
		args.mode = MODE_UPLOADER
	else:
		args.mode = MODE_RUNTIME
	args.passthrough = _strip_separator(unknown)
	return args


def _run(cmd: Sequence[str], *, dry_run: bool, cwd: Path) -> int:
	printable = " ".join(cmd)
	print(f"sync: {printable}", flush=True)
	if dry_run:
		return 0
	completed = subprocess.run(cmd, cwd=cwd, check=False)  # noqa: S603
	return int(completed.returncode)


def main(argv: Sequence[str] | None = None) -> int:
	args = parse_args(argv)
	root = repo_root()
	extras = resolve_extras()
	uv_cmd = build_uv_sync_command(args.mode, extras, args.passthrough)
	code = _run(uv_cmd, dry_run=args.dry_run, cwd=root)
	if code != 0:
		return code

	# CUDA ensure only when we selected the semantic extra on Windows.
	if (
		sys.platform == "win32"
		and "semantic" in extras
		and not args.skip_ensure
		and not is_cuda_forced_off()
	):
		ensure = windows_ensure_command(root)
		if ensure is None:
			print("sync: warning: Windows CUDA ensure script or PowerShell not found", file=sys.stderr)
			return 0
		return _run(ensure, dry_run=args.dry_run, cwd=root)
	return 0


if __name__ == "__main__":
	sys.exit(main())
