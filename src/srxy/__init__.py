from __future__ import annotations

from typing import TYPE_CHECKING, Any

from srxy.domain.dsl import Q
from srxy.domain.file_query import FileQ
from srxy.domain.models import (
	FieldConfig,
	FileSearchResult,
	LineMatch,
	MatchType,
	SearchResult,
	SkippedFile,
)
from srxy.domain.progress import ActivityUpdate


if TYPE_CHECKING:
	from srxy.application.use_cases.search_files import magic_file_search as magic_file_search
	from srxy.application.use_cases.search_objects import magic_search as magic_search, search as search


__all__ = [
	"ActivityUpdate",
	"FieldConfig",
	"FileQ",
	"FileSearchResult",
	"LineMatch",
	"MatchType",
	"Q",
	"SearchResult",
	"SkippedFile",
	"magic_file_search",
	"magic_search",
	"search",
]

# Search entry points pull optional/heavy outbound deps (cryptography, etc.).
# Keep them lazy so `import srxy.adapters.inbound.installer` works in the slim AppImage venv.
_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
	"magic_file_search": ("srxy.application.use_cases.search_files", "magic_file_search"),
	"magic_search": ("srxy.application.use_cases.search_objects", "magic_search"),
	"search": ("srxy.application.use_cases.search_objects", "search"),
}


def __getattr__(name: str) -> Any:
	target = _LAZY_EXPORTS.get(name)
	if target is None:
		raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
	module_name, attr = target
	from importlib import import_module

	value = getattr(import_module(module_name), attr)
	globals()[name] = value
	return value


def __dir__() -> list[str]:
	return sorted({*globals().keys(), *__all__})
