from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from srxy.adapters.inbound.gui.capabilities import (
	Capabilities,
	default_capabilities,
	probe_capabilities,
	unavailable_reason,
)
from srxy.adapters.inbound.gui.help_text import help_text
from srxy.application.model_preflight import (
	format_download_prompt,
	list_pending_model_downloads,
)
from srxy.i18n import tr


pytestmark = pytest.mark.unit


def test_given_known_key_when_help_text_then_includes_guidance():
	# given / when / then
	assert "filenames" in help_text("search_names").lower() or "file" in help_text("search_names").lower()
	assert "tesseract" in help_text("ocr").lower()
	assert "github.com/tesseract-ocr" in help_text("ocr")
	assert "srxy[semantic]" in help_text("semantic")
	assert "ffmpeg.org" in help_text("transcribe")


def test_given_unknown_key_when_help_text_then_fallback_message():
	assert help_text("not_a_real_key") == tr("help.not_available")


def test_given_no_gpu_when_unavailable_reason_then_mentions_gpu():
	caps = Capabilities(
		semantic_deps=True,
		has_gpu=False,
		ocr=True,
		ffmpeg=True,
		transcribe_deps=True,
		semantic_enabled=False,
		semantic_image_enabled=False,
		transcribe_enabled=False,
		ocr_enabled=True,
	)
	assert "GPU" in unavailable_reason("semantic", caps)
	assert "GPU" in unavailable_reason("transcribe", caps)


def test_given_missing_tesseract_when_unavailable_reason_then_mentions_tesseract():
	caps = Capabilities(
		semantic_deps=True,
		has_gpu=True,
		ocr=False,
		ffmpeg=True,
		transcribe_deps=True,
		semantic_enabled=True,
		semantic_image_enabled=True,
		transcribe_enabled=True,
		ocr_enabled=False,
	)
	assert "tesseract" in unavailable_reason("ocr", caps).lower()


def test_given_probe_when_called_then_returns_capabilities():
	probe_capabilities.cache_clear()
	caps = probe_capabilities()
	assert isinstance(caps.semantic_deps, bool)
	assert isinstance(caps.has_gpu, bool)
	assert caps.ocr_enabled == caps.ocr


def test_given_probe_when_called_twice_then_second_call_is_cached(monkeypatch: pytest.MonkeyPatch):
	probe_capabilities.cache_clear()
	calls = 0

	def _count_gpu():
		nonlocal calls
		calls += 1
		return False

	monkeypatch.setattr("srxy.adapters.inbound.gui.capabilities._probe_has_gpu", _count_gpu)
	first = probe_capabilities()
	second = probe_capabilities()
	assert first == second
	assert calls == 1


def test_given_default_capabilities_when_called_then_skips_gpu_probe(monkeypatch: pytest.MonkeyPatch):
	monkeypatch.setattr(
		"srxy.adapters.inbound.gui.capabilities._probe_has_gpu",
		lambda: (_ for _ in ()).throw(AssertionError("gpu probe should not run")),
	)
	caps = default_capabilities()
	assert caps.has_gpu is False
	assert caps.semantic_enabled is False


def test_given_path_when_format_download_prompt_then_includes_target(tmp_path: Path):
	model_dir = tmp_path / "model"
	prompt = format_download_prompt("Semantic text model", model_dir, size_hint="~80 MB")
	assert "Semantic text model" in prompt
	assert str(model_dir) in prompt
	assert "~80 MB" in prompt


def test_given_semantic_request_when_model_missing_then_lists_pending_download():
	args = MagicMock()
	args.semantic = True
	args.semantic_all = False
	args.semantic_image = False
	args.transcribe = False
	with (
		patch("srxy.application.model_preflight.ensure_semantic_text_model", return_value=False),
		patch("srxy.application.model_preflight.ensure_semantic_image_model", return_value=True),
		patch("srxy.application.model_preflight.ensure_transcribe_model", return_value=True),
	):
		pending = list_pending_model_downloads(args)
	assert len(pending) == 1
	assert pending[0].kind == "semantic_text"
