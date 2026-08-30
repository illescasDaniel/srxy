"""Unit tests for scripts/dev/sync.py platform extras and uv argv."""

from __future__ import annotations

import importlib.util
from pathlib import Path

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


def test_given_runtime_mode_when_building_uv_command_then_omits_default_groups():
	# given
	sync = _load_sync_module()

	# when
	cmd = sync.build_uv_sync_command(sync.MODE_RUNTIME, ["semantic"])

	# then
	assert cmd == ["uv", "sync", "--no-default-groups", "--extra", "semantic"]


def test_given_dev_mode_without_extras_when_building_uv_command_then_only_uv_sync():
	# given
	sync = _load_sync_module()

	# when
	cmd = sync.build_uv_sync_command(sync.MODE_DEV, [])

	# then
	assert cmd == ["uv", "sync"]


def test_given_dev_mode_when_building_uv_command_then_keeps_default_groups():
	# given
	sync = _load_sync_module()

	# when
	cmd = sync.build_uv_sync_command(sync.MODE_DEV, ["semantic"])

	# then
	assert cmd == ["uv", "sync", "--extra", "semantic"]


def test_given_uploader_mode_when_building_uv_command_then_adds_uploader_group():
	# given
	sync = _load_sync_module()

	# when
	cmd = sync.build_uv_sync_command(sync.MODE_UPLOADER, ["semantic"], ["--offline"])

	# then
	assert cmd == ["uv", "sync", "--extra", "semantic", "--group", "uploader", "--offline"]


def test_given_dev_flag_when_parsing_args_then_mode_is_dev_and_passthrough_is_forwarded():
	# given
	sync = _load_sync_module()

	# when
	args = sync.parse_args(["--dev", "--offline", "--reinstall-package", "srxy"])

	# then
	assert args.mode == sync.MODE_DEV
	assert args.passthrough == ["--offline", "--reinstall-package", "srxy"]
	assert args.dry_run is False


def test_given_no_mode_flag_when_parsing_args_then_mode_is_runtime():
	# given
	sync = _load_sync_module()

	# when
	args = sync.parse_args([])

	# then
	assert args.mode == sync.MODE_RUNTIME


def test_given_uploader_flag_when_parsing_args_then_mode_is_uploader():
	# given
	sync = _load_sync_module()

	# when
	args = sync.parse_args(["--uploader"])

	# then
	assert args.mode == sync.MODE_UPLOADER
