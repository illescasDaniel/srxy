"""Outbound ports for content extraction and related infrastructure."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Protocol

from srxy.domain.models import SkippedFile
from srxy.domain.progress import ActivityCallback
from srxy.domain.text_unit import TextUnit


class FileWalkerPort(Protocol):
	def iter_files(
		self,
		root: Path,
		*,
		skip_hidden_folders: bool = True,
		skip_noise_folders: bool = True,
		skip_noise_files: bool = True,
		match_skipped_names: bool = False,
		include_archives: bool = False,
		include_subdirectories: bool = True,
		cancel_check: Callable[[], bool] | None = None,
		skipped_files: list[SkippedFile] | None = None,
	) -> Iterator[Path]: ...

	def collect_files(
		self,
		root: Path,
		*,
		skip_hidden_folders: bool = True,
		skip_noise_folders: bool = True,
		skip_noise_files: bool = True,
		match_skipped_names: bool = False,
		include_archives: bool = False,
		include_subdirectories: bool = True,
		cancel_check: Callable[[], bool] | None = None,
		skipped_files: list[SkippedFile] | None = None,
	) -> list[Path]: ...

	def is_searchable(self, path: Path) -> bool: ...

	def is_archive_member(self, path: Path) -> bool: ...


class TextExtractorPort(Protocol):
	def iter_units(
		self,
		path: Path,
		max_file_size: int | None,
		*,
		search_docs_tags: bool = True,
		ocr: bool | None = None,
		transcribe: bool | None = None,
		skipped_files: list[SkippedFile] | None = None,
		on_activity: ActivityCallback | None = None,
	) -> Iterator[TextUnit]: ...

	def effective_max_file_size(
		self,
		path: Path,
		max_file_size: int | None,
		*,
		ocr: bool | None = None,
	) -> int | None: ...

	def can_search_without_reading_body(self, path: Path) -> bool: ...

	def within_size_limit(self, path: Path, max_file_size: int | None) -> bool: ...

	def size_bytes(self, path: Path) -> int: ...

	def ocr_active(self, ocr: bool | None) -> bool: ...

	def transcribe_active(self, transcribe: bool | None) -> bool: ...

	def ocr_requested(self, ocr: bool | None) -> bool: ...

	def transcribe_requested(self, transcribe: bool | None) -> bool: ...


class ImageSimilarityPort(Protocol):
	def encode_query(self, query: str) -> object | None: ...

	def score(
		self,
		query: str,
		path: Path,
		*,
		file_hash: str | None = None,
		query_embedding: object | None = None,
	) -> float: ...

	def requested(self, semantic_image: bool | None) -> bool: ...

	def is_active(self, semantic_image: bool | None) -> bool: ...

	def is_image_path(self, path: Path) -> bool: ...


class ContentCachePort(Protocol):
	def get_file_content_hash(self, path: Path) -> str | None: ...

	def reset_run_file_hashes(self): ...


class ModelStorePort(Protocol):
	def ensure_models(self, *keys: str) -> None: ...
