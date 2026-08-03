from __future__ import annotations

import argparse

import pytest

from srxy.adapters.inbound.cli.cli import build_parser, should_use_gui, should_use_tui


pytestmark = pytest.mark.unit


def _args(argv: list[str]) -> argparse.Namespace:
	return build_parser().parse_args(argv)


def test_given_cli_flag_when_should_use_gui_then_returns_false(monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setattr("srxy.application.launch.gui_importable", lambda: True)
	monkeypatch.setattr("srxy.application.launch.gui_display_available", lambda: True)
	assert should_use_gui(_args(["q", ".", "--cli"])) is False


def test_given_tui_flag_when_should_use_gui_then_returns_false(monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setattr("srxy.application.launch.gui_importable", lambda: True)
	monkeypatch.setattr("srxy.application.launch.gui_display_available", lambda: True)
	assert should_use_gui(_args(["q", ".", "--tui"])) is False


def test_given_gui_available_when_should_use_gui_then_returns_true(monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setattr("srxy.application.launch.gui_importable", lambda: True)
	monkeypatch.setattr("srxy.application.launch.gui_display_available", lambda: True)
	monkeypatch.delenv("CI", raising=False)
	assert should_use_gui(_args(["q", "."])) is True


def test_given_gui_unavailable_and_tty_when_should_use_tui_then_fallthrough(monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setattr("srxy.application.launch.gui_importable", lambda: False)
	monkeypatch.setattr("srxy.application.launch.sys.stdout", type("T", (), {"isatty": staticmethod(lambda: True)})())
	monkeypatch.setattr("srxy.application.launch.sys.stderr", type("T", (), {"isatty": staticmethod(lambda: True)})())
	monkeypatch.delenv("CI", raising=False)
	assert should_use_tui(_args(["q", "."])) is True


def test_given_tui_flag_when_should_use_tui_then_returns_true(monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setattr("srxy.application.launch.gui_importable", lambda: True)
	monkeypatch.setattr("srxy.application.launch.gui_display_available", lambda: True)
	monkeypatch.setattr("srxy.application.launch.sys.stdout", type("T", (), {"isatty": staticmethod(lambda: True)})())
	monkeypatch.setattr("srxy.application.launch.sys.stderr", type("T", (), {"isatty": staticmethod(lambda: True)})())
	monkeypatch.delenv("CI", raising=False)
	assert should_use_tui(_args(["q", ".", "--tui"])) is True
	assert should_use_gui(_args(["q", ".", "--tui"])) is False
