from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from srxy.device import (
	resolve_semantic_image_device,
	resolve_torch_device,
	resolve_transcribe_device,
	transcribe_backend_for_device,
	transcribe_compute_type,
)
from srxy.matchers import semantic as semantic_module


pytestmark = pytest.mark.unit


def test_given_cuda_available_when_resolving_torch_device_then_prefers_cuda(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.delenv("SRXY_SEMANTIC_DEVICE", raising=False)
	fake_torch = MagicMock()
	fake_torch.cuda.is_available.return_value = True
	fake_torch.backends.mps.is_available.return_value = False

	with patch.dict("sys.modules", {"torch": fake_torch}):
		# when / then
		assert resolve_torch_device() == "cuda"


def test_given_mps_only_when_resolving_torch_device_then_prefers_mps(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.delenv("SRXY_SEMANTIC_DEVICE", raising=False)
	fake_torch = MagicMock()
	fake_torch.cuda.is_available.return_value = False
	fake_torch.backends.mps.is_available.return_value = True

	with patch.dict("sys.modules", {"torch": fake_torch}):
		# when / then
		assert resolve_torch_device() == "mps"


def test_given_forced_cpu_when_resolving_torch_device_then_returns_cpu(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_SEMANTIC_DEVICE", "cpu")

	# when / then
	assert resolve_torch_device() == "cpu"


def test_given_semantic_image_device_override_when_resolving_then_uses_override(monkeypatch: pytest.MonkeyPatch):
	# given

	monkeypatch.setenv("SRXY_SEMANTIC_IMAGE_DEVICE", "cpu")

	# when / then
	assert resolve_semantic_image_device() == "cpu"


def test_given_semantic_model_load_when_device_resolved_then_passes_device(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_SEMANTIC_DEVICE", "mps")
	semantic_module.reset_semantic_model()
	fake_model = MagicMock()
	with (
		patch("srxy.model_store.ensure_semantic_text_model", return_value=True),
		patch("srxy.matchers.semantic.resolve_torch_device", return_value="mps"),
		patch("sentence_transformers.SentenceTransformer", return_value=fake_model) as constructor,
	):
		# when — call loader directly; unit conftest mocks _get_model for other tests
		semantic_module._load_model()  # pyright: ignore[reportPrivateUsage]

	# then
	constructor.assert_called_once()
	assert constructor.call_args.kwargs["device"] == "mps"
	semantic_module.reset_semantic_model()


def test_given_transcribe_device_override_when_resolving_then_uses_override(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_TRANSCRIBE_DEVICE", "cpu")

	# when / then
	assert resolve_transcribe_device() == "cpu"


def test_given_mps_device_when_selecting_backend_then_uses_transformers():
	# when / then
	assert transcribe_backend_for_device("mps") == "transformers"


def test_given_cuda_device_when_selecting_compute_type_then_uses_float16():
	# when / then
	assert transcribe_compute_type("cuda") == "float16"
