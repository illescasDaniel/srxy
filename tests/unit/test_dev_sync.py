"""Unit tests for scripts/dev/sync.py platform extras and uv argv."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest


pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
SYNC_SCRIPT = REPO_ROOT / "scripts" / "dev" / "sync.py"


def _load_sync_module():
	spec = importlib.util.spec_from_file_location("srxy_dev_sync", SYNC_SCRIPT)
	assert spec is not None and spec.loader is not None
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def test_given_linux_nvidia_when_resolving_extras_then_uses_semantic():
	# given
	sync = _load_sync_module()

	# when
	extras = sync.resolve_extras(system="linux", nvidia=True, environ={})

	# then
	assert extras == ["semantic"]


def test_given_linux_without_nvidia_when_resolving_extras_then_omits_semantic():
	# given
	sync = _load_sync_module()

	# when
	extras = sync.resolve_extras(system="linux", nvidia=False, environ={})

	# then
	assert extras == []


def test_given_linux_with_cuda_skipped_when_resolving_extras_then_omits_semantic():
	# given
	sync = _load_sync_module()

	# when
	extras = sync.resolve_extras(system="linux", nvidia=True, environ={"SRXY_SKIP_CUDA_TORCH": "1"})

	# then
	assert extras == []


def test_given_macos_apple_silicon_when_resolving_extras_then_uses_semantic():
	# given
	sync = _load_sync_module()

	# when
	extras = sync.resolve_extras(system="darwin", machine="arm64", nvidia=False, environ={})

	# then
	assert extras == ["semantic"]


def test_given_macos_intel_when_resolving_extras_then_omits_semantic():
	# given
	sync = _load_sync_module()

	# when
	extras = sync.resolve_extras(system="darwin", machine="x86_64", nvidia=False, environ={})

	# then
	assert extras == []


def test_given_windows_nvidia_when_resolving_extras_then_uses_semantic():
	# given
	sync = _load_sync_module()

	# when
	extras = sync.resolve_extras(system="win32", nvidia=True, environ={})

	# then
	assert extras == ["semantic"]


def test_given_windows_without_nvidia_when_resolving_extras_then_omits_semantic():
	# given
	sync = _load_sync_module()

	# when
	extras = sync.resolve_extras(system="win32", nvidia=False, environ={})

	# then
	assert extras == []


def test_given_windows_nvidia_with_cuda_skipped_when_resolving_extras_then_omits_semantic():
	# given
	sync = _load_sync_module()

	# when
	extras = sync.resolve_extras(
		system="win32",
		nvidia=True,
		environ={"SRXY_SKIP_CUDA_TORCH": "1"},
	)

	# then
	assert extras == []


def test_given_empty_cuda_visible_devices_when_resolving_linux_extras_then_omits_semantic():
	# given
	sync = _load_sync_module()

	# when
	extras = sync.resolve_extras(
		system="linux",
		nvidia=True,
		environ={"CUDA_VISIBLE_DEVICES": ""},
	)

	# then
	assert extras == []


def test_given_no_extras_when_building_uv_command_then_only_uv_sync():
	# given
	sync = _load_sync_module()

	# when
	cmd = sync.build_uv_sync_command([], [])

	# then
	assert cmd == ["uv", "sync"]


def test_given_semantic_extra_when_building_uv_command_then_adds_extra_flag():
	# given
	sync = _load_sync_module()

	# when
	cmd = sync.build_uv_sync_command(["semantic"])

	# then
	assert cmd == ["uv", "sync", "--extra", "semantic"]


def test_given_passthrough_flags_when_building_uv_command_then_appends_them():
	# given
	sync = _load_sync_module()

	# when
	cmd = sync.build_uv_sync_command(["semantic"], ["--group", "uploader", "--offline"])

	# then
	assert cmd == ["uv", "sync", "--extra", "semantic", "--group", "uploader", "--offline"]


def test_given_pruning_flag_when_parsing_args_then_passthrough_is_forwarded():
	# given
	sync = _load_sync_module()

	# when
	args = sync.parse_args(["--no-default-groups", "--offline"])

	# then
	assert args.passthrough == ["--no-default-groups", "--offline"]
	assert args.force is False


def test_given_extra_flags_when_parsing_args_then_passthrough_is_forwarded():
	# given
	sync = _load_sync_module()

	# when
	args = sync.parse_args(["--offline", "--reinstall-package", "srxy"])

	# then
	assert args.passthrough == ["--offline", "--reinstall-package", "srxy"]


def test_given_project_venv_prefix_when_running_inside_then_detects():
	# given
	sync = _load_sync_module()
	venv = sync.project_venv_path()

	# when / then
	with patch.object(sync, "project_venv_path", return_value=venv):
		with patch.object(sync.sys, "prefix", str(venv)):
			assert sync.running_inside_project_venv() is True


def test_given_pruning_sync_from_project_venv_when_main_then_refuses():
	# given
	sync = _load_sync_module()

	# when
	with patch.object(sync, "running_inside_project_venv", return_value=True):
		code = sync.main(["--no-default-groups", "--dry-run"])

	# then
	assert code == 1


def test_given_pruning_sync_from_project_venv_with_force_when_main_then_runs():
	# given
	sync = _load_sync_module()

	# when
	with patch.object(sync, "running_inside_project_venv", return_value=True):
		code = sync.main(["--no-default-groups", "--force", "--dry-run"])

	# then
	assert code == 0
