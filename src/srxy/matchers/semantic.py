from __future__ import annotations

import os
import sys
from pathlib import Path

from srxy.device import resolve_torch_device
from srxy.matchers.base import Matcher


DEFAULT_MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

_semantic_model: object | None = None
_run_embedding_cache: dict[tuple[str, str], object] = {}

_TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})


def semantic_env_enabled() -> bool:
	value = os.environ.get("SRXY_SEMANTIC", "").strip().lower()
	return value in _TRUTHY_ENV_VALUES


def sentence_transformers_installed() -> bool:
	import importlib.util

	return importlib.util.find_spec("sentence_transformers") is not None


def is_semantic_available() -> bool:
	return semantic_env_enabled() and sentence_transformers_installed()


def _model_source() -> str:
	local_path = os.environ.get("SRXY_SEMANTIC_MODEL_PATH", "").strip()
	if local_path:
		return local_path
	return os.environ.get("SRXY_SEMANTIC_MODEL", DEFAULT_MODEL_ID).strip() or DEFAULT_MODEL_ID


def _model_variant() -> str:
	return _model_source()


def _load_model() -> object:
	from sentence_transformers import SentenceTransformer  # type: ignore[reportMissingImports]

	from srxy.model_store import ensure_semantic_text_model, is_model_installed, semantic_text_model_missing_message

	if not ensure_semantic_text_model(interactive=sys.stdin.isatty()):
		raise RuntimeError(semantic_text_model_missing_message())

	source = _model_source()
	model_path = Path(source)
	device = resolve_torch_device()
	os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
	os.environ.setdefault("TQDM_DISABLE", "1")
	os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
	os.environ.setdefault("JOBLIB_MULTIPROCESSING", "0")
	if model_path.is_dir() and is_model_installed(model_path):
		os.environ.setdefault("HF_HUB_OFFLINE", "1")
		os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
		return SentenceTransformer(str(model_path), device=device, local_files_only=True)
	return SentenceTransformer(source, device=device)


def _get_model() -> object:
	global _semantic_model
	if _semantic_model is None:
		_semantic_model = _load_model()
	return _semantic_model


def warmup_semantic_model():
	"""Load the semantic model into memory. Intended for integration tests."""
	_get_model()


def reset_semantic_model():
	"""Reset the cached semantic model. Intended for tests."""
	global _semantic_model
	_semantic_model = None
	_run_embedding_cache.clear()


def _cosine_similarity(left: object, right: object) -> float:
	from sentence_transformers import util  # type: ignore[reportMissingImports]

	return float(util.cos_sim(left, right)[0][0])  # type: ignore[index]


def _encode_text_cached(text: str) -> object:
	import numpy as np

	from srxy.cache import CACHE_KIND_SEMANTIC_EMBED, cache_get, cache_put, hash_bytes

	variant = _model_variant()
	content_hash = hash_bytes(text.encode("utf-8"))
	mem_key = (content_hash, variant)
	cached_run = _run_embedding_cache.get(mem_key)
	if cached_run is not None:
		return cached_run

	cached = cache_get(CACHE_KIND_SEMANTIC_EMBED, content_hash, variant)
	if cached is not None:
		array = np.frombuffer(cached, dtype=np.float32)
		_run_embedding_cache[mem_key] = array
		return array

	model = _get_model()
	embedding = model.encode(text)  # type: ignore[union-attr]
	array = np.asarray(embedding, dtype=np.float32)
	cache_put(CACHE_KIND_SEMANTIC_EMBED, content_hash, variant, array.tobytes())
	_run_embedding_cache[mem_key] = array
	return array


class SemanticMatcher(Matcher):
	def score(self, query: str, value: str) -> float:
		if not query or not value:
			return 0.0

		query_embedding = _encode_text_cached(query)
		value_embedding = _encode_text_cached(value)
		similarity = _cosine_similarity(query_embedding, value_embedding)
		return max(0.0, min(1.0, similarity))
