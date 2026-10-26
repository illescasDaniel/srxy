from __future__ import annotations

import argparse
from unittest.mock import MagicMock

import pytest

from srxy.adapters.inbound.cli import cli


pytestmark = pytest.mark.unit


@pytest.mark.parametrize("argv,expected", [([], None), (["q"], None), (["q", "."], "."), (["q", ""], "")])
def test_given_optional_path_when_parsing_then_omission_stays_distinct(argv: list[str], expected: str | None):
	# given / when
	args = cli.build_parser().parse_args(argv)

	# then
	assert args.path == expected
	assert args.app_launch is False


def test_given_app_marker_when_parsing_then_intent_is_hidden_from_help():
	# given
	parser = cli.build_parser()

	# when
	args = parser.parse_args(["--app-launch", "q", "."])

	# then
	assert args.app_launch is True
	assert args.path == "."
	assert "--app-launch" not in parser.format_help()


@pytest.mark.parametrize("query,auto_start", [(None, False), ("", False), ("  ", False), ("needle", True)])
@pytest.mark.parametrize("app_launch", [False, True])
def test_given_gui_launch_when_dispatching_then_keeps_omission_and_query_autostart(
	monkeypatch: pytest.MonkeyPatch, query: str | None, auto_start: bool, app_launch: bool
):
	# given
	dispatch = MagicMock(return_value=17)
	monkeypatch.setattr(cli, "should_use_gui", lambda args: True)
	monkeypatch.setattr("srxy.adapters.inbound.gui.run_gui", dispatch)
	argv = ["--app-launch"] if app_launch else []
	if query is not None:
		argv.append(query)

	# when
	result = cli.main(argv)

	# then
	assert result == 17
	args = dispatch.call_args.args[0]
	assert args.path is None
	assert args.app_launch is app_launch
	assert dispatch.call_args.kwargs == {"auto_start": auto_start}


@pytest.mark.parametrize("route", ["cli", "tui"])
def test_given_non_gui_omission_when_dispatching_then_keeps_dot_default(monkeypatch: pytest.MonkeyPatch, route: str):
	# given
	dispatch = MagicMock(return_value=19)
	monkeypatch.setattr(cli, "should_use_gui", lambda args: False)
	monkeypatch.setattr(cli, "should_use_tui", lambda args: route == "tui")
	monkeypatch.setattr(cli, "run_plain", dispatch)
	monkeypatch.setattr("srxy.adapters.inbound.tui.run_tui", dispatch)
	monkeypatch.setattr("srxy.application.launch.gui_display_available", lambda: False)

	# when
	result = cli.main(["needle", "--" + route])

	# then
	assert result == 19
	args: argparse.Namespace = dispatch.call_args.args[0]
	assert args.path == "."
