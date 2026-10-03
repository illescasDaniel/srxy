from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from srxy.adapters.outbound.models.device import (
	drop_torch_cache_object,
	release_cuda_memory,
	resolve_semantic_image_device,
	resolve_torch_device,
	resolve_transcribe_device,
	transcribe_backend_for_device,
	transcribe_compute_type,
)
from srxy.application.matching import semantic as semantic_module


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


def test_given_torch_missing_when_resolving_torch_device_then_returns_cpu(monkeypatch: pytest.MonkeyPatch):
	# given — core CI has no [semantic] / torch
	monkeypatch.delenv("SRXY_SEMANTIC_DEVICE", raising=False)
	monkeypatch.setattr(
		"srxy.adapters.outbound.models.device._torch_available",
		lambda: False,
	)

	# when / then
	assert resolve_torch_device() == "cpu"
	assert resolve_transcribe_device() == "cpu"


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
	constructor = MagicMock(return_value=fake_model)
	fake_sentence_transformers = MagicMock()
	fake_sentence_transformers.SentenceTransformer = constructor
	with (
		patch("srxy.adapters.outbound.models.model_store.ensure_semantic_text_model", return_value=True),
		patch("srxy.application.matching.semantic.resolve_torch_device", return_value="mps"),
		patch.dict("sys.modules", {"sentence_transformers": fake_sentence_transformers}),
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


def test_given_module_with_to_when_dropping_torch_cache_object_then_moves_to_cpu():
	# given
	module = MagicMock()
	module.model = None

	# when
	drop_torch_cache_object(module)

	# then
	module.to.assert_called_once_with("cpu")


def test_given_pipeline_wrapper_when_dropping_torch_cache_object_then_moves_inner_model():
	# given
	inner = MagicMock()
	pipeline = MagicMock()
	pipeline.model = inner
	# Avoid treating the MagicMock itself as endlessly nested via .model defaults
	type(inner).model = property(lambda self: None)

	# when
	drop_torch_cache_object(pipeline)

	# then
	inner.to.assert_called_once_with("cpu")


def test_given_no_torch_when_releasing_cuda_memory_then_is_noop(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setattr(
		"srxy.adapters.outbound.models.device._torch_available",
		lambda: False,
	)

	# when / then — must not raise
	release_cuda_memory()


def test_given_cuda_available_when_releasing_cuda_memory_then_empties_cache(monkeypatch: pytest.MonkeyPatch):
	# given
	fake_torch = MagicMock()
	fake_torch.cuda.is_available.return_value = True
	fake_torch.cuda.ipc_collect = MagicMock()
	monkeypatch.setattr(
		"srxy.adapters.outbound.models.device._torch_available",
		lambda: True,
	)

	with patch.dict("sys.modules", {"torch": fake_torch}):
		# when
		release_cuda_memory()

	# then
	fake_torch.cuda.synchronize.assert_called_once()
	fake_torch.cuda.empty_cache.assert_called_once()
	fake_torch.cuda.ipc_collect.assert_called_once()
