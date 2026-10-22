from __future__ import annotations

import random

import pytest

from srxy.domain.exceptions import IgnorePatternError
from srxy.domain.ignore_rules import IgnoreMatcher, IgnoreSpec, _compile_segment, _wildcard_match, parse_ignore_lines


pytestmark = [pytest.mark.unit]

_PATTERN_ALPHABET = "ab.c*?*[ab][!c]x"
_NAME_ALPHABET = "abcx.-"


def _random_pattern(rng: random.Random) -> str:
	return "".join(rng.choice(_PATTERN_ALPHABET) for _ in range(rng.randint(1, 8)))


def _random_name(rng: random.Random) -> str:
	return "".join(rng.choice(_NAME_ALPHABET) for _ in range(rng.randint(1, 9)))


def test_given_random_generic_segments_when_matching_then_prefilter_agrees_with_plain_matcher():
	# given
	rng = random.Random(1234)  # noqa: S311
	checked = 0
	for _ in range(600):
		text = _random_pattern(rng)
		try:
			segment = _compile_segment(text, allow_globstar=False)
		except IgnorePatternError:  # unclosed bracket
			segment = None
		if segment is None:
			continue
		for _ in range(40):
			name = _random_name(rng)
			# when
			fast = segment.matches(name)
			# then
			assert fast == _wildcard_match(segment.tokens, name), (text, name)
			checked += 1
	assert checked > 10_000


def test_given_random_pattern_lists_when_deciding_then_indexed_matcher_equals_last_match_wins_scan():
	# given
	rng = random.Random(99)  # noqa: S311
	for _ in range(150):
		lines = [("!" if rng.random() < 0.25 else "") + _random_pattern(rng) for _ in range(rng.randint(1, 12))]
		try:
			rules = parse_ignore_lines(lines, strict=True)
		except IgnorePatternError:
			rules = None
		if rules is None:
			continue
		matcher = IgnoreMatcher(rules)
		for _ in range(40):
			name = _random_name(rng)
			# when
			got = matcher.is_ignored((name,), False)
			# then
			expected = False
			for pattern in rules.patterns:
				if pattern.matches((name,), False):
					expected = not pattern.negated
			assert got == expected, (lines, name)


def test_given_repeated_names_when_deciding_then_memoised_verdict_is_stable():
	# given
	matcher = IgnoreMatcher.from_spec(IgnoreSpec(patterns=("*cache*", "!keep?cache")))
	# when
	first = [matcher.is_ignored((name,), False) for name in ("my_cache", "keep_cache", "other")]
	second = [matcher.is_ignored((name,), False) for name in ("my_cache", "keep_cache", "other")]
	# then
	assert first == second == [True, False, False]


def test_given_random_rules_and_stack_when_filtering_a_batch_then_it_equals_per_name_is_ignored():
	# given
	rng = random.Random(7)  # noqa: S311
	for _ in range(150):
		user = parse_ignore_lines(_random_lines(rng), strict=False)
		stack = (
			parse_ignore_lines(_random_lines(rng), strict=False),
			parse_ignore_lines(_random_lines(rng), strict=False, base=("a",)),
			parse_ignore_lines(_random_lines(rng), strict=False, base=("a", "b")),
		)
		matcher = IgnoreMatcher(user, stack, git_dir=True)
		names = [_random_name(rng) for _ in range(25)] + [".git"]
		for rel_dir in ((), ("a",), ("a", "b"), ("x",)):
			for is_dir in (False, True):
				# when
				got = matcher.filter_names(rel_dir, names, is_dir)
				# then
				expected = [name for name in names if not matcher.is_ignored((*rel_dir, name), is_dir)]
				assert got == expected, (rel_dir, is_dir)


def _random_lines(rng: random.Random) -> list[str]:
	lines = []
	for _ in range(rng.randint(0, 14)):
		line = _random_pattern(rng)
		if rng.random() < 0.2:
			line = "!" + line
		if rng.random() < 0.15:
			line += "/"
		if rng.random() < 0.15:
			line = "/" + line
		lines.append(line)
	return lines
