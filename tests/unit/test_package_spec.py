from __future__ import annotations

from pathlib import Path

import pytest

from srxy.adapters.inbound.installer.package_spec import resolve_srxy_install_spec, with_semantic_extra


pytestmark = pytest.mark.unit


def test_given_source_checkout_when_resolving_spec_then_uses_project_root():
	# given / when
	spec = resolve_srxy_install_spec()

	# then
	assert Path(spec).is_dir()
	assert (Path(spec) / "pyproject.toml").is_file()


def test_given_path_spec_when_adding_semantic_then_appends_extra():
	# given / when / then
	assert with_semantic_extra("/opt/srxy") == "/opt/srxy[semantic]"
	assert with_semantic_extra("srxy") == "srxy[semantic]"
	assert with_semantic_extra("srxy[semantic]") == "srxy[semantic]"


def test_given_env_override_when_resolving_spec_then_uses_override(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_INSTALL_SPEC", "srxy==9.9.9")

	# when / then
	assert resolve_srxy_install_spec() == "srxy==9.9.9"
