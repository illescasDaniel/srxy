from __future__ import annotations

import os
import sys

import pytest

from srxy.adapters.inbound.gui import qt_theme


pytestmark = pytest.mark.unit


def test_given_wayland_and_vulkan_when_prefer_stable_then_uses_vulkan_backend(
	monkeypatch: pytest.MonkeyPatch,
):
	monkeypatch.setattr(sys, "platform", "linux")
	monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
	monkeypatch.delenv("QSG_RHI_BACKEND", raising=False)
	monkeypatch.delenv("QSG_RENDER_LOOP", raising=False)
	monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
	monkeypatch.setattr(qt_theme, "vulkan_runtime_available", lambda: True)

	qt_theme.prefer_stable_wayland_rendering()

	assert os.environ.get("QSG_RHI_BACKEND") == "vulkan"
	assert "QSG_RENDER_LOOP" not in os.environ


def test_given_wayland_without_vulkan_when_prefer_stable_then_uses_basic_loop(
	monkeypatch: pytest.MonkeyPatch,
):
	monkeypatch.setattr(sys, "platform", "linux")
	monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
	monkeypatch.delenv("QSG_RHI_BACKEND", raising=False)
	monkeypatch.delenv("QSG_RENDER_LOOP", raising=False)
	monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
	monkeypatch.setattr(qt_theme, "vulkan_runtime_available", lambda: False)

	qt_theme.prefer_stable_wayland_rendering()

	assert os.environ.get("QSG_RENDER_LOOP") == "basic"
	assert "QSG_RHI_BACKEND" not in os.environ


def test_given_user_override_when_prefer_stable_then_no_changes(monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setattr(sys, "platform", "linux")
	monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
	monkeypatch.setenv("QSG_RHI_BACKEND", "opengl")
	monkeypatch.delenv("QSG_RENDER_LOOP", raising=False)

	qt_theme.prefer_stable_wayland_rendering()

	assert os.environ.get("QSG_RHI_BACKEND") == "opengl"
	assert "QSG_RENDER_LOOP" not in os.environ


def test_given_non_wayland_when_prefer_stable_then_no_changes(monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setattr(sys, "platform", "linux")
	monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
	monkeypatch.delenv("QSG_RHI_BACKEND", raising=False)
	monkeypatch.delenv("QSG_RENDER_LOOP", raising=False)

	qt_theme.prefer_stable_wayland_rendering()

	assert "QSG_RHI_BACKEND" not in os.environ
	assert "QSG_RENDER_LOOP" not in os.environ
