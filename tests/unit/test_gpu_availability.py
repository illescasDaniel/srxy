"""Unit tests for GPU availability probes."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from srxy.application.gpu_availability import (
	_has_nvidia_windows_nofork,  # pyright: ignore[reportPrivateUsage]
	has_accelerated_gpu_nofork,
)


pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Windows nofork probe
# ---------------------------------------------------------------------------


def test_given_non_windows_when_windows_nofork_probe_then_returns_false(monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setattr("sys.platform", "linux")
	assert _has_nvidia_windows_nofork() is False


def test_given_nvapi64_present_when_windows_nofork_probe_then_returns_true(
	monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
	monkeypatch.setattr("sys.platform", "win32")
	system32 = tmp_path / "Windows" / "System32"
	system32.mkdir(parents=True)
	(system32 / "nvapi64.dll").touch()
	monkeypatch.setenv("SystemRoot", str(tmp_path / "Windows"))
	assert _has_nvidia_windows_nofork() is True


def test_given_nvcuda_present_when_windows_nofork_probe_then_returns_true(
	monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
	monkeypatch.setattr("sys.platform", "win32")
	system32 = tmp_path / "Windows" / "System32"
	system32.mkdir(parents=True)
	(system32 / "nvcuda.dll").touch()
	monkeypatch.setenv("SystemRoot", str(tmp_path / "Windows"))
	assert _has_nvidia_windows_nofork() is True


def test_given_no_dlls_and_registry_key_present_when_windows_nofork_probe_then_returns_true(
	monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
	monkeypatch.setattr("sys.platform", "win32")
	system32 = tmp_path / "Windows" / "System32"
	system32.mkdir(parents=True)
	monkeypatch.setenv("SystemRoot", str(tmp_path / "Windows"))

	fake_winreg = MagicMock()
	fake_winreg.OpenKey.return_value.__enter__ = lambda s: s
	fake_winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
	fake_winreg.HKEY_LOCAL_MACHINE = MagicMock()
	with patch.dict("sys.modules", {"winreg": fake_winreg}):
		assert _has_nvidia_windows_nofork() is True

	fake_winreg.OpenKey.assert_called_once()
	call_args = fake_winreg.OpenKey.call_args
	assert "nvlddmkm" in str(call_args)


def test_given_no_dlls_and_no_registry_key_when_windows_nofork_probe_then_returns_false(
	monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
	monkeypatch.setattr("sys.platform", "win32")
	system32 = tmp_path / "Windows" / "System32"
	system32.mkdir(parents=True)
	monkeypatch.setenv("SystemRoot", str(tmp_path / "Windows"))

	fake_winreg = MagicMock()
	fake_winreg.OpenKey.side_effect = OSError("not found")
	fake_winreg.HKEY_LOCAL_MACHINE = MagicMock()
	with patch.dict("sys.modules", {"winreg": fake_winreg}):
		assert _has_nvidia_windows_nofork() is False


# ---------------------------------------------------------------------------
# has_accelerated_gpu_nofork integration
# ---------------------------------------------------------------------------


def test_given_force_gpu_env_when_nofork_probe_then_overrides(monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setenv("SRXY_FORCE_GPU", "1")
	assert has_accelerated_gpu_nofork() is True


def test_given_force_no_gpu_env_when_nofork_probe_then_overrides(monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setenv("SRXY_FORCE_NO_GPU", "1")
	assert has_accelerated_gpu_nofork() is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only path")
def test_given_windows_with_nvapi_when_nofork_probe_then_detects_gpu(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
	"""On a real Windows system, nvapi64.dll presence determines the result."""
	monkeypatch.delenv("SRXY_FORCE_GPU", raising=False)
	monkeypatch.delenv("SRXY_FORCE_NO_GPU", raising=False)
	# Create a fake nvapi64.dll in a temp System32 dir
	system32 = tmp_path / "System32"
	system32.mkdir()
	(system32 / "nvapi64.dll").touch()
	monkeypatch.setenv("SystemRoot", str(tmp_path.parent))
	# Direct probe
	assert _has_nvidia_windows_nofork() is True
