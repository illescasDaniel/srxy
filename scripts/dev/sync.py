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

First-time / bootstrap (never loads the project venv):

  uv run --no-project python scripts/dev/sync.py
  uv run --no-project python scripts/dev/sync.py --group uploader
  uv run --no-project python scripts/dev/sync.py --no-default-groups

Once ``.venv`` exists, thin Taskipy wrappers also work:

  uv run task sync-dev
  uv run task sync-uploader

All ``uv sync`` flags (``--group``, ``--no-default-groups``, ``--offline``, …) pass
through verbatim. Pruning syncs (``--no-default-groups``, ``--only-group``) are refused
when this script runs from inside the project ``.venv`` unless ``--force`` is set.
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

_PRUNING_FLAGS = frozenset({"--no-default-groups", "--only-group"})

_REPO_ROOT = Path(__file__).resolve().parents[2]

_USAGE = """\
Platform-aware uv sync for this checkout.

Bootstrap (same on every OS — does not use the project venv):

  uv run --no-project python scripts/dev/sync.py
  uv run --no-project python scripts/dev/sync.py --group uploader
  uv run --no-project python scripts/dev/sync.py --no-default-groups

Or use the wrappers: ./scripts/dev/sync.sh (Unix) / .\\scripts\\dev\\sync.ps1 (Windows)

Once .venv exists:

  uv run task sync-dev
  uv run task sync-uploader

Linux / Windows + NVIDIA → --extra semantic
macOS Apple Silicon → --extra semantic
No GPU → no semantic extra (core only)

CI uses bare ``uv sync --frozen`` (no semantic extras).

Extra uv sync flags pass through, e.g.
  uv run --no-project python scripts/dev/sync.py --offline --reinstall-package srxy
"""


def repo_root() -> Path:
	return _REPO_ROOT


def project_venv_path() -> Path:
	return repo_root() / ".venv"


def running_inside_project_venv() -> bool:
	try:
		venv = project_venv_path().resolve()
		prefix = Path(sys.prefix).resolve()
	except OSError:
		return False
	return prefix == venv or venv in prefix.parents


def passthrough_prunes(passthrough: Sequence[str]) -> bool:
	return any(flag.split("=", 1)[0] in _PRUNING_FLAGS for flag in passthrough)


def bootstrap_command(*, passthrough: Sequence[str] = ()) -> str:
	args = ["uv", "run", "--no-project", "python", "scripts/dev/sync.py", *passthrough]
	return " ".join(args)


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
	extras: Sequence[str],
	passthrough: Sequence[str] = (),
) -> list[str]:
	cmd = ["uv", "sync"]
	for extra in extras:
		cmd.extend(["--extra", extra])
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
	parser.add_argument(
		"--force",
		action="store_true",
		help="allow pruning sync flags even when running from the project .venv",
	)
	args, unknown = parser.parse_known_args(argv)
	args.passthrough = _strip_separator(unknown)
	return args


def _run(cmd: Sequence[str], *, dry_run: bool, cwd: Path) -> int:
	printable = " ".join(cmd)
	print(f"sync: {printable}", flush=True)
	if dry_run:
		return 0
	completed = subprocess.run(cmd, cwd=cwd, check=False)  # noqa: S603
	return int(completed.returncode)


def _refuse_pruning_sync(*, passthrough: Sequence[str]) -> int:
	print(
		"sync: error: pruning sync flags cannot run from the project .venv "
		"(loaded packages such as taskipy/psutil would block removal on Windows).",
		file=sys.stderr,
	)
	print(f"sync: rerun with: {bootstrap_command(passthrough=passthrough)}", file=sys.stderr)
	print("sync: or pass --force to override.", file=sys.stderr)
	return 1


def main(argv: Sequence[str] | None = None) -> int:
	args = parse_args(argv)
	root = repo_root()
	if (
		not args.force
		and running_inside_project_venv()
		and passthrough_prunes(args.passthrough)
	):
		return _refuse_pruning_sync(passthrough=args.passthrough)

	extras = resolve_extras()
	uv_cmd = build_uv_sync_command(extras, args.passthrough)
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
