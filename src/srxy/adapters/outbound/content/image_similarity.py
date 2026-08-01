"""CLIP image similarity adapter."""

from __future__ import annotations

from pathlib import Path

from srxy.adapters.outbound.semantic.semantic_image import (
	encode_semantic_image_query,
	is_semantic_image_active,
	is_semantic_image_path,
	score_image,
	semantic_image_requested,
)


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
