"""Outbound ports for content extraction and related infrastructure."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Protocol


class DocumentReaderPort(Protocol):
	def iter_text_units(self, path: Path) -> Iterator[object]: ...


class OcrEnginePort(Protocol):
	def is_available(self) -> bool: ...


class SpeechTranscriberPort(Protocol):
	def is_available(self) -> bool: ...


class ImageEmbedderPort(Protocol):
	def is_available(self) -> bool: ...


class ModelStorePort(Protocol):
	def ensure_models(self, *keys: str) -> None: ...


class ResultCachePort(Protocol):
	def get(self, key: str) -> object | None: ...

	def set(self, key: str, value: object) -> None: ...
