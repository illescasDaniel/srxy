from __future__ import annotations

import os
from pathlib import Path

import pytest

from srxy.application.ignore_edit import (
	PathOutsideRootError,
	add_ignore_line,
	pattern_for_path,
	remove_ignore_line,
	row_ignore_choices,
)


pytestmark = pytest.mark.unit


def _kinds(choices) -> list[str]:
	return [choice.kind for choice in choices]


def _by_kind(choices) -> dict[str, str]:
	return {choice.kind: choice.pattern for choice in choices}


def test_given_folder_inside_root_when_pattern_for_path_then_anchored_with_trailing_slash(tmp_path: Path):
	# given
	root = tmp_path / "work"
	folder = root / "src" / "old"
	folder.mkdir(parents=True)

	# when
	pattern = pattern_for_path(folder, root, is_dir=True)

	# then
	assert pattern == "/src/old/"


def test_given_path_outside_root_when_pattern_for_path_then_raises_outside_root(tmp_path: Path):
	# given
	root = tmp_path / "work"
	root.mkdir()
	other = tmp_path / "other" / "x"
	other.parent.mkdir()

	# when / then
	with pytest.raises(PathOutsideRootError):
		pattern_for_path(other, root, is_dir=False)


def test_given_dotdot_escape_when_pattern_for_path_then_raises_outside_root(tmp_path: Path):
	# given
	root = tmp_path / "work"
	root.mkdir()
	(tmp_path / "other").mkdir()

	# when / then
	with pytest.raises(PathOutsideRootError):
		pattern_for_path(root / ".." / "other", root, is_dir=True)


def test_given_sibling_with_same_prefix_when_pattern_for_path_then_raises_outside_root(tmp_path: Path):
	# given
	root = tmp_path / "work"
	root.mkdir()
	sibling = tmp_path / "work2" / "x"
	sibling.parent.mkdir()

	# when / then
	with pytest.raises(PathOutsideRootError):
		pattern_for_path(sibling, root, is_dir=False)


def test_given_file_inside_root_when_pattern_for_path_then_anchored_without_trailing_slash(tmp_path: Path):
	# given
	root = tmp_path / "work"
	file = root / "app" / "debug.log"
	file.parent.mkdir(parents=True)
	file.write_text("x")

	# when
	pattern = pattern_for_path(file, root, is_dir=False)

	# then
	assert pattern == "/app/debug.log"


def test_given_root_reached_through_symlink_when_pattern_for_path_then_resolves_both(tmp_path: Path):
	# given
	real_root = tmp_path / "real" / "work"
	folder = real_root / "src" / "old"
	folder.mkdir(parents=True)
	link = tmp_path / "home"
	try:
		os.symlink(tmp_path / "real", link, target_is_directory=True)
	except (OSError, NotImplementedError):
		pytest.skip("symlinks unavailable")
	root_via_link = link / "work"

	# when
	pattern = pattern_for_path(folder, root_via_link, is_dir=True)

	# then
	assert pattern == "/src/old/"


def test_given_symlink_pointing_outside_root_when_pattern_for_path_then_raises_outside_root(tmp_path: Path):
	# given
	root = tmp_path / "work"
	root.mkdir()
	outside = tmp_path / "other"
	outside.mkdir()
	link = root / "escape"
	try:
		os.symlink(outside, link, target_is_directory=True)
	except (OSError, NotImplementedError):
		pytest.skip("symlinks unavailable")

	# when / then
	with pytest.raises(PathOutsideRootError):
		pattern_for_path(link, root, is_dir=True)


@pytest.mark.parametrize(
	("name", "expected"),
	[
		("a[1]", "/a\\[1\\]"),
		("star*name", "/star\\*name"),
		("what?", "/what\\?"),
	],
)
def test_given_glob_characters_in_name_when_pattern_for_path_then_escaped(tmp_path: Path, name: str, expected: str):
	# given
	root = tmp_path / "work"
	root.mkdir()
	file = root / name

	# when
	pattern = pattern_for_path(file, root, is_dir=False)

	# then
	assert pattern == expected


def test_given_glob_characters_in_folder_name_when_pattern_for_path_then_escaped_with_slash(tmp_path: Path):
	# given
	root = tmp_path / "work"
	folder = root / "dir[x]" / "s*"
	folder.mkdir(parents=True)

	# when
	pattern = pattern_for_path(folder, root, is_dir=True)

	# then
	assert pattern == "/dir\\[x\\]/s\\*/"


def test_given_file_in_subfolder_when_row_ignore_choices_then_file_folder_and_ext(tmp_path: Path):
	# given
	root = tmp_path / "work"
	file = root / "app" / "debug.log"
	file.parent.mkdir(parents=True)
	file.write_text("x")

	# when
	choices = row_ignore_choices(file, root, is_dir=False, archive_path=None)

	# then
	assert _kinds(choices) == ["file", "folder", "ext"]
	assert _by_kind(choices) == {"file": "/app/debug.log", "folder": "/app/", "ext": "*.log"}


def test_given_file_in_nested_folder_when_row_ignore_choices_then_folder_is_parent_anchored(tmp_path: Path):
	# given
	root = tmp_path / "work"
	file = root / "app" / "logs" / "a.log"
	file.parent.mkdir(parents=True)
	file.write_text("x")

	# when
	choices = row_ignore_choices(file, root, is_dir=False, archive_path=None)

	# then
	assert _by_kind(choices)["folder"] == "/app/logs/"


def test_given_file_directly_in_root_when_row_ignore_choices_then_no_folder_choice(tmp_path: Path):
	# given
	root = tmp_path / "work"
	root.mkdir()
	file = root / "notes.txt"
	file.write_text("x")

	# when
	choices = row_ignore_choices(file, root, is_dir=False, archive_path=None)

	# then
	assert _kinds(choices) == ["file", "ext"]
	assert _by_kind(choices) == {"file": "/notes.txt", "ext": "*.txt"}


def test_given_suffixless_file_when_row_ignore_choices_then_no_ext_choice(tmp_path: Path):
	# given
	root = tmp_path / "work"
	file = root / "app" / "Makefile"
	file.parent.mkdir(parents=True)
	file.write_text("x")

	# when
	choices = row_ignore_choices(file, root, is_dir=False, archive_path=None)

	# then
	assert _kinds(choices) == ["file", "folder"]


def test_given_suffixless_file_in_root_when_row_ignore_choices_then_only_file_choice(tmp_path: Path):
	# given
	root = tmp_path / "work"
	root.mkdir()
	file = root / "Makefile"
	file.write_text("x")

	# when
	choices = row_ignore_choices(file, root, is_dir=False, archive_path=None)

	# then
	assert _kinds(choices) == ["file"]


def test_given_extension_with_glob_char_when_row_ignore_choices_then_ext_pattern_escaped(tmp_path: Path):
	# given
	root = tmp_path / "work"
	root.mkdir()
	file = root / "a.l[g"
	file.write_text("x")

	# when
	choices = row_ignore_choices(file, root, is_dir=False, archive_path=None)

	# then
	assert _by_kind(choices)["ext"] == "*.l\\[g"


def test_given_archive_member_row_when_row_ignore_choices_then_only_archive_choice(tmp_path: Path):
	# given
	root = tmp_path / "work"
	archive = root / "data" / "pack.zip"
	archive.parent.mkdir(parents=True)
	archive.write_text("x")
	member = archive / "inner" / "doc.txt"

	# when
	choices = row_ignore_choices(member, root, is_dir=False, archive_path=archive)

	# then
	assert _kinds(choices) == ["archive"]
	assert choices[0].pattern == "/data/pack.zip"


def test_given_directory_result_when_row_ignore_choices_then_only_this_folder_choice(tmp_path: Path):
	# given
	root = tmp_path / "work"
	folder = root / "src" / "old"
	folder.mkdir(parents=True)

	# when
	choices = row_ignore_choices(folder, root, is_dir=True, archive_path=None)

	# then
	assert _kinds(choices) == ["this_folder"]
	assert choices[0].pattern == "/src/old/"


def test_given_row_outside_root_when_row_ignore_choices_then_raises_outside_root(tmp_path: Path):
	# given
	root = tmp_path / "work"
	root.mkdir()
	file = tmp_path / "other" / "x.txt"
	file.parent.mkdir()
	file.write_text("x")

	# when / then
	with pytest.raises(PathOutsideRootError):
		row_ignore_choices(file, root, is_dir=False, archive_path=None)


def test_given_new_pattern_when_add_ignore_line_then_appended_and_reported_added():
	# given
	text = "*.log\n"

	# when
	new_text, added = add_ignore_line(text, "/app/debug.log")

	# then
	assert added is True
	assert new_text.splitlines() == ["*.log", "/app/debug.log"]


def test_given_empty_text_when_add_ignore_line_then_single_line():
	# given / when
	new_text, added = add_ignore_line("", "*.log")

	# then
	assert added is True
	assert new_text.splitlines() == ["*.log"]


def test_given_text_without_trailing_newline_when_add_ignore_line_then_lines_not_merged():
	# given / when
	new_text, added = add_ignore_line("a", "b")

	# then
	assert added is True
	assert new_text.splitlines() == ["a", "b"]


def test_given_existing_pattern_when_add_ignore_line_then_no_op():
	# given
	text = "*.log\nbuild/\n"

	# when
	new_text, added = add_ignore_line(text, "*.log")

	# then
	assert added is False
	assert new_text == text


def test_given_added_rule_when_remove_ignore_line_then_only_that_line_removed():
	# given
	text, _ = add_ignore_line("a\n\n# note\nb", "/app/debug.log")

	# when
	result = remove_ignore_line(text, "/app/debug.log")

	# then
	assert result.splitlines() == ["a", "", "# note", "b"]


def test_given_pattern_twice_when_remove_ignore_line_then_only_last_occurrence_removed():
	# given
	text = "x\ny\nx"

	# when
	result = remove_ignore_line(text, "x")

	# then
	assert result.splitlines() == ["x", "y"]


def test_given_missing_pattern_when_remove_ignore_line_then_unchanged():
	# given
	text = "a\nb"

	# when
	result = remove_ignore_line(text, "zzz")

	# then
	assert result.splitlines() == ["a", "b"]


def test_given_longer_line_containing_pattern_when_remove_ignore_line_then_only_exact_line_matches():
	# given
	text = "*.log\n*.log.bak"

	# when
	result = remove_ignore_line(text, "*.log")

	# then
	assert result.splitlines() == ["*.log.bak"]


def test_given_symlink_to_file_inside_root_when_row_choices_then_uses_link_own_path(tmp_path: Path):
	# given
	root = tmp_path / "work"
	(root / "a").mkdir(parents=True)
	(root / "b").mkdir()
	(root / "b" / "real.txt").write_text("x")
	link = root / "a" / "link.txt"
	link.symlink_to(Path("..") / "b" / "real.txt")

	# when
	choices = row_ignore_choices(link, root, is_dir=False, archive_path=None)

	# then
	assert _by_kind(choices) == {"file": "/a/link.txt", "folder": "/a/", "ext": "*.txt"}


def test_given_symlink_to_file_outside_root_when_row_choices_then_still_offers_own_path(tmp_path: Path):
	# given
	root = tmp_path / "work"
	root.mkdir()
	outside = tmp_path / "outside.txt"
	outside.write_text("x")
	link = root / "link.txt"
	link.symlink_to(outside)

	# when
	choices = row_ignore_choices(link, root, is_dir=False, archive_path=None)

	# then
	assert _by_kind(choices) == {"file": "/link.txt", "ext": "*.txt"}


def test_given_symlink_to_folder_when_row_choices_for_dir_then_this_folder_uses_link_path(tmp_path: Path):
	# given
	root = tmp_path / "work"
	(root / "real").mkdir(parents=True)
	link = root / "alias"
	link.symlink_to(root / "real", target_is_directory=True)

	# when
	choices = row_ignore_choices(link, root, is_dir=True, archive_path=None)

	# then
	assert _by_kind(choices) == {"this_folder": "/alias/"}
