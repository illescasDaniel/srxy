"""DefaultFileWalker honours IgnoreSpec (per-search patterns and .gitignore files)."""

from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path

import pytest

from srxy.adapters.outbound.content.file_walker import DefaultFileWalker
from srxy.domain.ignore_rules import MAX_GITIGNORE_BYTES, IgnoreSpec
from srxy.domain.models import SkippedFile


_WINDOWS = sys.platform == "win32"
_skip_on_windows = pytest.mark.skipif(_WINDOWS, reason="symlinks / chmod unreliable on Windows")


def _touch(path: Path, text: str = "x"):
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(text, encoding="utf-8")


def _rel(root: Path, paths) -> set[str]:
	return {p.relative_to(root).as_posix() for p in paths}


def _walk(root: Path, patterns: tuple[str, ...] = (), *, respect_gitignore: bool = False, **kwargs) -> set[str]:
	spec = IgnoreSpec(patterns=patterns, respect_gitignore=respect_gitignore)
	return _rel(root, DefaultFileWalker().collect_files(root, ignore=spec, **kwargs))


def test_given_bare_name_rule_when_walking_then_skips_file_and_folder_contents_at_any_depth(tmp_path: Path):
	# given
	_touch(tmp_path / "a" / "start")
	_touch(tmp_path / "a" / "other.txt")
	_touch(tmp_path / "b" / "start" / "one.txt")
	_touch(tmp_path / "b" / "start" / "deep" / "two.txt")

	# when
	found = _walk(tmp_path, ("start",))

	# then
	assert found == {"a/other.txt"}


def test_given_leading_slash_rule_when_walking_then_only_root_entry_is_skipped(tmp_path: Path):
	# given
	_touch(tmp_path / "start")
	_touch(tmp_path / "a" / "start")

	# when
	found = _walk(tmp_path, ("/start",))

	# then
	assert found == {"a/start"}


def test_given_trailing_slash_rule_when_walking_then_folder_pruned_and_file_with_same_name_yielded(tmp_path: Path):
	# given
	_touch(tmp_path / "logs" / "a.txt")
	_touch(tmp_path / "x" / "logs")

	# when
	found = _walk(tmp_path, ("logs/",))

	# then
	assert found == {"x/logs"}


def test_given_excluded_folder_and_reinclude_inside_when_walking_then_file_stays_skipped(tmp_path: Path):
	# given
	_touch(tmp_path / "build" / "keep.txt")
	_touch(tmp_path / "build" / "other.txt")
	_touch(tmp_path / "ok.txt")

	# when
	found = _walk(tmp_path, ("build/", "!build/keep.txt"))

	# then
	assert found == {"ok.txt"}


def test_given_ignored_hidden_folder_and_include_hidden_when_walking_then_still_skipped(tmp_path: Path):
	# given
	_touch(tmp_path / ".cache" / "a.txt")
	_touch(tmp_path / ".other" / "b.txt")

	# when
	found = _walk(tmp_path, (".cache/",), skip_hidden_folders=False)

	# then
	assert found == {".other/b.txt"}


def test_given_ignored_noise_entries_and_include_noise_when_walking_then_still_skipped(tmp_path: Path):
	# given
	_touch(tmp_path / "node_modules" / "pkg.js")
	_touch(tmp_path / "uv.lock")
	_touch(tmp_path / "keep.lock")

	# when
	found = _walk(
		tmp_path,
		("node_modules/", "uv.lock"),
		skip_noise_folders=False,
		skip_noise_files=False,
	)

	# then
	assert found == {"keep.lock"}


def test_given_ignored_noise_entries_and_match_skipped_names_when_walking_then_no_name_or_content_candidate(
	tmp_path: Path,
):
	# given
	_touch(tmp_path / "node_modules" / "pkg.js")
	_touch(tmp_path / "uv.lock")
	_touch(tmp_path / "other.lock")
	skipped: list[SkippedFile] = []

	# when
	found = _walk(
		tmp_path,
		("node_modules/", "uv.lock"),
		match_skipped_names=True,
		include_directories=True,
		skipped_files=skipped,
	)

	# then
	assert found == {"other.lock"}


def test_given_respect_gitignore_with_nested_files_when_walking_then_nested_reinclude_wins(tmp_path: Path):
	# given
	_touch(tmp_path / ".gitignore", "*.dat\n")
	_touch(tmp_path / "a.dat")
	_touch(tmp_path / "sub" / ".gitignore", "!keep.dat\n")
	_touch(tmp_path / "sub" / "keep.dat")
	_touch(tmp_path / "sub" / "drop.dat")

	# when
	found = _walk(tmp_path, respect_gitignore=True)

	# then
	assert "a.dat" not in found
	assert "sub/drop.dat" not in found
	assert "sub/keep.dat" in found


def test_given_respect_gitignore_off_when_walking_then_gitignore_rules_have_no_effect(tmp_path: Path):
	# given
	_touch(tmp_path / ".gitignore", "*.dat\n")
	_touch(tmp_path / "a.dat")

	# when
	found = _walk(tmp_path, ("unrelated",), respect_gitignore=False)

	# then
	assert "a.dat" in found


def test_given_gitignore_excludes_and_user_reincludes_when_walking_then_user_rule_wins(tmp_path: Path):
	# given
	_touch(tmp_path / ".gitignore", "x.txt\ny.txt\n")
	_touch(tmp_path / "x.txt")
	_touch(tmp_path / "y.txt")

	# when
	found = _walk(tmp_path, ("!x.txt",), respect_gitignore=True)

	# then
	assert "x.txt" in found
	assert "y.txt" not in found


def test_given_respect_gitignore_on_when_walking_then_git_directory_is_ignored(tmp_path: Path):
	# given
	_touch(tmp_path / ".git" / "config")
	_touch(tmp_path / ".git" / "objects" / "ab" / "cd")
	_touch(tmp_path / "src.txt")

	# when
	found = _walk(tmp_path, respect_gitignore=True, skip_hidden_folders=False)

	# then
	assert found == {"src.txt"}


@_skip_on_windows
def test_given_symlinked_gitignore_when_walking_then_its_rules_are_not_applied(tmp_path: Path):
	# given
	outside = tmp_path / "outside"
	_touch(outside / "rules.txt", "*\n")
	root = tmp_path / "root"
	_touch(root / "a.txt")
	(root / ".gitignore").symlink_to(outside / "rules.txt")

	# when
	found = _walk(root, respect_gitignore=True)

	# then
	assert "a.txt" in found


def test_given_malformed_gitignore_lines_when_walking_then_valid_lines_apply_and_search_completes(tmp_path: Path):
	# given
	_touch(tmp_path / ".gitignore", "[oops\ntrailing\\\n*.dat\n")
	_touch(tmp_path / "a.dat")
	_touch(tmp_path / "b.txt")

	# when
	found = _walk(tmp_path, respect_gitignore=True)

	# then
	assert "a.dat" not in found
	assert "b.txt" in found


def test_given_oversized_gitignore_when_walking_then_lines_within_cap_apply_and_rest_is_ignored(tmp_path: Path):
	# given
	padding = ("# " + "p" * 98 + "\n") * (MAX_GITIGNORE_BYTES // 100 + 10)
	_touch(tmp_path / ".gitignore", "*.early\n" + padding + "*.late\n")
	_touch(tmp_path / "a.early")
	_touch(tmp_path / "b.late")

	# when
	found = _walk(tmp_path, respect_gitignore=True)

	# then
	assert "a.early" not in found
	assert "b.late" in found


@_skip_on_windows
@pytest.mark.skipif(not _WINDOWS and os.geteuid() == 0, reason="root can read any file")
def test_given_unreadable_gitignore_when_walking_then_search_runs_without_its_rules(tmp_path: Path):
	# given
	gitignore = tmp_path / ".gitignore"
	_touch(gitignore, "*.txt\n")
	_touch(tmp_path / "a.txt")
	gitignore.chmod(0o000)

	# when
	try:
		found = _walk(tmp_path, respect_gitignore=True)
	finally:
		gitignore.chmod(0o644)

	# then
	assert "a.txt" in found


@_skip_on_windows
@pytest.mark.parametrize("rule", ["link", "link/"])
def test_given_symlink_to_folder_when_rule_matches_then_link_ignored_and_contents_not_searched(
	tmp_path: Path, rule: str
):
	# given
	_touch(tmp_path / "real" / "f.txt")
	(tmp_path / "link").symlink_to(tmp_path / "real", target_is_directory=True)

	# when
	found = _walk(tmp_path, (rule,), include_directories=True)

	# then
	assert found == {"real", "real/f.txt"}


@_skip_on_windows
def test_given_symlink_to_folder_without_rule_when_walking_then_link_is_yielded_as_directory(tmp_path: Path):
	# given
	_touch(tmp_path / "real" / "f.txt")
	(tmp_path / "link").symlink_to(tmp_path / "real", target_is_directory=True)

	# when
	found = _walk(tmp_path, ("unrelated",), include_directories=True)

	# then
	assert found == {"real", "real/f.txt", "link"}


@_skip_on_windows
def test_given_symlink_to_file_when_rule_has_trailing_slash_then_link_is_not_matched(tmp_path: Path):
	# given
	_touch(tmp_path / "target.txt")
	(tmp_path / "link").symlink_to(tmp_path / "target.txt")

	# when
	found = _walk(tmp_path, ("link/",))

	# then
	assert found == {"target.txt", "link"}


@_skip_on_windows
def test_given_symlink_to_file_when_bare_rule_then_link_is_ignored(tmp_path: Path):
	# given
	_touch(tmp_path / "target.txt")
	(tmp_path / "link").symlink_to(tmp_path / "target.txt")

	# when
	found = _walk(tmp_path, ("link",))

	# then
	assert found == {"target.txt"}


@_skip_on_windows
def test_given_broken_symlink_when_trailing_slash_rule_then_not_matched_and_bare_rule_matches(tmp_path: Path):
	# given
	(tmp_path / "link").symlink_to(tmp_path / "missing")

	# when
	with_slash = _walk(tmp_path, ("link/",))
	bare = _walk(tmp_path, ("link",))

	# then
	assert with_slash == {"link"}
	assert bare == set()


def test_given_root_folder_name_matches_rule_when_walking_then_root_is_still_searched(tmp_path: Path):
	# given
	root = tmp_path / "build"
	_touch(root / "a.txt")

	# when
	found = _walk(root, ("build/", "build"))

	# then
	assert found == {"a.txt"}


def test_given_root_is_single_file_matching_rule_when_walking_then_root_is_still_yielded(tmp_path: Path):
	# given
	target = tmp_path / "notes.log"
	_touch(target)
	spec = IgnoreSpec(patterns=("*.log", "notes.log"))

	# when
	found = DefaultFileWalker().collect_files(target, ignore=spec)

	# then
	assert found == [target]


def test_given_include_directories_when_folder_ignored_then_it_is_never_yielded(tmp_path: Path):
	# given
	_touch(tmp_path / "gone" / "a.txt")
	_touch(tmp_path / "kept" / "b.txt")

	# when
	found = _walk(tmp_path, ("gone/",), include_directories=True)

	# then
	assert found == {"kept", "kept/b.txt"}


def test_given_ignored_archive_and_include_archives_when_walking_then_not_yielded_or_expanded(tmp_path: Path):
	# given
	for name in ("skip.zip", "keep.zip"):
		with zipfile.ZipFile(tmp_path / name, "w") as archive:
			archive.writestr("inner.txt", "hello")

	# when
	found = _walk(tmp_path, ("skip.zip",), include_archives=True)

	# then
	assert "skip.zip" not in found
	assert not any(entry.startswith("skip.zip") for entry in found)
	assert "keep.zip" in found
	assert any(entry.startswith("keep.zip") and entry != "keep.zip" for entry in found)


def test_given_case_differing_rule_when_walking_then_folder_is_skipped(tmp_path: Path):
	# given
	_touch(tmp_path / "build" / "a.txt")
	_touch(tmp_path / "ok.txt")

	# when
	found = _walk(tmp_path, ("Build/",))

	# then
	assert found == {"ok.txt"}


@pytest.mark.parametrize("spec", [None, IgnoreSpec(), IgnoreSpec(patterns=(), respect_gitignore=False)])
def test_given_inactive_spec_when_walking_then_results_equal_walk_without_ignore(tmp_path: Path, spec):
	# given
	_touch(tmp_path / ".gitignore", "*.txt\n")
	_touch(tmp_path / "a.txt")
	_touch(tmp_path / "sub" / "b.md")
	walker = DefaultFileWalker()

	# when
	with_spec = _rel(tmp_path, walker.collect_files(tmp_path, ignore=spec))
	baseline = _rel(tmp_path, walker.collect_files(tmp_path))

	# then
	assert with_spec == baseline


def test_given_ignore_rule_when_iter_files_then_streaming_walk_applies_it(tmp_path: Path):
	# given
	_touch(tmp_path / "a.log")
	_touch(tmp_path / "b.txt")
	spec = IgnoreSpec(patterns=("*.log",))

	# when
	found = _rel(tmp_path, DefaultFileWalker().iter_files(tmp_path, ignore=spec))

	# then
	assert found == {"b.txt"}


def test_given_gitignore_with_escaped_slash_when_walking_then_no_crash_and_other_rules_apply(tmp_path: Path):
	# given
	_touch(tmp_path / ".gitignore", "foo\\/\na\\/b\n*.dat\n")
	_touch(tmp_path / "a.dat")
	_touch(tmp_path / "b.txt")

	# when
	found = _walk(tmp_path, respect_gitignore=True)

	# then
	assert "a.dat" not in found
	assert "b.txt" in found
