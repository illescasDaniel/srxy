#!/usr/bin/env python3
"""OS-aware quality gate dispatcher for srxy.

Forwards documented flags to ``scripts/quality/checks.sh`` (Unix) or
``scripts/quality/checks-win.ps1`` (Windows). The underlying scripts remain
the real gate; CI still invokes ``checks.sh`` directly.

Taskipy:

  uv run task checks
  uv run task checks -- --quiet --fix
  uv run task checks -- --quiet --gui
  uv run task checks -- --quiet --full

Direct (no Taskipy):

  uv run python scripts/quality/checks.py --help
  ./scripts/quality/checks.sh --quiet --fix
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

_USAGE = """\
OS-aware quality gate for this checkout.

Taskipy (pass flags after ``--`` so ``uv run`` does not consume them):

  uv run task checks
  uv run task checks -- --quiet --fix
  uv run task checks -- --quiet --gui
  uv run task checks -- --quiet --full
  uv run task checks -- --quiet --full+cpu

Direct:

  uv run python scripts/quality/checks.py
  ./scripts/quality/checks.sh --quiet --fix          # Unix
  .\\scripts\\quality\\checks-win.ps1 --quiet --fix   # Windows

Defaults: verbose output, auto-scope from git diff/status.
AI agents should pass ``--quiet``. Humans omit it for full gate logs.
"""


@dataclass(frozen=True, slots=True)
class ChecksOptions:
	fix: bool = False
	full: bool = False
	full_cpu: bool = False
	quiet: bool = False
	timings: bool = False
	no_cache: bool = False
	scope: str | None = None
	all_buckets: bool = False
	core: bool = False
	cli: bool = False
	tui: bool = False
	gui: bool = False


def repo_root() -> Path:
	return _REPO_ROOT


def _strip_separator(argv: Sequence[str]) -> list[str]:
	return [a for a in argv if a != "--"]


def to_script_args(options: ChecksOptions) -> list[str]:
	"""Build argv for checks.sh / checks-win.ps1 from parsed options."""
	args: list[str] = []
	if options.fix:
		args.append("--fix")
	if options.full:
		args.append("--full")
	if options.full_cpu:
		args.append("--full+cpu")
	if options.quiet:
		args.append("--quiet")
	if options.timings:
		args.append("--timings")
	if options.no_cache:
		args.append("--no-cache")
	if options.scope is not None:
		args.append(f"--scope={options.scope}")
	if options.all_buckets:
		args.append("--all")
	if options.core:
		args.append("--core")
	if options.cli:
		args.append("--cli")
	if options.tui:
		args.append("--tui")
	if options.gui:
		args.append("--gui")
	return args


def unix_script_path(root: Path | None = None) -> Path:
	repo = repo_root() if root is None else root
	return repo / "scripts" / "quality" / "checks.sh"


def windows_script_path(root: Path | None = None) -> Path:
	repo = repo_root() if root is None else root
	return repo / "scripts" / "quality" / "checks-win.ps1"


def windows_shell() -> str | None:
	return shutil.which("pwsh") or shutil.which("powershell") or shutil.which("powershell.exe")


def script_command(
	options: ChecksOptions,
	*,
	platform: str | None = None,
	root: Path | None = None,
) -> list[str]:
	"""Return the full command line for the current (or given) platform."""
	plat = sys.platform if platform is None else platform
	repo = repo_root() if root is None else root
	script_args = to_script_args(options)

	if plat == "win32":
		ps1 = windows_script_path(repo)
		shell = windows_shell()
		if shell is None:
			raise RuntimeError("PowerShell not found (need pwsh or powershell on PATH)")
		if not ps1.is_file():
			raise FileNotFoundError(f"Windows gate script not found: {ps1}")
		return [
			shell,
			"-NoProfile",
			"-ExecutionPolicy",
			"Bypass",
			"-File",
			str(ps1),
			*script_args,
		]

	sh = unix_script_path(repo)
	if not sh.is_file():
		raise FileNotFoundError(f"Unix gate script not found: {sh}")
	return [str(sh), *script_args]


def parse_args(argv: Sequence[str] | None = None) -> ChecksOptions:
	parser = argparse.ArgumentParser(
		prog="checks.py",
		description=_USAGE,
		formatter_class=argparse.RawDescriptionHelpFormatter,
	)
	parser.add_argument(
		"--fix",
		action="store_true",
		help="autofix Ruff/shell, then run remaining gate steps",
	)
	parser.add_argument(
		"--full",
		action="store_true",
		help="pre-release gate: all buckets, coverage, no testmon",
	)
	parser.add_argument(
		"--full+cpu",
		"--full-cpu",
		dest="full_cpu",
		action="store_true",
		help="--full plus forced-CPU transcribe matrix on heavy",
	)
	parser.add_argument(
		"--quiet",
		action="store_true",
		help="agent-verbosity: sparse progress, full failures",
	)
	parser.add_argument(
		"--timings",
		action="store_true",
		help="append pytest --durations=25 and print per-step seconds",
	)
	parser.add_argument(
		"--no-cache",
		action="store_true",
		help="force pip-audit and wheel build (skip .gate-cache)",
	)
	parser.add_argument(
		"--scope",
		metavar="BUCKETS",
		help="comma-separated pytest buckets (e.g. core,gui)",
	)
	parser.add_argument(
		"--all",
		dest="all_buckets",
		action="store_true",
		help="run all pytest buckets",
	)
	parser.add_argument(
		"--core",
		action="store_true",
		help="scope to core bucket (tests/unit, tests/cli)",
	)
	parser.add_argument(
		"--cli",
		action="store_true",
		help="scope to cli (alias for core; cli tests live under tests/cli)",
	)
	parser.add_argument(
		"--tui",
		action="store_true",
		help="scope to tui bucket",
	)
	parser.add_argument(
		"--gui",
		action="store_true",
		help="scope to gui bucket",
	)
	raw = _strip_separator(argv if argv is not None else sys.argv[1:])
	ns = parser.parse_args(raw)
	if ns.full_cpu:
		ns.full = True
	return ChecksOptions(
		fix=ns.fix,
		full=ns.full,
		full_cpu=ns.full_cpu,
		quiet=ns.quiet,
		timings=ns.timings,
		no_cache=ns.no_cache,
		scope=ns.scope,
		all_buckets=ns.all_buckets,
		core=ns.core,
		cli=ns.cli,
		tui=ns.tui,
		gui=ns.gui,
	)


def _kill_process_group(proc: subprocess.Popen[bytes], sig: signal.Signals) -> None:
	if proc.poll() is not None:
		return
	try:
		os.killpg(proc.pid, sig)
	except (ProcessLookupError, PermissionError):
		try:
			proc.send_signal(sig)
		except ProcessLookupError:
			pass


def _wait_after_interrupt(proc: subprocess.Popen[bytes]) -> int:
	print("note: quality gate interrupted — stopping child processes...", flush=True)
	_kill_process_group(proc, signal.SIGINT)
	deadline = time.monotonic() + 5.0
	while proc.poll() is None and time.monotonic() < deadline:
		time.sleep(0.1)
	if proc.poll() is None:
		_kill_process_group(proc, signal.SIGKILL)
		try:
			proc.wait(timeout=5)
		except subprocess.TimeoutExpired:
			pass
	return 130 if proc.returncode is None else int(proc.returncode)


def run_gate_command(cmd: Sequence[str], *, cwd: Path) -> int:
	"""Run the platform gate script; forward Ctrl+C to the child process group."""
	proc = subprocess.Popen(  # noqa: S603
		list(cmd),
		cwd=cwd,
		start_new_session=True,
	)

	def _handle_signal(signum: int, _frame: object) -> None:
		sig = signal.Signals(signum)
		_kill_process_group(proc, sig)

	previous_int = signal.getsignal(signal.SIGINT)
	previous_term = signal.getsignal(signal.SIGTERM)
	signal.signal(signal.SIGINT, _handle_signal)
	signal.signal(signal.SIGTERM, _handle_signal)
	try:
		return int(proc.wait())
	except KeyboardInterrupt:
		return _wait_after_interrupt(proc)
	finally:
		signal.signal(signal.SIGINT, previous_int)
		signal.signal(signal.SIGTERM, previous_term)


def main(argv: Sequence[str] | None = None) -> int:
	options = parse_args(argv)
	root = repo_root()
	cmd = script_command(options, root=root)
	printable = " ".join(cmd)
	print(f"checks: {printable}", flush=True)
	return run_gate_command(cmd, cwd=root)


if __name__ == "__main__":
	sys.exit(main())
