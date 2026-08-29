"""CLIP image similarity adapter."""

from __future__ import annotations

from pathlib import Path


def encode_semantic_image_query(query: str) -> object | None:
	from srxy.adapters.outbound.semantic.semantic_image import (
		encode_semantic_image_query as _encode,
	)

	return _encode(query)


def score_image(
	query: str,
	path: Path,
	*,
	file_hash: str | None = None,
	query_embedding: object | None = None,
) -> float:
	from srxy.adapters.outbound.semantic.semantic_image import score_image as _score

	return _score(query, path, file_hash=file_hash, query_embedding=query_embedding)


def semantic_image_requested(semantic_image: bool | None) -> bool:
	from srxy.adapters.outbound.semantic.semantic_image import semantic_image_requested as _req

	return _req(semantic_image)


def is_semantic_image_active(semantic_image: bool | None = None) -> bool:
	from srxy.adapters.outbound.semantic.semantic_image import is_semantic_image_active as _active

	return _active(semantic_image)


def is_semantic_image_path(path: Path) -> bool:
	from srxy.adapters.outbound.semantic.semantic_image import is_semantic_image_path as _is_path

	return _is_path(path)


class ClipImageSimilarity:
	"""ImageSimilarityPort over the CLIP semantic-image adapter."""

	def encode_query(self, query: str) -> object | None:
		return encode_semantic_image_query(query)

	def score(
		self,
		query: str,
		path: Path,
		*,
		file_hash: str | None = None,
		query_embedding: object | None = None,
	) -> float:
		return score_image(
			query,
			path,
			file_hash=file_hash,
			query_embedding=query_embedding,
		)

	def requested(self, semantic_image: bool | None) -> bool:
		return semantic_image_requested(semantic_image)

	def is_active(self, semantic_image: bool | None) -> bool:
		return is_semantic_image_active(semantic_image)

	def is_image_path(self, path: Path) -> bool:
		return is_semantic_image_path(path)
