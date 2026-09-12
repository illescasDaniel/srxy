"""Unit tests for quality gate lock file metadata (lib.sh helpers)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[2]
_LIB = _REPO / "scripts" / "quality" / "internal" / "lib.sh"


def _bash_lib_snippet(body: str) -> subprocess.CompletedProcess[str]:
	script = f'''
set -euo pipefail
# shellcheck source=scripts/quality/internal/lib.sh
source "{_LIB}"
{body}
'''
	bash = shutil.which("bash") or "bash"
	return subprocess.run(  # noqa: S603
		[bash, "-c", script],
		capture_output=True,
		text=True,
		check=False,
		cwd=_REPO,
	)


def test_given_child_pids_when_building_csv_then_lists_unique_main_and_children():
	# given / when
	result = _bash_lib_snippet(
		"""
export LIB_GATE_LOCK_MAIN_PID=100
LIB_GATE_CHILD_PIDS=(200 300 200)
lib_gate_lock_pid_csv
"""
	)

	# then
	assert result.returncode == 0
	assert result.stdout.strip() == "100,200,300"


def test_given_lock_metadata_when_printing_holder_then_reports_pids():
	# given
	lock_path = _REPO / ".test-gate-lock-sample"
	lock_path.write_text(
		"pid=99999\npids=99999\nstatus=running\nscript=checks.sh\n",
		encoding="utf-8",
	)
	try:
		result = _bash_lib_snippet(
			f"""
lib_gate_print_lock_holder "{lock_path}"
"""
		)
	finally:
		lock_path.unlink(missing_ok=True)

	# then
	assert result.returncode == 0
	assert "Lock holder metadata:" in result.stderr
	assert "pid=99999" in result.stderr
	assert "Process check:" in result.stderr
