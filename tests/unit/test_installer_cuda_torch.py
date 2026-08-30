"""Unit tests for Windows CUDA PyTorch ensure (installer)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from srxy.adapters.inbound.installer import cuda_torch as cuda_mod
from srxy.adapters.inbound.installer.cuda_torch import (
	TorchProbe,
	cuda_wheel_index_url,
	ensure_windows_cuda_torch,
	probe_torch,
	should_ensure_windows_cuda_torch,
)


pytestmark = pytest.mark.unit


def test_given_non_windows_when_should_ensure_then_false(monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setattr(cuda_mod, "has_nvidia_gpu", lambda: True)
	assert should_ensure_windows_cuda_torch(install_semantic=True, is_windows=False) is False


def test_given_no_semantic_when_should_ensure_then_false(monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setattr(cuda_mod, "has_nvidia_gpu", lambda: True)
	assert should_ensure_windows_cuda_torch(install_semantic=False, is_windows=True) is False


def test_given_windows_semantic_nvidia_when_should_ensure_then_true(monkeypatch: pytest.MonkeyPatch):
	monkeypatch.delenv("SRXY_SKIP_CUDA_TORCH", raising=False)
	monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
	monkeypatch.setattr(cuda_mod, "has_nvidia_gpu", lambda: True)
	assert should_ensure_windows_cuda_torch(install_semantic=True, is_windows=True) is True


def test_given_skip_env_when_should_ensure_then_false(monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setenv("SRXY_SKIP_CUDA_TORCH", "1")
	monkeypatch.setattr(cuda_mod, "has_nvidia_gpu", lambda: True)
	assert should_ensure_windows_cuda_torch(install_semantic=True, is_windows=True) is False


def test_given_empty_cuda_visible_when_should_ensure_then_false(monkeypatch: pytest.MonkeyPatch):
	monkeypatch.delenv("SRXY_SKIP_CUDA_TORCH", raising=False)
	monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
	monkeypatch.setattr(cuda_mod, "has_nvidia_gpu", lambda: True)
	assert should_ensure_windows_cuda_torch(install_semantic=True, is_windows=True) is False


def test_given_probe_output_when_parsing_then_detects_cuda_build():
	def fake_run(cmd: list[str], **kwargs: object):
		_ = cmd, kwargs
		return SimpleNamespace(returncode=0, stdout="2.13.0+cu130\n1\n", stderr="")

	probe = probe_torch(Path("python"), run_probe=fake_run)
	assert probe is not None
	assert probe.version == "2.13.0+cu130"
	assert probe.cuda_available is True
	assert probe.is_cuda_build is True


def test_given_cpu_torch_when_ensure_then_reinstalls_from_pytorch_index(tmp_path: Path):
	uv = tmp_path / "uv.exe"
	python = tmp_path / "python.exe"
	uv.write_bytes(b"uv")
	python.write_bytes(b"py")
	captured: list[list[str]] = []
	probes = iter(
		[
			TorchProbe(version="2.13.0+cpu", cuda_available=False),
			TorchProbe(version="2.13.0+cu130", cuda_available=True),
		]
	)

	def fake_run(cmd: list[str], *, env: dict[str, str] | None = None):
		_ = env
		captured.append(list(cmd))

	result = ensure_windows_cuda_torch(
		uv=uv,
		python=python,
		env={"VIRTUAL_ENV": str(tmp_path)},
		run=fake_run,
		probe=lambda *_a, **_k: next(probes),
	)

	assert result == "installed"
	assert len(captured) == 1
	cmd = captured[0]
	assert cmd[:4] == [str(uv), "pip", "install", "--reinstall-package"]
	assert "torch" in cmd and "torchvision" in cmd and "torchaudio" in cmd
	assert "--index-url" in cmd
	assert cmd[cmd.index("--index-url") + 1] == cuda_wheel_index_url("cu130")


def test_given_cuda_build_already_when_ensure_then_skips_install(tmp_path: Path):
	uv = tmp_path / "uv.exe"
	python = tmp_path / "python.exe"
	captured: list[list[str]] = []

	def fake_run(cmd: list[str], *, env: dict[str, str] | None = None):
		_ = env
		captured.append(list(cmd))

	result = ensure_windows_cuda_torch(
		uv=uv,
		python=python,
		env={},
		run=fake_run,
		probe=lambda *_a, **_k: TorchProbe(version="2.13.0+cu130", cuda_available=True),
	)

	assert result == "ok"
	assert captured == []


def test_given_primary_index_fails_when_ensure_then_tries_fallback(tmp_path: Path):
	uv = tmp_path / "uv.exe"
	python = tmp_path / "python.exe"
	captured: list[list[str]] = []
	probes = iter(
		[
			TorchProbe(version="2.13.0+cpu", cuda_available=False),
			TorchProbe(version="2.13.0+cu126", cuda_available=True),
		]
	)

	def fake_run(cmd: list[str], *, env: dict[str, str] | None = None):
		_ = env
		captured.append(list(cmd))
		if "cu130" in " ".join(cmd):
			raise RuntimeError("cu130 failed")

	result = ensure_windows_cuda_torch(
		uv=uv,
		python=python,
		env={},
		run=fake_run,
		probe=lambda *_a, **_k: next(probes),
	)

	assert result == "installed"
	assert len(captured) == 2
	assert "cu130" in captured[0][-1]
	assert "cu126" in captured[1][-1]
