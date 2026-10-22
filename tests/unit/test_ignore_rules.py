from __future__ import annotations

import time

import pytest

from srxy.domain.exceptions import IgnorePatternError, IgnoreReason
from srxy.domain.ignore_rules import (
	MAX_GITIGNORE_LINES,
	MAX_LINE_CHARS,
	MAX_USER_LINES,
	IgnoreMatcher,
	IgnoreRuleSet,
	IgnoreSpec,
	count_effective_patterns,
	escape_literal,
	normalize_part,
	parse_ignore_lines,
)


pytestmark = [pytest.mark.unit]


def _matcher(*lines: str) -> IgnoreMatcher:
	return IgnoreMatcher.from_spec(IgnoreSpec(patterns=tuple(lines)))


def _ignored(matcher: IgnoreMatcher, path: str, *, is_dir: bool = False) -> bool:
	"""Mimic the walker: test every ancestor folder top-down, then the entry itself.

	`is_ignored` is only correct when called top-down (an excluded parent folder is never descended into).
	"""
	parts = tuple(path.split("/"))
	for depth in range(1, len(parts)):
		if matcher.is_ignored(parts[:depth], True):
			return True
	return matcher.is_ignored(parts, is_dir)


# --- Scenario: bare name matches files and folders at any depth


def test_given_bare_name_rule_when_matching_file_and_folder_at_depth_then_both_ignored():
	# given
	matcher = _matcher("start")

	# when
	file_ignored = _ignored(matcher, "a/start")
	folder_ignored = _ignored(matcher, "b/start", is_dir=True)
	inside_folder_ignored = _ignored(matcher, "b/start/inner.txt")
	deep_ignored = _ignored(matcher, "x/y/z/start")

	# then
	assert file_ignored
	assert folder_ignored
	assert inside_folder_ignored
	assert deep_ignored


def test_given_bare_name_rule_when_matching_other_names_then_not_ignored():
	# given
	matcher = _matcher("start")

	# when / then
	assert not _ignored(matcher, "a/starting")
	assert not _ignored(matcher, "a/restart")
	assert not _ignored(matcher, "a/start.txt")


# --- Scenario: leading slash anchors to the root


def test_given_leading_slash_rule_when_matching_then_only_root_entry_ignored():
	# given
	matcher = _matcher("/start")

	# when
	at_root = _ignored(matcher, "start")
	nested = _ignored(matcher, "a/start")

	# then
	assert at_root
	assert not nested


def test_given_rule_with_inner_slash_when_matching_then_anchored_to_root():
	# given
	matcher = _matcher("a/b")

	# when / then
	assert _ignored(matcher, "a/b")
	assert not _ignored(matcher, "x/a/b")


# --- Scenario: trailing slash matches folders only


def test_given_trailing_slash_rule_when_matching_folder_and_file_then_only_folder_ignored():
	# given
	matcher = _matcher("logs/")

	# when
	folder_ignored = _ignored(matcher, "logs", is_dir=True)
	nested_folder_ignored = _ignored(matcher, "x/logs", is_dir=True)
	file_ignored = _ignored(matcher, "logs", is_dir=False)
	nested_file_ignored = _ignored(matcher, "x/logs", is_dir=False)

	# then
	assert folder_ignored
	assert nested_folder_ignored
	assert not file_ignored
	assert not nested_file_ignored


# --- Scenario: glob and re-include


def test_given_glob_and_reinclude_when_matching_then_reincluded_file_not_ignored():
	# given
	matcher = _matcher("*.log", "!keep.log")

	# when
	debug_ignored = _ignored(matcher, "debug.log")
	keep_ignored = _ignored(matcher, "keep.log")
	nested_keep_ignored = _ignored(matcher, "a/keep.log")
	nested_debug_ignored = _ignored(matcher, "a/debug.log")

	# then
	assert debug_ignored
	assert not keep_ignored
	assert not nested_keep_ignored
	assert nested_debug_ignored


def test_given_reinclude_before_exclude_when_matching_then_last_match_wins_and_ignored():
	# given
	matcher = _matcher("!keep.log", "*.log")

	# when / then
	assert _ignored(matcher, "keep.log")


@pytest.mark.parametrize(
	("pattern", "name", "expected"),
	[
		("?.md", "a.md", True),
		("?.md", "ab.md", False),
		("[a-c]x", "bx", True),
		("[a-c]x", "dx", False),
		("[!a-c]x", "dx", True),
		("[!a-c]x", "bx", False),
		("a*c", "abbbc", True),
		("a*c", "abbb", False),
		("*.tar.gz", "x.tar.gz", True),
	],
)
def test_given_glob_pattern_when_matching_name_then_follows_gitignore_glob_rules(
	pattern: str, name: str, expected: bool
):
	# given
	matcher = _matcher(pattern)

	# when
	result = _ignored(matcher, name)

	# then
	assert result is expected


def test_given_star_when_matching_then_does_not_cross_path_separators():
	# given
	matcher = _matcher("/a*c")

	# when / then
	assert _ignored(matcher, "abc")
	assert not _ignored(matcher, "a/c")


# --- Scenario: cannot re-include under an excluded folder


def test_given_excluded_folder_and_reinclude_inside_when_walking_top_down_then_file_still_ignored():
	# given
	matcher = _matcher("build/", "!build/keep.txt")

	# when
	# The walker prunes `build/` after the first call and never tests `build/keep.txt` directly,
	# so the top-down check on the parent decides.
	folder_ignored = matcher.is_ignored(("build",), True)
	file_ignored = _ignored(matcher, "build/keep.txt")

	# then
	assert folder_ignored
	assert file_ignored


# --- Scenario: double-star in the middle


def test_given_double_star_in_the_middle_when_matching_then_zero_or_more_folders_between():
	# given
	matcher = _matcher("docs/**/draft*")

	# when
	deep = _ignored(matcher, "docs/a/b/draft1.md")
	direct = _ignored(matcher, "docs/draft2.md")
	other_name = _ignored(matcher, "docs/a/b/final.md")
	wrong_root = _ignored(matcher, "other/docs/draft3.md")

	# then
	assert deep
	assert direct
	assert not other_name
	assert not wrong_root


def test_given_leading_double_star_when_matching_then_any_depth_including_root():
	# given
	matcher = _matcher("**/deep")

	# when / then
	assert _ignored(matcher, "deep")
	assert _ignored(matcher, "a/b/deep")
	assert not _ignored(matcher, "a/deeper")


def test_given_trailing_double_star_when_matching_then_contents_ignored_but_not_folder_itself():
	# given
	matcher = _matcher("abc/**")

	# when
	contents_ignored = matcher.is_ignored(("abc", "x"), False)
	deep_contents_ignored = _ignored(matcher, "abc/x/y.txt")
	folder_ignored = matcher.is_ignored(("abc",), True)

	# then
	assert contents_ignored
	assert deep_contents_ignored
	assert not folder_ignored


# --- Scenario: comments and blank lines


def test_given_comments_and_blank_lines_when_parsing_then_no_rule_created_from_them():
	# given
	lines = ["# note", "", "*.log", "", "# another"]

	# when
	rules = parse_ignore_lines(lines, strict=True)

	# then
	assert len(rules.patterns) == 1
	assert rules.patterns[0].raw == "*.log"
	assert rules.patterns[0].line_number == 3


def test_given_only_comments_and_blanks_when_matching_then_nothing_ignored():
	# given
	matcher = _matcher("# note", "", "#")

	# when / then
	assert not _ignored(matcher, "note")
	assert not _ignored(matcher, "a/b.txt")


def test_given_escaped_hash_when_matching_then_matches_literal_hash_name():
	# given
	matcher = _matcher("\\#note")

	# when / then
	assert _ignored(matcher, "#note")
	assert not _ignored(matcher, "note")


def test_given_pattern_flags_when_parsing_then_negated_dir_only_and_anchored_are_set():
	# given
	lines = ["!a/", "/b", "c/d", "e"]

	# when
	patterns = parse_ignore_lines(lines, strict=True).patterns

	# then
	negated, rooted, inner, bare = patterns
	assert (negated.negated, negated.dir_only, negated.anchored) == (True, True, False)
	assert (rooted.negated, rooted.dir_only, rooted.anchored) == (False, False, True)
	assert (inner.negated, inner.dir_only, inner.anchored) == (False, False, True)
	assert (bare.negated, bare.dir_only, bare.anchored) == (False, False, False)


def test_given_rule_set_when_deciding_then_true_false_or_none_by_last_match():
	# given
	rules = parse_ignore_lines(["*.log", "!keep.log"], strict=True)

	# when
	ignored = rules.decide(("debug.log",), False)
	reincluded = rules.decide(("keep.log",), False)
	no_opinion = rules.decide(("readme.md",), False)

	# then
	assert ignored is True
	assert reincluded is False
	assert no_opinion is None


# --- Scenario: case-insensitive on every OS


def test_given_mixed_case_folder_rule_when_matching_lowercase_folder_then_ignored():
	# given
	matcher = _matcher("Build/")

	# when
	lower = _ignored(matcher, "build", is_dir=True)
	upper = _ignored(matcher, "BUILD", is_dir=True)
	as_file = _ignored(matcher, "build", is_dir=False)

	# then
	assert lower
	assert upper
	assert not as_file


def test_given_glob_rule_when_matching_other_case_then_ignored():
	# given
	matcher = _matcher("*.LOG")

	# when / then
	assert _ignored(matcher, "a/debug.log")
	assert _ignored(matcher, "a/Debug.Log")


def test_given_equivalent_unicode_forms_when_normalizing_then_equal_and_casefolded():
	# given
	decomposed = "é"
	composed = "é"

	# when / then
	assert normalize_part(decomposed) == normalize_part(composed)
	assert normalize_part("ABC") == "abc"


def test_given_decomposed_rule_when_matching_composed_name_then_ignored():
	# given
	matcher = _matcher("café")

	# when / then
	assert _ignored(matcher, "café")


# --- Scenario: pathological pattern stays linear


@pytest.mark.parametrize("pattern", ["**********b", "a*a*a*a*a*a*a*a*a*c", "**/**/**/**/**/**/**/**/b"])
def test_given_pathological_pattern_when_matching_255_char_names_then_completes_quickly(pattern: str):
	# given
	matcher = _matcher(pattern)
	names = ["a" * 255, "a" * 254 + "b", "ab" * 127 + "a"]
	deep_path = tuple(["a" * 255] * 8)

	# when
	started = time.perf_counter()
	results = [matcher.is_ignored((name,), False) for name in names]
	deep_result = matcher.is_ignored(deep_path, False)
	elapsed = time.perf_counter() - started

	# then
	assert elapsed < 0.05
	assert isinstance(deep_result, bool)
	assert all(isinstance(result, bool) for result in results)


def test_given_pathological_star_pattern_when_matching_then_result_is_correct():
	# given
	matcher = _matcher("**********b")

	# when / then
	assert matcher.is_ignored(("a" * 254 + "b",), False)
	assert not matcher.is_ignored(("a" * 255,), False)


# --- Scenario: traversal-looking pattern


def test_given_traversal_looking_rule_when_matching_then_nothing_matches():
	# given
	matcher = _matcher("../etc/passwd")

	# when / then
	assert not _ignored(matcher, "etc/passwd")
	assert not _ignored(matcher, "a/etc/passwd")
	assert not matcher.is_ignored(("..", "etc", "passwd"), False)
	assert not matcher.is_ignored(("etc",), True)
	assert not matcher.is_ignored(("passwd",), False)


# --- Scenario: size caps


def test_given_too_many_lines_when_parsing_strict_then_raises_too_many_lines():
	# given
	lines = ["x"] * (MAX_USER_LINES + 1)

	# when
	with pytest.raises(IgnorePatternError) as caught:
		parse_ignore_lines(lines, strict=True)

	# then
	assert caught.value.reason is IgnoreReason.TOO_MANY_LINES


def test_given_exactly_max_lines_when_parsing_strict_then_accepted():
	# given
	lines = [f"p{index}" for index in range(MAX_USER_LINES)]

	# when
	rules = parse_ignore_lines(lines, strict=True)

	# then
	assert len(rules.patterns) == MAX_USER_LINES


def test_given_too_many_lines_when_building_matcher_from_spec_then_raises():
	# given
	spec = IgnoreSpec(patterns=tuple(["x"] * (MAX_USER_LINES + 1)))

	# when / then
	with pytest.raises(IgnorePatternError) as caught:
		IgnoreMatcher.from_spec(spec)
	assert caught.value.reason is IgnoreReason.TOO_MANY_LINES


def test_given_long_line_after_blank_and_comment_when_parsing_strict_then_error_has_one_based_line_number():
	# given
	long_line = "a" * (MAX_LINE_CHARS + 1)
	lines = ["# note", "", long_line]

	# when
	with pytest.raises(IgnorePatternError) as caught:
		parse_ignore_lines(lines, strict=True)

	# then
	assert caught.value.reason is IgnoreReason.LINE_TOO_LONG
	assert caught.value.line_number == 3


def test_given_line_of_exactly_max_chars_when_parsing_strict_then_accepted():
	# given
	lines = ["a" * MAX_LINE_CHARS]

	# when
	rules = parse_ignore_lines(lines, strict=True)

	# then
	assert len(rules.patterns) == 1


# --- Scenario: invalid user pattern


def test_given_unclosed_bracket_when_parsing_strict_then_raises_with_line_number_and_reason():
	# given
	lines = ["*.log", "[oops"]

	# when
	with pytest.raises(IgnorePatternError) as caught:
		parse_ignore_lines(lines, strict=True)

	# then
	assert caught.value.reason is IgnoreReason.UNCLOSED_BRACKET
	assert caught.value.line_number == 2
	assert caught.value.pattern == "[oops"


def test_given_trailing_backslash_when_parsing_strict_then_raises_trailing_backslash():
	# given
	lines = ["", "foo\\"]

	# when
	with pytest.raises(IgnorePatternError) as caught:
		parse_ignore_lines(lines, strict=True)

	# then
	assert caught.value.reason is IgnoreReason.TRAILING_BACKSLASH
	assert caught.value.line_number == 2


@pytest.mark.parametrize("bad", ["[oops", "foo\\"])
def test_given_invalid_pattern_when_building_matcher_from_spec_then_raises(bad: str):
	# given
	spec = IgnoreSpec(patterns=(bad,))

	# when / then
	with pytest.raises(IgnorePatternError):
		IgnoreMatcher.from_spec(spec)


def test_given_invalid_lines_when_parsing_non_strict_then_skipped_and_valid_lines_kept():
	# given
	lines = ["[oops", "*.log", "bad\\", "!keep.log"]

	# when
	rules = parse_ignore_lines(lines, strict=False)

	# then
	assert [pattern.raw for pattern in rules.patterns] == ["*.log", "!keep.log"]
	assert [pattern.line_number for pattern in rules.patterns] == [2, 4]


def test_given_more_than_gitignore_line_cap_when_parsing_non_strict_then_rest_ignored():
	# given
	lines = ["x"] * MAX_GITIGNORE_LINES + ["beyond"]

	# when
	rules = parse_ignore_lines(lines, strict=False)

	# then
	assert len(rules.patterns) == MAX_GITIGNORE_LINES
	assert all(pattern.raw == "x" for pattern in rules.patterns)


# --- parse_ignore_lines base handling


def test_given_base_when_parsing_then_rule_set_records_base_and_matcher_applies_rules_below_it():
	# given
	rules = parse_ignore_lines(["*.tmp", "!keep.tmp"], strict=False, base=("sub",))
	matcher = _matcher().with_gitignore(rules)

	# when
	skipped = _ignored(matcher, "sub/a.tmp")
	reincluded = _ignored(matcher, "sub/keep.tmp")
	deeper = _ignored(matcher, "sub/deep/a.tmp")

	# then
	assert rules.base == ("sub",)
	assert skipped
	assert not reincluded
	assert deeper


def test_given_anchored_rule_in_nested_gitignore_when_matching_then_relative_to_its_directory():
	# given
	rules = parse_ignore_lines(["/x"], strict=False, base=("sub",))
	matcher = _matcher().with_gitignore(rules)

	# when
	direct = matcher.is_ignored(("sub", "x"), False)
	deeper = matcher.is_ignored(("sub", "a", "x"), False)

	# then
	assert direct
	assert not deeper


def test_given_root_and_nested_gitignore_when_matching_then_deeper_file_wins():
	# given
	root = parse_ignore_lines(["*.tmp"], strict=False)
	nested = parse_ignore_lines(["!keep.tmp"], strict=False, base=("sub",))
	matcher = _matcher().with_gitignore(root).with_gitignore(nested)

	# when
	root_tmp = _ignored(matcher, "a.tmp")
	kept = _ignored(matcher, "sub/keep.tmp")
	other_tmp = _ignored(matcher, "sub/x.tmp")

	# then
	assert root_tmp
	assert not kept
	assert other_tmp


def test_given_user_rule_and_gitignore_when_matching_then_user_rule_wins():
	# given
	gitignore = parse_ignore_lines(["x.txt"], strict=False)
	matcher = _matcher("!x.txt").with_gitignore(gitignore)

	# when / then
	assert not _ignored(matcher, "x.txt")


def test_given_with_gitignore_when_called_then_original_matcher_unchanged():
	# given
	original = _matcher()

	# when
	extended = original.with_gitignore(parse_ignore_lines(["*.tmp"], strict=False))

	# then
	assert not original.is_ignored(("a.tmp",), False)
	assert extended.is_ignored(("a.tmp",), False)


def test_given_git_dir_flag_when_matching_then_dot_git_folder_ignored():
	# given
	empty = IgnoreRuleSet(base=(), patterns=())
	with_flag = IgnoreMatcher(empty, git_dir=True)
	without_flag = IgnoreMatcher(empty)

	# when / then
	assert with_flag.is_ignored((".git",), True)
	assert not with_flag.is_ignored((".github",), True)
	assert not without_flag.is_ignored((".git",), True)


# --- count_effective_patterns


def test_given_lines_with_blanks_and_comments_when_counting_then_only_real_patterns_counted():
	# given
	lines = ["# a", "", "*.log", "!keep.log", "\\#literal", ""]

	# when
	count = count_effective_patterns(lines)

	# then
	assert count == 3


def test_given_empty_list_when_counting_then_zero():
	# given / when / then
	assert count_effective_patterns([]) == 0


# --- escape_literal round trip


@pytest.mark.parametrize(
	("name", "other"),
	[
		("plain.txt", "plain.tx"),
		("a*b", "aXb"),
		("a?b", "aXb"),
		("[x]", "x"),
		("back\\slash", "backslash"),
		("#hash", "hash"),
		("!bang", "bang"),
		("trail ", "trail"),
		("star*", "starfish"),
	],
)
def test_given_escaped_name_when_matching_then_matches_only_itself(name: str, other: str):
	# given
	matcher = _matcher(escape_literal(name))

	# when
	itself = matcher.is_ignored((name,), False)
	nested = matcher.is_ignored(("dir", name), False)
	different = matcher.is_ignored((other,), False)

	# then
	assert itself
	assert nested
	assert not different


def test_given_escaped_anchored_path_when_matching_then_matches_exact_path_only():
	# given
	matcher = _matcher("/" + escape_literal("my[dir]") + "/" + escape_literal("a*.txt"))

	# when
	exact = _ignored(matcher, "my[dir]/a*.txt")
	other = _ignored(matcher, "my[dir]/abc.txt")

	# then
	assert exact
	assert not other


# --- IgnoreSpec.active


def test_given_default_spec_when_checking_active_then_false():
	# given / when / then
	assert IgnoreSpec().active is False


def test_given_patterns_when_checking_active_then_true():
	# given / when / then
	assert IgnoreSpec(patterns=("*.log",)).active is True


def test_given_respect_gitignore_when_checking_active_then_true():
	# given / when / then
	assert IgnoreSpec(respect_gitignore=True).active is True


@pytest.mark.parametrize("bad", ["foo\\/", "a\\/b", "x/\\/y"])
def test_given_escaped_slash_when_parsing_strict_then_raises_trailing_backslash(bad: str):
	# given
	lines = ["ok", bad]

	# when
	with pytest.raises(IgnorePatternError) as caught:
		parse_ignore_lines(lines, strict=True)

	# then
	assert caught.value.reason is IgnoreReason.TRAILING_BACKSLASH
	assert caught.value.line_number == 2


@pytest.mark.parametrize("bad", ["foo\\/", "a\\/b", "x/\\/y"])
def test_given_escaped_slash_when_parsing_non_strict_then_line_skipped_and_others_apply(bad: str):
	# given
	lines = ["*.log", bad, "*.tmp"]

	# when
	rules = parse_ignore_lines(lines, strict=False)

	# then
	assert [pattern.raw for pattern in rules.patterns] == ["*.log", "*.tmp"]


def test_given_noop_lines_when_counting_then_they_are_not_counted():
	# given
	lines = ["/", "!", "../x", "*.log"]

	# when
	count = count_effective_patterns(lines)

	# then
	assert count == 1
