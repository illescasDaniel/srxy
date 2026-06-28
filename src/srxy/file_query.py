from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum

from srxy.models import QNodeType
from srxy.utils import normalize_text


class FileQueryParseError(ValueError):
	"""Raised when a boolean file-search query string cannot be parsed."""


@dataclass(frozen=True)
class FileQ:
	"""Boolean search expression over fuzzy terms (always composite matching)."""

	node_type: QNodeType
	value: str | None = None
	children: tuple[FileQ, ...] = ()

	@classmethod
	def leaf(cls, text: str) -> FileQ:
		return cls(QNodeType.LEAF, normalize_text(text), ())

	term = leaf

	@classmethod
	def _combine(cls, node_type: QNodeType, *children: FileQ) -> FileQ:
		if not children:
			raise ValueError("FileQ expressions require at least one child")
		return cls(node_type, None, tuple(children))

	@classmethod
	def all(cls, *children: FileQ) -> FileQ:
		return cls._combine(QNodeType.AND, *children)

	@classmethod
	def any(cls, *children: FileQ) -> FileQ:
		return cls._combine(QNodeType.OR, *children)

	def __and__(self, other: object) -> FileQ:
		if not isinstance(other, FileQ):
			return NotImplemented
		return FileQ.all(self, other)

	def __or__(self, other: object) -> FileQ:
		if not isinstance(other, FileQ):
			return NotImplemented
		return FileQ.any(self, other)


def query_is_compound(expr: FileQ) -> bool:
	return expr.node_type != QNodeType.LEAF


def coerce_file_query(query: str | FileQ) -> FileQ:
	if isinstance(query, FileQ):
		return query
	return parse_file_query(query)


def iter_terms(expr: FileQ) -> Iterable[str]:
	if expr.node_type == QNodeType.LEAF:
		if expr.value:
			yield expr.value
		return
	for child in expr.children:
		yield from iter_terms(child)


def format_file_query(expr: FileQ) -> str:
	if expr.node_type == QNodeType.LEAF:
		term = expr.value or ""
		if not term:
			return '""'
		if _needs_quoting(term):
			return f'"{_escape_term(term)}"'
		return term

	child_texts = [format_file_query(child) for child in expr.children]
	operator = " & " if expr.node_type == QNodeType.AND else " | "
	combined = operator.join(child_texts)
	if len(expr.children) > 1:
		return f"({combined})"
	return combined


def build_file_query_from_rows(rows: list[tuple[str, str | None]]) -> FileQ:
	if not rows:
		return FileQ.leaf("")
	expr = FileQ.leaf(rows[0][0])
	for term, join in rows[1:]:
		leaf = FileQ.leaf(term)
		if join == "and":
			expr = expr & leaf
		elif join == "or":
			expr = expr | leaf
		else:
			raise ValueError(f"unsupported join operator: {join!r}")
	return expr


def score_file_query(expr: FileQ, term_scores: dict[str, float]) -> float:
	if expr.node_type == QNodeType.LEAF:
		if expr.value is None:
			return 0.0
		return term_scores.get(expr.value, 0.0)

	child_scores = [score_file_query(child, term_scores) for child in expr.children]
	if not child_scores:
		return 0.0
	if expr.node_type == QNodeType.AND:
		return min(child_scores)
	return max(child_scores)


def score_file_query_on_text(
	expr: FileQ,
	score_term: Callable[[str, str], float],
	text: str,
) -> float:
	if expr.node_type == QNodeType.LEAF:
		if expr.value is None:
			return 0.0
		return score_term(expr.value, text)

	child_scores = [score_file_query_on_text(child, score_term, text) for child in expr.children]
	if not child_scores:
		return 0.0
	if expr.node_type == QNodeType.AND:
		return min(child_scores)
	return max(child_scores)


def file_q_to_dict(expr: FileQ) -> dict[str, object]:
	if expr.node_type == QNodeType.LEAF:
		return {"node_type": expr.node_type.value, "term": expr.value or ""}
	return {
		"node_type": expr.node_type.value,
		"children": [file_q_to_dict(child) for child in expr.children],
	}


def file_q_from_dict(data: dict[str, object]) -> FileQ:
	node_type = QNodeType(str(data["node_type"]))
	if node_type == QNodeType.LEAF:
		return FileQ.leaf(str(data.get("term", "")))
	children_data = data.get("children", ())
	if not isinstance(children_data, list):
		children_data = []
	children = tuple(file_q_from_dict(child) for child in children_data if isinstance(child, dict))
	if node_type == QNodeType.AND:
		return FileQ.all(*children)
	return FileQ.any(*children)


def parse_file_query(raw: str) -> FileQ:
	text = raw.strip()
	if not text:
		return FileQ.leaf("")
	if not _has_boolean_syntax(text):
		return FileQ.leaf(text)
	tokens = _tokenize(text)
	if not tokens:
		return FileQ.leaf("")
	parser = _Parser(tokens)
	expr = parser.parse_expression()
	if parser.peek() is not None:
		raise FileQueryParseError(f"unexpected token {parser.peek()!r}")
	return expr


def query_highlight_terms(raw: str) -> list[str]:
	text = raw.strip()
	if not text:
		return []
	if not _has_boolean_syntax(text):
		return [text]
	try:
		terms = list(iter_terms(parse_file_query(text)))
	except FileQueryParseError:
		return [text]
	return terms if terms else [text]


class _TokenKind(Enum):
	TERM = "term"
	AND = "and"
	OR = "or"
	LPAREN = "lparen"
	RPAREN = "rparen"


@dataclass(frozen=True)
class _Token:
	kind: _TokenKind
	value: str = ""


class _Parser:
	def __init__(self, tokens: list[_Token]):
		self._tokens = tokens
		self._index = 0

	def peek(self) -> _Token | None:
		if self._index >= len(self._tokens):
			return None
		return self._tokens[self._index]

	def consume(self) -> _Token:
		token = self.peek()
		if token is None:
			raise FileQueryParseError("unexpected end of query")
		self._index += 1
		return token

	def parse_expression(self) -> FileQ:
		expr = self.parse_and_expression()
		while True:
			token = self.peek()
			if token is None or token.kind != _TokenKind.OR:
				break
			self.consume()
			right = self.parse_and_expression()
			expr = expr | right
		return expr

	def parse_and_expression(self) -> FileQ:
		expr = self.parse_primary()
		while True:
			token = self.peek()
			if token is None or token.kind != _TokenKind.AND:
				break
			self.consume()
			right = self.parse_primary()
			expr = expr & right
		return expr

	def parse_primary(self) -> FileQ:
		token = self.peek()
		if token is None:
			raise FileQueryParseError("unexpected end of query")
		if token.kind == _TokenKind.LPAREN:
			self.consume()
			expr = self.parse_expression()
			close = self.peek()
			if close is None or close.kind != _TokenKind.RPAREN:
				raise FileQueryParseError("missing closing parenthesis")
			self.consume()
			return expr
		if token.kind == _TokenKind.TERM:
			self.consume()
			return FileQ.leaf(token.value)
		raise FileQueryParseError(f"unexpected token {token.kind.value}")


def _has_boolean_syntax(text: str) -> bool:
	in_quote: str | None = None
	for index, char in enumerate(text):
		if in_quote is not None:
			if char == in_quote and (index == 0 or text[index - 1] != "\\"):
				in_quote = None
			continue
		if char in {'"', "'"}:
			in_quote = char
			continue
		if char in "&|()":
			return True
	return False


def _tokenize(text: str) -> list[_Token]:
	tokens: list[_Token] = []
	index = 0
	length = len(text)

	while index < length:
		char = text[index]
		if char.isspace():
			index += 1
			continue
		if char == "&":
			tokens.append(_Token(_TokenKind.AND))
			index += 1
			continue
		if char == "|":
			tokens.append(_Token(_TokenKind.OR))
			index += 1
			continue
		if char == "(":
			tokens.append(_Token(_TokenKind.LPAREN))
			index += 1
			continue
		if char == ")":
			tokens.append(_Token(_TokenKind.RPAREN))
			index += 1
			continue
		if char in {'"', "'"}:
			term, index = _read_quoted_term(text, index)
			tokens.append(_Token(_TokenKind.TERM, term))
			continue
		term, index = _read_bare_term(text, index)
		if term:
			tokens.append(_Token(_TokenKind.TERM, term))

	return tokens


def _read_quoted_term(text: str, start: int) -> tuple[str, int]:
	quote = text[start]
	index = start + 1
	chars: list[str] = []
	while index < len(text):
		char = text[index]
		if char == "\\" and index + 1 < len(text):
			chars.append(text[index + 1])
			index += 2
			continue
		if char == quote:
			return "".join(chars), index + 1
		chars.append(char)
		index += 1
	raise FileQueryParseError("unterminated quoted term")


def _read_bare_term(text: str, start: int) -> tuple[str, int]:
	index = start
	chars: list[str] = []
	while index < len(text):
		char = text[index]
		if char.isspace() or char in "&|()":
			break
		chars.append(char)
		index += 1
	term = "".join(chars)
	if not term:
		raise FileQueryParseError(f"unexpected character {text[start]!r}")
	return term, index


def _needs_quoting(term: str) -> bool:
	if not term:
		return True
	if any(char.isspace() for char in term):
		return True
	return any(char in '&|()"\\' for char in term)


def _escape_term(term: str) -> str:
	return term.replace("\\", "\\\\").replace('"', '\\"')
