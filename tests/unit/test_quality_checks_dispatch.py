"""Unit tests for scripts/quality/checks.py OS dispatch."""

from __future__ import annotations

import importlib.util
import io
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
