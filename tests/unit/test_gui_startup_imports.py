"""Regression: GUI cold-start must not import the CLI adapter or heavy search stack."""

from __future__ import annotations

import subprocess
import sys

import pytest


pytestmark = pytest.mark.unit


def _run_probe(code: str) -> subprocess.CompletedProcess[str]:
	return subprocess.run(  # noqa: S603
		[sys.executable, "-c", code],
		check=False,
		capture_output=True,
		text=True,
	)


def test_given_fresh_interpreter_when_importing_cli_then_skips_heavy_outbound_stack():
	probe = (
		"import sys; "
		"from srxy.adapters.inbound.cli import cli; "  # noqa: F841 — import side effects
		"assert 'srxy.adapters.outbound.ocr.ocr_text' not in sys.modules; "
		"assert 'srxy.adapters.outbound.semantic.semantic_image' not in sys.modules; "
		"assert 'srxy.adapters.outbound.transcribe.transcribe_text' not in sys.modules; "
		"assert 'srxy.adapters.outbound.cache.cache' not in sys.modules; "
		"assert 'srxy.application.use_cases.search_files' not in sys.modules; "
		"assert 'cryptography' not in sys.modules; "
		"assert 'rapidfuzz' not in sys.modules; "
		"assert 'jellyfish' not in sys.modules"
	)
	result = _run_probe(probe)
	assert result.returncode == 0, result.stderr or result.stdout


def test_given_fresh_interpreter_when_importing_gui_controller_then_does_not_import_cli():
	probe = (
		"import sys; "
		"from srxy.adapters.inbound.gui import controller; "  # noqa: F841
		"assert 'srxy.adapters.inbound.cli.cli' not in sys.modules; "
		"assert 'srxy.adapters.outbound.ocr.ocr_text' not in sys.modules; "
		"assert 'srxy.adapters.outbound.transcribe.transcribe_text' not in sys.modules; "
		"assert 'srxy.application.use_cases.search_files' not in sys.modules; "
		"assert 'cryptography' not in sys.modules; "
		"assert 'rapidfuzz' not in sys.modules"
	)
	result = _run_probe(probe)
	assert result.returncode == 0, result.stderr or result.stdout
