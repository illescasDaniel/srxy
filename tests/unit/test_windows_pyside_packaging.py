"""Contract tests for the Windows PySide offline installer wrapper (no full Windows build).

Mirrors tests/unit/test_linux_appimage_packaging.py — checks script layout / content
so CI (Linux) can catch obvious regressions without a Windows host. A full build +
smoke still needs Windows (see packaging/windows/README.md).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[2]
_WINDOWS = _REPO / "packaging" / "windows"
_RESOURCES_WINDOWS = _REPO / "src" / "srxy" / "resources" / "windows"


def test_given_windows_pyside_scripts_when_checking_layout_then_present():
	# given
	scripts = [
		_WINDOWS / "build-offline-pyside.ps1",
		_WINDOWS / "prune-pyside.ps1",
		_WINDOWS / "smoke-offline-pyside.ps1",
	]

	# when / then
	for path in scripts:
		assert path.is_file(), f"missing {path}"
	assert (_WINDOWS / "README.md").is_file()


def test_given_inno_offline_installer_when_checking_layout_then_still_present():
	"""This PR adds the PySide wrapper alongside Inno — it must not remove it."""
	# given / when / then
	assert (_WINDOWS / "srxy-offline.iss").is_file()
	assert (_WINDOWS / "build-offline.ps1").is_file()
	assert (_WINDOWS / "smoke-offline.ps1").is_file()


def test_given_installer_launcher_source_when_checking_layout_then_present():
	# given / when / then
	assert (_RESOURCES_WINDOWS / "SrxyLauncher.cs").is_file(), "existing app launcher must stay untouched"
	assert (_RESOURCES_WINDOWS / "SrxyInstallerLauncher.cs").is_file()


def test_given_installer_launcher_source_when_reading_then_launches_wizard_module():
	# given
	text = (_RESOURCES_WINDOWS / "SrxyInstallerLauncher.cs").read_text(encoding="utf-8")

	# when / then
	assert "SRXY_INSTALLER_PAYLOAD" in text
	assert "srxy.adapters.inbound.installer" in text
	assert "pythonw.exe" in text
	assert "venv" in text and "Scripts" in text


def test_given_build_script_when_reading_then_stages_wizard_only_venv_and_bundled_wheel():
	# given
	text = (_WINDOWS / "build-offline-pyside.ps1").read_text(encoding="utf-8")

	# when / then
	assert "UV_PYTHON_PREFERENCE" in text
	assert "only-managed" in text
	assert "--relocatable" in text
	assert 'uv pip install --python $VenvPy "PySide6>=6.6"' in text
	assert "--no-deps $Root" in text
	assert "share\\srxy\\srxy.whl" in text
	assert "installer_meta.toml" in text
	assert "prune-pyside.ps1" in text
	assert "SrxyInstallerLauncher.cs" in text
	assert "SRXY_INSTALLER_PAYLOAD" in text
	# Relocation guard mirrors the macOS/Linux offline builds.
	assert "wizard-reloc-ok" in text
	assert "relocatable" in text.lower()
	# Names an artifact distinct from the Inno .exe.zip so neither overwrites the other.
	assert "installer-$InstallerVersion-pyside-$Arch.zip" in text
	assert "SHA256SUMS-windows-offline-pyside" in text


def test_given_build_script_when_reading_then_reuses_prebuilt_app_launcher_for_prefix_installs():
	# given
	text = (_WINDOWS / "build-offline-pyside.ps1").read_text(encoding="utf-8")

	# when / then — same payload layout the Inno build + install.py already understand.
	assert "share\\srxy\\windows" in text
	assert "_write_windows_ico" in text
	assert "_launcher_cs_source" in text
	assert "_find_csc" in text


def test_given_prune_script_when_reading_then_targets_windows_pyside_layout():
	# given
	text = (_WINDOWS / "prune-pyside.ps1").read_text(encoding="utf-8")

	# when / then — Windows PySide6 wheel layout differs from macOS/Linux (no "Qt\" prefix).
	assert "PySide6" in text
	assert '"qml"' in text
	assert '"plugins"' in text
	assert 'Join-Path $pside "Qt\\lib"' not in text
	assert 'Join-Path $pside "Qt/lib"' not in text
	# DLL pruning is a DENYLIST (not an allowlist): an incomplete allowlist broke
	# CI when Qt 6.11 split QtQml further (Qt6QmlCore.dll became a separate,
	# required dependency of Qt6Qml.dll) — see denyDllPatterns comment. A denylist
	# of clearly-unused module families (WebEngine, Multimedia, 3D, ...) keeps
	# everything else (including any future Qt module splits) by default.
	assert "denyDllPatterns" in text
	assert "Qt6WebEngine*.dll" in text
	assert "keepDllPatterns" not in text
	deny_block = text[text.index("$denyDllPatterns = @(") : text.index(")", text.index("$denyDllPatterns = @("))]
	assert "Qt6QmlCore" not in deny_block  # must not be denied — kept by default


def test_given_smoke_script_when_reading_then_relocates_before_testing():
	# given
	text = (_WINDOWS / "smoke-offline-pyside.ps1").read_text(encoding="utf-8")

	# when / then — same relocation-bug class the macOS/Linux offline smoke tests guard.
	assert "Copy-Item" in text
	assert "SRXY_INSTALLER_PAYLOAD" in text
	assert "--install" in text
	assert "--uninstall" in text
	assert "SrxyInstaller.exe" in text


def test_given_installer_meta_when_checking_windows_pyside_smoke_then_references_current_payload_env():
	"""SRXY_INSTALLER_PAYLOAD is already understood by package_spec.py / meta.py — the
	Windows PySide payload reuses that exact contract (payload/share/srxy/...)."""
	# given
	package_spec = (_REPO / "src" / "srxy" / "adapters" / "inbound" / "installer" / "package_spec.py").read_text(
		encoding="utf-8"
	)
	meta = (_REPO / "src" / "srxy" / "adapters" / "inbound" / "installer" / "meta.py").read_text(encoding="utf-8")

	# when / then
	assert "SRXY_INSTALLER_PAYLOAD" in package_spec
	assert "SRXY_INSTALLER_PAYLOAD" in meta


def test_given_windows_ci_workflow_when_checking_then_has_pyside_job():
	# given
	workflow = (_REPO / ".github" / "workflows" / "windows-installer.yml").read_text(encoding="utf-8")

	# when / then
	assert "build-offline-pyside" in workflow
	assert "build-offline-pyside.ps1" in workflow
	assert "smoke-offline-pyside.ps1" in workflow
	# The existing Inno job must remain.
	assert "build-offline.ps1" in workflow


def test_given_windows_ci_workflow_when_checking_triggers_then_runs_on_develop():
	"""The build-offline-pyside job must actually run on PRs/pushes targeting develop
	(not just main) — this is where feature branches for this workstream land.

	No YAML lib dependency in this project's test env — extract the `on:` block by
	line range (up to the next top-level key) and check both branch lists textually.
	"""
	# given
	lines = (_REPO / ".github" / "workflows" / "windows-installer.yml").read_text(encoding="utf-8").splitlines()
	on_start = next(i for i, line in enumerate(lines) if line.strip() == "on:")
	on_end = next(i for i in range(on_start + 1, len(lines)) if lines[i] and not lines[i][0].isspace())
	on_block = "\n".join(lines[on_start:on_end])

	# when
	push_start = on_block.index("push:")
	pull_request_start = on_block.index("pull_request:")
	push_block = on_block[push_start:pull_request_start]
	pull_request_block = on_block[pull_request_start:]

	# then
	assert "branches: [main, develop]" in push_block
	assert "branches: [main, develop]" in pull_request_block


def test_given_taskipy_tasks_when_checking_then_pyside_windows_tasks_registered():
	# given
	pyproject = (_REPO / "pyproject.toml").read_text(encoding="utf-8")

	# when / then
	assert "build-windows-installer-offline-pyside" in pyproject
	assert "smoke-windows-installer-offline-pyside" in pyproject
	# The existing Inno task must remain registered too.
	assert "build-windows-installer-offline " in pyproject or "build-windows-installer-offline =" in pyproject


@pytest.mark.skipif(os.name != "nt", reason="PowerShell script syntax check needs Windows/pwsh")
def test_given_powershell_available_when_parsing_scripts_then_no_syntax_errors():
	import shutil
	import subprocess

	for name in ("build-offline-pyside.ps1", "prune-pyside.ps1", "smoke-offline-pyside.ps1"):
		path = _WINDOWS / name
		result = subprocess.run(  # noqa: S603
			[
				shutil.which("powershell") or "powershell",
				"-NoProfile",
				"-Command",
				f"$null = [System.Management.Automation.PSParser]::Tokenize((Get-Content -Raw '{path}'), [ref]$null)",
			],
			capture_output=True,
			text=True,
			check=False,
		)
		assert result.returncode == 0, result.stderr
