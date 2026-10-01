"""Unit tests for scripts/quality/checks.py OS dispatch."""

from __future__ import annotations

import importlib.util
import io
import signal
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[2]
_CHECKS_SCRIPT = _REPO / "scripts" / "quality" / "checks.py"


def _load_checks_module():
	spec = importlib.util.spec_from_file_location("srxy_quality_checks", _CHECKS_SCRIPT)
	assert spec is not None and spec.loader is not None
	module = importlib.util.module_from_spec(spec)
	sys.modules[spec.name] = module
	spec.loader.exec_module(module)
	return module


def test_given_quiet_fix_flags_when_building_script_args_then_forwards_canonical_flags():
	# given
	checks = _load_checks_module()
	options = checks.ChecksOptions(fix=True, quiet=True)

	# when
	args = checks.to_script_args(options)

	# then
	assert args == ["--fix", "--quiet"]


def test_given_scope_buckets_when_building_script_args_then_emits_scope_equals_form():
	# given
	checks = _load_checks_module()
	options = checks.ChecksOptions(scope="core,gui")

	# when
	args = checks.to_script_args(options)

	# then
	assert args == ["--scope=core,gui"]


def test_given_full_cpu_flag_when_parsing_args_then_sets_full_and_full_cpu():
	# given
	checks = _load_checks_module()

	# when
	options = checks.parse_args(["--full+cpu"])

	# then
	assert options.full is True
	assert options.full_cpu is True
	assert checks.to_script_args(options) == ["--full", "--full+cpu"]


def test_given_full_cpu_alias_when_parsing_args_then_sets_full_and_full_cpu():
	# given
	checks = _load_checks_module()

	# when
	options = checks.parse_args(["--full-cpu"])

	# then
	assert options.full is True
	assert options.full_cpu is True


def test_given_unix_platform_when_building_command_then_uses_checks_sh():
	# given
	checks = _load_checks_module()
	options = checks.ChecksOptions(quiet=True, gui=True)
	root = _REPO

	# when
	cmd = checks.script_command(options, platform="linux", root=root)

	# then
	assert cmd[0] == str(checks.unix_script_path(root))
	assert cmd[1:] == ["--quiet", "--gui"]


def test_given_windows_platform_when_building_command_then_uses_powershell_and_ps1():
	# given
	checks = _load_checks_module()
	options = checks.ChecksOptions(quiet=True, fix=True)
	root = _REPO

	# when
	with patch.object(checks, "windows_shell", return_value="/usr/bin/pwsh"):
		cmd = checks.script_command(options, platform="win32", root=root)

	# then
	assert cmd[0] == "/usr/bin/pwsh"
	assert "-File" in cmd
	assert str(checks.windows_script_path(root)) in cmd
	assert "--quiet" in cmd
	assert "--fix" in cmd


def test_given_help_flag_when_parsing_args_then_lists_documented_flags():
	# given
	checks = _load_checks_module()
	stdout = io.StringIO()

	# when
	with patch.object(sys, "argv", ["checks.py", "--help"]):
		with patch.object(sys, "stdout", stdout):
			with pytest.raises(SystemExit) as exc:
				checks.main(["--help"])

	# then
	assert exc.value.code == 0
	help_text = stdout.getvalue()
	for flag in ("--fix", "--full", "--quiet", "--scope", "--gui", "--all"):
		assert flag in help_text


def test_given_taskipy_separator_when_parsing_args_then_strips_leading_dashes():
	# given
	checks = _load_checks_module()

	# when
	options = checks.parse_args(["--", "--quiet", "--gui"])

	# then
	assert options.quiet is True
	assert options.gui is True


def test_given_all_scope_shorthands_when_building_script_args_then_forwards_each_flag():
	# given
	checks = _load_checks_module()
	options = checks.ChecksOptions(all_buckets=True, core=True, cli=True, tui=True, gui=True)

	# when
	args = checks.to_script_args(options)

	# then
	assert args == ["--all", "--core", "--cli", "--tui", "--gui"]


def test_given_true_command_when_running_gate_command_then_returns_zero():
	# given
	checks = _load_checks_module()

	# when
	code = checks.run_gate_command(["true"], cwd=_REPO)

	# then
	assert code == 0


def test_given_keyboard_interrupt_when_running_gate_command_then_returns_130(monkeypatch):
	# given
	checks = _load_checks_module()

	class _FakeProc:
		pid = 4242
		returncode = None
		_wait_calls = 0

		def poll(self):
			return self.returncode

		def wait(self, timeout=None):
			self._wait_calls += 1
			if self._wait_calls == 1:
				raise KeyboardInterrupt
			self.returncode = 130
			return 130

	fake = _FakeProc()
	monkeypatch.setattr(checks.subprocess, "Popen", lambda *args, **kwargs: fake)
	monkeypatch.setattr(checks, "_kill_process_group", lambda *args: None)

	# when
	code = checks.run_gate_command(["bash", "-c", "sleep 120"], cwd=_REPO)

	# then
	assert code == 130


def test_given_no_sigkill_attribute_when_resolving_force_kill_signal_then_falls_back_to_sigterm(
	monkeypatch,
):
	"""Windows Python has no signal.SIGKILL at all — the real failure mode this
	guards against is an AttributeError raised just from *referencing*
	signal.SIGKILL, which crashed the interrupted-gate path under Windows CI (and,
	via a dead xdist worker, took unrelated tests down alongside it)."""
	# given — simulate Windows: signal.SIGKILL does not exist on the real module
	# (checks.py does `import signal`, so this is the same module object).
	checks = _load_checks_module()
	monkeypatch.delattr(checks.signal, "SIGKILL", raising=False)

	# when
	resolved = checks._force_kill_signal()

	# then
	assert resolved == signal.SIGTERM


def test_given_no_killpg_when_kill_process_group_then_falls_back_to_send_signal(monkeypatch):
	"""os.killpg does not exist on Windows (process groups are a POSIX concept);
	_kill_process_group must fall back to Popen.send_signal instead of letting an
	AttributeError escape (it is not a ProcessLookupError/PermissionError, so the
	original try/except around os.killpg alone did not catch it)."""
	# given
	checks = _load_checks_module()
	monkeypatch.delattr(checks.os, "killpg", raising=False)
	sent: list[object] = []

	class _FakeProc:
		def poll(self):
			return None

		def send_signal(self, sig):
			sent.append(sig)

	# when
	checks._kill_process_group(_FakeProc(), signal.SIGTERM)

	# then
	assert sent == [signal.SIGTERM]


def test_given_no_sigkill_and_no_killpg_when_wait_after_interrupt_then_sends_sigterm_fallback(
	monkeypatch,
):
	"""End-to-end repro of the Windows crash: no signal.SIGKILL, no os.killpg.
	_wait_after_interrupt must still send SIGINT then the SIGTERM kill fallback
	via Popen.send_signal, and return the process's exit code — no AttributeError."""
	# given
	monkeypatch.delattr(signal, "SIGKILL", raising=False)
	checks = _load_checks_module()
	monkeypatch.delattr(checks.os, "killpg", raising=False)
	sent: list[object] = []

	class _FakeProc:
		pid = 4242
		returncode = None

		def poll(self):
			# Never finishes on its own — forces the real control flow to reach the
			# post-deadline kill fallback instead of exiting the wait loop early.
			return None

		def send_signal(self, sig):
			sent.append(sig)

		def wait(self, timeout=None):
			self.returncode = 130
			return 130

	# Fake clock that advances past the 5s deadline after a few calls, without a
	# real sleep (poll() always reports "still running", so only the deadline
	# — not poll() turning non-None — can end the wait loop).
	clock = {"t": 0.0}

	def _fake_monotonic() -> float:
		clock["t"] += 1.0
		return clock["t"]

	monkeypatch.setattr(checks.time, "monotonic", _fake_monotonic)
	monkeypatch.setattr(checks.time, "sleep", lambda _seconds: None)

	# when
	code = checks._wait_after_interrupt(_FakeProc())

	# then
	assert code == 130
	assert sent == [checks.signal.SIGINT, checks.signal.SIGTERM]
