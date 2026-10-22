"""Pure ignore-rule matching (gitignore-like subset); no I/O."""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field

from srxy.domain.exceptions import IgnorePatternError, IgnoreReason


MAX_USER_LINES = 1000
MAX_LINE_CHARS = 1024
MAX_GITIGNORE_BYTES = 1 << 20
MAX_GITIGNORE_LINES = 10_000


class _Marker:
	"""Wildcard token: `?` (one char) or `*` (any run of chars, never crossing a path separator)."""

	__slots__ = ("star",)

	def __init__(self, *, star: bool):
		self.star = star


_ANY_ONE = _Marker(star=False)
_ANY_RUN = _Marker(star=True)


@dataclass(frozen=True, slots=True)
class _CharClass:
	negated: bool
	singles: frozenset[str]
	ranges: tuple[tuple[str, str], ...]

	def accepts(self, char: str) -> bool:
		found = char in self.singles or any(low <= char <= high for low, high in self.ranges)
		return found != self.negated


_Token = str | _CharClass | _Marker


@dataclass(frozen=True, slots=True)
class _Segment:
	"""A compiled path segment: per-character tokens, or the '**' sentinel."""

	tokens: tuple[_Token, ...] = ()
	globstar: bool = False
	literal: str | None = None  # whole segment is a plain string
	suffix: str | None = None  # segment is `*` followed by a plain string
	prefix: str = ""  # literal text every match starts with
	tail: str = ""  # literal text every match ends with
	runs: tuple[str, ...] = ()  # literal runs that must occur, in order, between prefix and tail
	min_len: int = 0  # fewest characters any match has
	star_only: bool = False  # only literals and `*`: prefix / runs / tail decide the match fully

	def matches(self, name: str) -> bool:
		if self.literal is not None:
			return name == self.literal
		if self.suffix is not None:
			return name.endswith(self.suffix)
		return self.matches_generic(name)

	def matches_generic(self, name: str) -> bool:
		"""Generic segment: C-level necessary conditions first, the Python matcher only for `?` / `[...]` survivors."""
		tail = self.tail
		if len(name) < self.min_len or not name.startswith(self.prefix) or (tail and not name.endswith(tail)):
			return False
		runs = self.runs
		if runs:
			pos = len(self.prefix)
			end = len(name) - len(tail)
			for run in runs:
				found = name.find(run, pos, end)
				if found < 0:
					return False
				pos = found + len(run)
		return True if self.star_only else _wildcard_match(self.tokens, name)


def _token_matches(token: _Token, char: str) -> bool:
	if isinstance(token, str):
		return token == char
	if isinstance(token, _CharClass):
		return token.accepts(char)
	return True  # `?`


def _wildcard_match(tokens: tuple[_Token, ...], name: str) -> bool:
	"""Two-pointer wildcard match with single-star backtracking: O(len(tokens) * len(name)), no recursion."""
	token_count = len(tokens)
	token_index = 0
	name_index = 0
	star_index = -1
	star_name_index = 0
	while name_index < len(name):
		if token_index < token_count and tokens[token_index] is _ANY_RUN:
			star_index = token_index
			star_name_index = name_index
			token_index += 1
		elif token_index < token_count and _token_matches(tokens[token_index], name[name_index]):
			token_index += 1
			name_index += 1
		elif star_index != -1:
			star_name_index += 1
			name_index = star_name_index
			token_index = star_index + 1
		else:
			return False
	while token_index < token_count and tokens[token_index] is _ANY_RUN:
		token_index += 1
	return token_index == token_count


@dataclass(frozen=True, slots=True)
class IgnoreSpec:
	"""JSON-safe ignore config for one search, built from args."""

	patterns: tuple[str, ...] = ()
	respect_gitignore: bool = False

	@property
	def active(self) -> bool:
		return bool(self.patterns) or self.respect_gitignore


@dataclass(frozen=True, slots=True)
class IgnorePattern:
	raw: str
	line_number: int
	negated: bool
	dir_only: bool
	anchored: bool  # has a '/' that is not the trailing one
	segments: tuple[_Segment, ...]  # compiled, NFC + casefold; '**' is a sentinel

	def matches(self, rel_parts: tuple[str, ...], is_dir: bool) -> bool:
		return self.matches_normalized(tuple(normalize_part(part) for part in rel_parts), is_dir)

	def matches_normalized(self, parts: tuple[str, ...], is_dir: bool) -> bool:
		"""Like `matches` for parts already passed through `normalize_part`."""
		if self.dir_only and not is_dir:
			return False
		if not parts:
			return False
		if not self.anchored:
			return self.segments[0].matches(parts[-1])
		return _match_anchored(self.segments, parts)


def _match_anchored(segments: tuple[_Segment, ...], parts: tuple[str, ...]) -> bool:
	"""Whole-path match; `**` via DP memoised on (segment index, part index)."""
	segment_count = len(segments)
	part_count = len(parts)
	memo: dict[tuple[int, int], bool] = {}

	def walk(seg_index: int, part_index: int) -> bool:
		if seg_index == segment_count:
			return part_index == part_count
		key = (seg_index, part_index)
		cached = memo.get(key)
		if cached is not None:
			return cached
		segment = segments[seg_index]
		if segment.globstar:
			if seg_index == segment_count - 1:
				result = part_index < part_count  # trailing `**`: contents only, at least one part
			else:
				result = any(walk(seg_index + 1, start) for start in range(part_index, part_count + 1))
		else:
			result = (
				part_index < part_count and segment.matches(parts[part_index]) and walk(seg_index + 1, part_index + 1)
			)
		memo[key] = result
		return result

	return walk(0, 0)


# (pattern index, all required literal runs, three longest runs padded with '', segment)
_Generic = tuple[int, tuple[str, ...], str, str, str, _Segment]
_SuffixItem = tuple[int, str, "_AnchoredRule | None"]


def _group_by_last_char(items: list[_SuffixItem]) -> dict[str, tuple[_SuffixItem, ...]]:
	"""Suffix rules keyed by the suffix's last char ('' for the empty suffix): a name only tries its own group."""
	groups: dict[str, list[_SuffixItem]] = {}
	for item in items:
		groups.setdefault(item[1][-1:], []).append(item)
	return {key: tuple(group) for key, group in groups.items()}


def _required_runs(segment: _Segment) -> tuple[str, ...]:
	"""Distinct non-empty literal runs every match of a generic segment must contain."""
	return tuple(dict.fromkeys(run for run in (segment.prefix, *segment.runs, segment.tail) if run))


class _RuleIndex:
	"""Pattern lookup tables for one `is_dir` kind; every table keeps the pattern's index so last match wins."""

	__slots__ = (
		"anch_generic",
		"anch_literal",
		"anch_suffix_groups",
		"fixed_len",
		"generic",
		"literals",
		"name_only",
		"suffix_groups",
	)

	def __init__(self, patterns: tuple[IgnorePattern, ...], is_dir: bool):
		self.literals: dict[str, int] = {}
		suffixes: list[_SuffixItem] = []
		self.generic: list[_Generic] = []
		self.fixed_len: dict[int, list[_Generic]] = {}  # no `*`: only names of exactly that length can match
		self.anch_literal: dict[str, list[tuple[int, _AnchoredRule]]] = {}
		anch_suffix: list[_SuffixItem] = []
		self.anch_generic: list[tuple[int, _AnchoredRule]] = []
		for index, pattern in enumerate(patterns):
			if pattern.dir_only and not is_dir:
				continue
			if not pattern.anchored:
				segment = pattern.segments[0]
				if segment.literal is not None:
					self.literals[segment.literal] = index  # later index overwrites: last wins
				elif segment.suffix is not None:
					suffixes.append((index, segment.suffix, None))
				else:
					runs = _required_runs(segment)
					top = (*sorted(runs, key=len, reverse=True)[:3], "", "", "")[:3]
					entry = (index, runs, *top, segment)
					if _ANY_RUN in segment.tokens:
						self.generic.append(entry)
					else:
						self.fixed_len.setdefault(len(segment.tokens), []).append(entry)
				continue
			rule = _AnchoredRule(pattern.segments)
			last = pattern.segments[-1]
			if last.globstar:
				self.anch_generic.append((index, rule))
			elif last.literal is not None:
				self.anch_literal.setdefault(last.literal, []).append((index, rule))
			elif last.suffix is not None:
				anch_suffix.append((index, last.suffix, rule))
			else:
				self.anch_generic.append((index, rule))
		self.name_only = not (self.anch_literal or anch_suffix or self.anch_generic)
		self.suffix_groups = _group_by_last_char(suffixes)
		self.anch_suffix_groups = _group_by_last_char(anch_suffix)

	def active_generic(self, text: str) -> list[_Generic]:
		"""Generic globs whose required literal runs all occur in `text` (a whole batch of names joined): the rest
		cannot match any name in the batch (checks the three longest runs)."""
		return [entry for entry in self.generic if entry[2] in text and entry[3] in text and entry[4] in text]

	def best_name(self, name: str, generic: list[_Generic] | None = None) -> int:
		"""Index of the last matching unanchored pattern, or -1. `generic` narrows the globs to try (see above)."""
		best = self.literals.get(name, -1)
		if self.suffix_groups:
			for key in (name[-1], ""):
				for index, suffix, _ in self.suffix_groups.get(key, ()):
					if index > best and name.endswith(suffix):
						best = index
		if self.fixed_len:
			for index, _, run1, run2, run3, segment in self.fixed_len.get(len(name), ()):
				if index > best and run1 in name and run2 in name and run3 in name and segment.matches_generic(name):
					best = index
		for index, _, run1, run2, run3, segment in self.generic if generic is None else generic:
			if index > best and run1 in name and run2 in name and run3 in name and segment.matches_generic(name):
				best = index
		return best

	def best(self, parts: tuple[str, ...], generic: list[_Generic] | None = None) -> int:
		"""Index of the last matching pattern, or -1."""
		name = parts[-1]
		best = self.best_name(name, generic)
		if self.anch_literal:
			for index, rule in self.anch_literal.get(name, ()):
				if index > best and rule.matches(parts):
					best = index
		if self.anch_suffix_groups:
			for key in (name[-1], ""):
				for index, suffix, rule in self.anch_suffix_groups.get(key, ()):
					if index > best and name.endswith(suffix) and rule is not None and rule.matches(parts):
						best = index
		for index, rule in self.anch_generic:
			if index > best and rule.matches(parts):
				best = index
		return best


class _AnchoredRule:
	"""An anchored pattern with cheap depth / first-segment prefilters before the full DP."""

	__slots__ = ("exact", "first_literal", "min_parts", "segments")

	def __init__(self, segments: tuple[_Segment, ...]):
		self.segments = segments
		fixed = sum(1 for segment in segments if not segment.globstar)
		self.exact = fixed == len(segments)
		self.min_parts = fixed if fixed else 1
		first = segments[0]
		self.first_literal = first.literal if not first.globstar else None

	def matches(self, parts: tuple[str, ...]) -> bool:
		count = len(parts)
		if count < self.min_parts or (self.exact and count != self.min_parts):
			return False
		if self.first_literal is not None and parts[0] != self.first_literal:
			return False
		return _match_anchored(self.segments, parts)


@dataclass(frozen=True, slots=True)
class IgnoreRuleSet:
	base: tuple[str, ...]  # dir parts it applies from; () = root / user list
	patterns: tuple[IgnorePattern, ...]
	norm_base: tuple[str, ...] = field(init=False, repr=False, compare=False)
	_file_index: _RuleIndex = field(init=False, repr=False, compare=False)
	_dir_index: _RuleIndex = field(init=False, repr=False, compare=False)

	def __post_init__(self):
		object.__setattr__(self, "norm_base", tuple(normalize_part(part) for part in self.base))
		object.__setattr__(self, "_file_index", _RuleIndex(self.patterns, False))
		object.__setattr__(self, "_dir_index", _RuleIndex(self.patterns, True))

	def index_for(self, is_dir: bool) -> _RuleIndex:
		return self._dir_index if is_dir else self._file_index

	def decide(self, rel_parts: tuple[str, ...], is_dir: bool) -> bool | None:
		"""Last match wins: True = ignore, False = re-included, None = no opinion."""
		return self.decide_normalized(tuple(normalize_part(part) for part in rel_parts), is_dir)

	def decide_normalized(self, parts: tuple[str, ...], is_dir: bool) -> bool | None:
		"""`decide` for parts already passed through `normalize_part`."""
		if not parts:
			return None
		index = self.index_for(is_dir).best(parts)
		if index < 0:
			return None
		return not self.patterns[index].negated


def normalize_part(name: str) -> str:
	"""NFC + casefold: names and patterns compare case-insensitively on every OS."""
	if name.isascii():
		return name.lower()  # ASCII is already NFC and casefold == lower
	return unicodedata.normalize("NFC", name).casefold()


def _strip_trailing_spaces(line: str) -> str:
	"""Drop trailing spaces unless backslash-escaped (as git does)."""
	end = len(line)
	while end > 0 and line[end - 1] == " ":
		backslashes = 0
		index = end - 2
		while index >= 0 and line[index] == "\\":
			backslashes += 1
			index -= 1
		if backslashes % 2:
			break
		end -= 1
	return line[:end]


def _parse_class(text: str, start: int) -> tuple[_CharClass, int] | None:
	"""Parse `[...]` starting at text[start] == '['. Returns the class and the index after `]`, or None if unclosed."""
	index = start + 1
	negated = False
	if index < len(text) and text[index] in "!^":
		negated = True
		index += 1
	singles: set[str] = set()
	ranges: list[tuple[str, str]] = []
	first = True
	while index < len(text):
		char = text[index]
		if char == "]" and not first:
			return _CharClass(negated, frozenset(singles), tuple(ranges)), index + 1
		first = False
		if char == "\\" and index + 1 < len(text):
			index += 1
			char = text[index]
		if index + 2 < len(text) and text[index + 1] == "-" and text[index + 2] != "]":
			high_index = index + 2
			high = text[high_index]
			if high == "\\" and high_index + 1 < len(text):
				high_index += 1
				high = text[high_index]
			ranges.append((char, high))
			index = high_index + 1
			continue
		singles.add(char)
		index += 1
	return None


def _compile_segment(text: str, *, allow_globstar: bool) -> _Segment:
	"""Compile one normalised segment; raises IgnorePatternError(UNCLOSED_BRACKET) with line_number 0 (caller fills in)."""
	if allow_globstar and text == "**":
		return _Segment(globstar=True)
	tokens: list[_Token] = []
	index = 0
	while index < len(text):
		char = text[index]
		if char == "\\":
			index += 1
			if index >= len(text):  # escaped slash (`foo\/`) leaves a segment ending in a lone backslash
				raise IgnorePatternError(line_number=0, pattern=text, reason=IgnoreReason.TRAILING_BACKSLASH)
			tokens.append(text[index])
		elif char == "*":
			if not tokens or tokens[-1] is not _ANY_RUN:
				tokens.append(_ANY_RUN)
		elif char == "?":
			tokens.append(_ANY_ONE)
		elif char == "[":
			parsed = _parse_class(text, index)
			if parsed is None:
				raise IgnorePatternError(line_number=0, pattern=text, reason=IgnoreReason.UNCLOSED_BRACKET)
			token, index = parsed
			tokens.append(token)
			continue
		else:
			tokens.append(char)
		index += 1
	literal = None
	suffix = None
	if all(isinstance(token, str) for token in tokens):
		literal = "".join(token for token in tokens if isinstance(token, str))
	elif tokens and tokens[0] is _ANY_RUN and all(isinstance(token, str) for token in tokens[1:]):
		suffix = "".join(token for token in tokens[1:] if isinstance(token, str))
	return _with_prefilter(_Segment(tokens=tuple(tokens), literal=literal, suffix=suffix))


def _with_prefilter(segment: _Segment) -> _Segment:
	"""Fill the necessary-condition fields (prefix, tail, ordered literal runs, min length) of a compiled segment."""
	tokens = segment.tokens
	if segment.literal is not None or segment.globstar or not tokens:
		return segment
	groups: list[str] = []
	current: list[str] = []
	for token in tokens:
		if isinstance(token, str):
			current.append(token)
		else:
			groups.append("".join(current))
			current = []
	groups.append("".join(current))  # groups[0] precedes the first non-literal token, groups[-1] follows the last
	prefix = groups[0]
	tail = groups[-1]
	middle = tuple(group for group in groups[1:-1] if group)
	if len(groups) == 1:  # no wildcard at all (a literal; handled by the caller)
		return segment
	return _Segment(
		tokens=tokens,
		literal=segment.literal,
		suffix=segment.suffix,
		prefix=prefix,
		tail=tail,
		runs=middle,
		min_len=sum(1 for token in tokens if token is not _ANY_RUN),
		star_only=all(isinstance(token, str) or token is _ANY_RUN for token in tokens),
	)


def _compile_line(line: str, line_number: int) -> IgnorePattern | None:
	"""Compile one raw line; None for blank/comment/empty. Raises IgnorePatternError for bad syntax."""
	text = _strip_trailing_spaces(line)
	if not text or text.startswith("#"):
		return None
	trailing = len(text) - len(text.rstrip("\\"))
	if trailing % 2:
		raise IgnorePatternError(line_number=line_number, pattern=line, reason=IgnoreReason.TRAILING_BACKSLASH)
	negated = text.startswith("!")
	if negated:
		text = text[1:]
	dir_only = text.endswith("/")
	if dir_only:
		text = text[:-1]
	anchored = text.startswith("/") or "/" in text
	raw_segments = [part for part in text.split("/") if part]
	if not raw_segments:
		return None
	try:
		segments = tuple(_compile_segment(normalize_part(part), allow_globstar=anchored) for part in raw_segments)
	except IgnorePatternError as error:
		raise IgnorePatternError(line_number=line_number, pattern=line, reason=error.reason) from None
	if any(segment.literal in {".", ".."} for segment in segments):
		return None  # traversal-looking: a real path part is never "." or "..", so it can never match
	return IgnorePattern(
		raw=line,
		line_number=line_number,
		negated=negated,
		dir_only=dir_only,
		anchored=anchored,
		segments=segments,
	)


def parse_ignore_lines(lines: Sequence[str], *, strict: bool, base: tuple[str, ...] = ()) -> IgnoreRuleSet:
	"""strict=True (user list): caps enforced, raises IgnorePatternError on the first bad line.

	strict=False (.gitignore): skips bad lines, truncates at MAX_GITIGNORE_LINES.
	"""
	if strict:
		if len(lines) > MAX_USER_LINES:
			raise IgnorePatternError(
				line_number=MAX_USER_LINES + 1, pattern=lines[MAX_USER_LINES], reason=IgnoreReason.TOO_MANY_LINES
			)
	else:
		lines = lines[:MAX_GITIGNORE_LINES]
	patterns: list[IgnorePattern] = []
	for number, line in enumerate(lines, start=1):
		if strict and len(line) > MAX_LINE_CHARS:
			raise IgnorePatternError(line_number=number, pattern=line, reason=IgnoreReason.LINE_TOO_LONG)
		try:
			pattern = _compile_line(line, number)
		except IgnorePatternError:
			if strict:
				raise
			continue
		if pattern is not None:
			patterns.append(pattern)
	return IgnoreRuleSet(base=base, patterns=tuple(patterns))


def count_effective_patterns(lines: Sequence[str]) -> int:
	"""Count lines that are not blank, comments or no-ops (`/`, `!`, `../x`); invalid lines count (they error)."""
	count = 0
	for number, line in enumerate(lines, start=1):
		try:
			if _compile_line(line, number) is not None:
				count += 1
		except IgnorePatternError:
			count += 1
	return count


def escape_literal(name: str) -> str:
	"""Backslash-escape * ? [ \\ and a leading # or !, plus trailing spaces."""
	escaped = "".join("\\" + char if char in "*?[\\" else char for char in name)
	if escaped.startswith(("#", "!")):
		escaped = "\\" + escaped
	stripped = escaped.rstrip(" ")
	return stripped + "\\ " * (len(escaped) - len(stripped))


class IgnoreMatcher:
	"""User rules plus a stack of .gitignore rule sets (immutable)."""

	def __init__(self, user: IgnoreRuleSet, stack: tuple[IgnoreRuleSet, ...] = (), *, git_dir: bool = False):
		self._user = user
		self._stack = stack
		self._git_dir = git_dir

	@classmethod
	def from_spec(cls, spec: IgnoreSpec) -> IgnoreMatcher:
		"""Strict parse; raises IgnorePatternError."""
		return cls(parse_ignore_lines(spec.patterns, strict=True), git_dir=spec.respect_gitignore)

	def with_gitignore(self, rules: IgnoreRuleSet) -> IgnoreMatcher:
		return IgnoreMatcher(self._user, (*self._stack, rules), git_dir=self._git_dir)

	def is_ignored(self, rel_parts: tuple[str, ...], is_dir: bool) -> bool:
		"""Order: git_dir check, then user.decide, then the stack deepest first, then False.

		Only correct when called top-down: the walker never descends into an ignored folder, which is what makes
		"cannot re-include a file under an excluded folder" hold without testing ancestors here.
		"""
		if not rel_parts:
			return False
		return self._ignored_normalized(tuple(normalize_part(part) for part in rel_parts), is_dir)

	def filter_names(self, rel_dir: tuple[str, ...], names: Sequence[str], is_dir: bool) -> list[str]:
		"""Names (children of `rel_dir`) that are not ignored. Normalises `rel_dir` once and prefilters the generic
		globs against the whole batch, so a folder whose names contain none of a glob's literals never runs it."""
		normalized_dir = tuple(normalize_part(part) for part in rel_dir)
		normalized_names = [normalize_part(name) for name in names]
		rule_sets = (self._user, *reversed(self._stack))
		joined = "\0".join(normalized_names)
		layers: list[tuple[IgnoreRuleSet, int, _RuleIndex, list[_Generic]]] = []
		for rules in rule_sets:
			depth = len(rules.base)
			if not rules.patterns or len(normalized_dir) < depth:  # no patterns, or names not deeper than its base
				continue
			if depth and rules.norm_base != normalized_dir[:depth]:
				continue
			index = rules.index_for(is_dir)
			layers.append((rules, depth, index, index.active_generic(joined)))
		git_dir = self._git_dir and is_dir
		if not layers and not git_dir:
			return list(names)
		kept: list[str] = []
		for name, normalized in zip(names, normalized_names, strict=True):
			if git_dir and normalized == ".git":
				continue
			parts = (*normalized_dir, normalized)
			for rules, depth, index, generic in layers:
				found = index.best(parts[depth:], generic)
				if found >= 0:
					if not rules.patterns[found].negated:
						break
					kept.append(name)
					break
			else:
				kept.append(name)
		return kept

	def _ignored_normalized(self, normalized: tuple[str, ...], is_dir: bool) -> bool:
		if self._git_dir and is_dir and normalized[-1] == ".git":
			return True
		verdict = self._user.decide_normalized(normalized, is_dir)
		if verdict is not None:
			return verdict
		for rules in reversed(self._stack):
			depth = len(rules.base)
			if len(normalized) <= depth:
				continue
			if depth and rules.norm_base != normalized[:depth]:
				continue
			verdict = rules.decide_normalized(normalized[depth:], is_dir)
			if verdict is not None:
				return verdict
		return False


__all__ = [
	"MAX_GITIGNORE_BYTES",
	"MAX_GITIGNORE_LINES",
	"MAX_LINE_CHARS",
	"MAX_USER_LINES",
	"IgnoreMatcher",
	"IgnorePatternError",
	"IgnorePattern",
	"IgnoreRuleSet",
	"IgnoreSpec",
	"count_effective_patterns",
	"escape_literal",
	"normalize_part",
	"parse_ignore_lines",
]
