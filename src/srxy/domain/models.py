from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class MatchType(Enum):
	EXACT = "exact"
	CONTAINS = "contains"
	PARTIAL = "partial"
	FUZZY = "fuzzy"
	PHONETIC = "phonetic"
	SEMANTIC = "semantic"
	COMPOSITE = "composite"


DEFAULT_COMPOSITE_WEIGHTS: dict[MatchType, float] = {
	MatchType.FUZZY: 0.35,
	MatchType.SEMANTIC: 0.20,
	MatchType.PARTIAL: 0.15,
	MatchType.PHONETIC: 0.12,
	MatchType.CONTAINS: 0.10,
	MatchType.EXACT: 0.08,
}


class QNodeType(Enum):
	LEAF = "leaf"
	AND = "and"
	OR = "or"


@dataclass(frozen=True)
class FieldConfig:
	name: str
	match: MatchType = MatchType.COMPOSITE
	weight: float = 1.0
	composite_weights: dict[MatchType, float] | None = None


@dataclass
class SearchResult:
	item: Any
	score: float
	breakdown: dict[str, Any] = field(default_factory=dict)


@dataclass
class LineMatch:
	line_number: int
	text: str
	score: float
	location_kind: str = "line"
	matched_term: str | None = None


@dataclass(frozen=True)
class SkippedFile:
	path: Path
	size_bytes: int
	reason: str = "oversized"


@dataclass
class FileSearchResult:
	path: Path
	score: float
	breakdown: dict[str, float] = field(default_factory=dict)
	lines: list[LineMatch] = field(default_factory=list)
	term_surfaces: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass(frozen=True)
class Q:
	"""Composable query expression tree for field-level search logic."""

	node_type: QNodeType
	field: str | None = None
	match: MatchType = MatchType.COMPOSITE
	weight: float = 1.0
	composite_weights: dict[MatchType, float] | None = None
	children: tuple[Q, ...] = ()

	def __init__(
		self,
		field: str,
		*,
		match: MatchType = MatchType.COMPOSITE,
		weight: float = 1.0,
		composite_weights: dict[MatchType, float] | None = None,
	):
		object.__setattr__(self, "node_type", QNodeType.LEAF)
		object.__setattr__(self, "field", field)
		object.__setattr__(self, "match", match)
		object.__setattr__(self, "weight", weight)
		object.__setattr__(self, "composite_weights", composite_weights)
		object.__setattr__(self, "children", ())

	@classmethod
	def composite(
		cls,
		field: str,
		*,
		weight: float = 1.0,
		composite_weights: dict[MatchType, float] | None = None,
	) -> Q:
		return cls(
			field,
			match=MatchType.COMPOSITE,
			weight=weight,
			composite_weights=composite_weights,
		)

	@classmethod
	def exact(cls, field: str, *, weight: float = 1.0) -> Q:
		return cls(field, match=MatchType.EXACT, weight=weight)

	@classmethod
	def contains(cls, field: str, *, weight: float = 1.0) -> Q:
		return cls(field, match=MatchType.CONTAINS, weight=weight)

	@classmethod
	def partial(cls, field: str, *, weight: float = 1.0) -> Q:
		return cls(field, match=MatchType.PARTIAL, weight=weight)

	@classmethod
	def fuzzy(cls, field: str, *, weight: float = 1.0) -> Q:
		return cls(field, match=MatchType.FUZZY, weight=weight)

	@classmethod
	def phonetic(cls, field: str, *, weight: float = 1.0) -> Q:
		return cls(field, match=MatchType.PHONETIC, weight=weight)

	@classmethod
	def semantic(cls, field: str, *, weight: float = 1.0) -> Q:
		return cls(field, match=MatchType.SEMANTIC, weight=weight)

	@classmethod
	def _combine(cls, node_type: QNodeType, *children: Q) -> Q:
		if not children:
			raise ValueError("Q expressions require at least one child")
		return cls.__new__(cls)._init_combined(node_type, children)

	def _init_combined(self, node_type: QNodeType, children: tuple[Q, ...] | list[Q]) -> Q:
		object.__setattr__(self, "node_type", node_type)
		object.__setattr__(self, "field", None)
		object.__setattr__(self, "match", MatchType.COMPOSITE)
		object.__setattr__(self, "weight", 1.0)
		object.__setattr__(self, "composite_weights", None)
		object.__setattr__(self, "children", tuple(children))
		return self

	@classmethod
	def all(cls, *children: Q) -> Q:
		return cls._combine(QNodeType.AND, *children)

	@classmethod
	def any(cls, *children: Q) -> Q:
		return cls._combine(QNodeType.OR, *children)

	def __and__(self, other: object) -> Q:
		if not isinstance(other, Q):
			return NotImplemented
		return Q.all(self, other)

	def __or__(self, other: object) -> Q:
		if not isinstance(other, Q):
			return NotImplemented
		return Q.any(self, other)
