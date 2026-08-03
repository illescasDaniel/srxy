from __future__ import annotations

import pytest

from srxy.adapters.inbound.installer.__main__ import main


pytestmark = pytest.mark.unit


def test_given_help_flag_when_running_installer_main_then_exits_zero_without_gui(
	capsys: pytest.CaptureFixture[str],
):
	# given / when
	with pytest.raises(SystemExit) as exc:
		main(["--help"])

	# then
	assert exc.value.code == 0
	assert "Install or uninstall srxy" in capsys.readouterr().out


def test_given_version_flag_when_running_installer_main_then_prints_version(
	capsys: pytest.CaptureFixture[str],
):
	# given / when
	code = main(["--version"])

	# then
	assert code == 0
	assert capsys.readouterr().out.strip()
