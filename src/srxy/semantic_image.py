from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

from srxy.cache import CACHE_KIND_CLIP_EMBED, cache_get, cache_put, get_file_content_hash
from srxy.device import resolve_semantic_image_device, warn_if_cpu_device
from srxy.image_formats import is_semantic_image_path, open_image_for_vision


DEFAULT_MODEL_ID = "sentence-transformers/clip-ViT-B-32"
DEFAULT_SEMANTIC_IMAGE_THRESHOLD = 0.18

_semantic_image_model: object | None = None
_query_embedding_cache: dict[str, object] = {}

_TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})

_SEMANTIC_IMAGE_UNAVAILABLE_MESSAGE = (
	"Image semantic search is disabled. Set SRXY_SEMANTIC_IMAGE=1 and install the optional "
	"dependency: pip install 'srxy[semantic]'"
)


def semantic_image_env_enabled() -> bool:
	value = os.environ.get("SRXY_SEMANTIC_IMAGE", "").strip().lower()
	return value in _TRUTHY_ENV_VALUES


def sentence_transformers_installed() -> bool:
	return importlib.util.find_spec("sentence_transformers") is not None


def is_semantic_image_available() -> bool:
	return semantic_image_env_enabled() and sentence_transformers_installed()


def semantic_image_requested(semantic_image: bool | None) -> bool:
	if semantic_image is not None:
		return semantic_image
	return semantic_image_env_enabled()


def is_semantic_image_active(semantic_image: bool | None = None) -> bool:
	return semantic_image_requested(semantic_image) and is_semantic_image_available()


def semantic_image_unavailable_message() -> str:
	return _SEMANTIC_IMAGE_UNAVAILABLE_MESSAGE


def ensure_semantic_image_available():
	if not is_semantic_image_available():
		raise RuntimeError(_SEMANTIC_IMAGE_UNAVAILABLE_MESSAGE)


def _model_source() -> str:
	local_path = os.environ.get("SRXY_SEMANTIC_IMAGE_MODEL_PATH", "").strip()
	if local_path:
		return local_path
	model_id = os.environ.get("SRXY_SEMANTIC_IMAGE_MODEL", DEFAULT_MODEL_ID).strip()
	return model_id or DEFAULT_MODEL_ID


def _model_variant() -> str:
	return _model_source()


def _load_model() -> object:
	from sentence_transformers import SentenceTransformer  # type: ignore[reportMissingImports]

	from srxy.model_store import (
		ensure_semantic_image_model,
		is_model_installed,
		semantic_image_model_missing_message,
	)

	if not ensure_semantic_image_model(interactive=sys.stdin.isatty()):
		raise RuntimeError(semantic_image_model_missing_message())

	source = _model_source()
	model_path = Path(source)
	device = resolve_semantic_image_device()
	warn_if_cpu_device(device, context="CLIP image semantic search")
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
	global _semantic_image_model
	if _semantic_image_model is None:
		_semantic_image_model = _load_model()
	return _semantic_image_model


def warmup_semantic_image_model():
	"""Load the CLIP model into memory. Intended for integration tests."""
	_get_model()


def reset_semantic_image_model():
	"""Reset the cached CLIP model. Intended for tests."""
	global _semantic_image_model
	_semantic_image_model = None
	_query_embedding_cache.clear()


def _cosine_similarity(left: object, right: object) -> float:
	from sentence_transformers import util  # type: ignore[reportMissingImports]

	return float(util.cos_sim(left, right)[0][0])  # type: ignore[index]


def encode_semantic_image_query(query: str) -> object:
	cached = _query_embedding_cache.get(query)
	if cached is not None:
		return cached
	model = _get_model()
	embedding = model.encode(query)  # type: ignore[union-attr]
	import numpy as np

	array = np.asarray(embedding, dtype=np.float32)
	_query_embedding_cache[query] = array
	return array


def _encode_image(path: Path, *, file_hash: str | None = None) -> object:
	import numpy as np

	variant = _model_variant()
	content_hash = file_hash or get_file_content_hash(path)
	cached = cache_get(CACHE_KIND_CLIP_EMBED, content_hash, variant)
	if cached is not None:
		return np.frombuffer(cached, dtype=np.float32)

	model = _get_model()
	with open_image_for_vision(path) as image:
		embedding = model.encode(image.convert("RGB"))  # type: ignore[union-attr]
	array = np.asarray(embedding, dtype=np.float32)
	cache_put(CACHE_KIND_CLIP_EMBED, content_hash, variant, array.tobytes())
	return array


def score_image(
	query: str,
	path: Path,
	*,
	file_hash: str | None = None,
	query_embedding: object | None = None,
) -> float:
	if not query or not path.is_file() or not is_semantic_image_path(path):
		return 0.0

	try:
		text_embedding = query_embedding if query_embedding is not None else encode_semantic_image_query(query)
		image_embedding = _encode_image(path, file_hash=file_hash)
		similarity = _cosine_similarity(text_embedding, image_embedding)
	except Exception:
		return 0.0
	return max(0.0, min(1.0, similarity))
