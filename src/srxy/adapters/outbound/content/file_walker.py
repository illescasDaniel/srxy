"""Filesystem walker for searchable paths (including archive members)."""

from __future__ import annotations

import fnmatch
import os
from collections.abc import Iterator
from pathlib import Path

from srxy.adapters.outbound.archive.archive_search import (
	archive_member_path,
	is_archive_member_path,
	is_searchable_path,
	is_standalone_archive,
	list_archive_members,
	split_archive_member_path,
)


_NOISE_DIR_NAMES = frozenset({"__pycache__", "node_modules"})

_NOISE_FILE_BASENAMES = frozenset(
	{
		"thumbs.db",
		"ehthumbs.db",
		"desktop.ini",
		"uv.lock",
		"poetry.lock",
		"pipfile.lock",
		"pdm.lock",
		"cargo.lock",
		"gemfile.lock",
		"composer.lock",
		"bun.lock",
		"bun.lockb",
		"flake.lock",
		"package-lock.json",
		"yarn.lock",
		"pnpm-lock.yaml",
		"npm-shrinkwrap.json",
		"go.sum",
	}
)

_NOISE_FILE_PATTERNS = (
	"*.lock",
	"*-lock.json",
	"*-lock.yaml",
	"*-lock.yml",
	"*.min.js",
	"*.min.css",
	"*.js.map",
	"*.css.map",
	"*.mjs.map",
	"*.cjs.map",
	"*.ts.map",
	"~$*",
	"*.tmp",
	"*.temp",
	"*.bak",
	"*.wbk",
	"*.xlk",
	"*.asd",
	"*.laccdb",
	"*.crdownload",
	"*.part",
)


def _is_hidden_path_part(name: str) -> bool:
	return name.startswith(".")


def is_noise_file(name: str) -> bool:
	"""Return True for common junk/lock/temp filenames (case-insensitive)."""
	lowered = name.lower()
	if lowered in _NOISE_FILE_BASENAMES:
		return True
	return any(fnmatch.fnmatchcase(lowered, pattern) for pattern in _NOISE_FILE_PATTERNS)


def _dirname_is_skipped_category(
	name: str,
	*,
	skip_hidden_folders: bool,
	skip_noise_folders: bool,
) -> bool:
	if skip_hidden_folders and _is_hidden_path_part(name):
		return True
	if skip_noise_folders and name in _NOISE_DIR_NAMES:
		return True
	return False


def _filename_is_skipped_category(
	name: str,
	*,
	skip_hidden_folders: bool,
	skip_noise_files: bool,
) -> bool:
	if skip_hidden_folders and _is_hidden_path_part(name):
		return True
	if skip_noise_files and is_noise_file(name):
		return True
	return False


def _should_skip_dirname(
	name: str,
	*,
	skip_hidden_folders: bool,
	skip_noise_folders: bool,
	match_skipped_names: bool,
) -> bool:
	if match_skipped_names:
		return False
	return _dirname_is_skipped_category(
		name,
		skip_hidden_folders=skip_hidden_folders,
		skip_noise_folders=skip_noise_folders,
	)


def _should_skip_filename(
	name: str,
	*,
	skip_hidden_folders: bool,
	skip_noise_files: bool,
	match_skipped_names: bool,
) -> bool:
	if match_skipped_names:
		return False
	return _filename_is_skipped_category(
		name,
		skip_hidden_folders=skip_hidden_folders,
		skip_noise_files=skip_noise_files,
	)


def _filesystem_path_for_skip_check(path: Path) -> Path:
	if is_archive_member_path(path):
		archive, _member = split_archive_member_path(path)
		return archive
	return path


def is_names_only_path(
	path: Path,
	*,
	search_root: Path,
	skip_hidden_folders: bool = True,
	skip_noise_folders: bool = True,
	skip_noise_files: bool = True,
	match_skipped_names: bool = False,
) -> bool:
	"""True when path is only searchable for names (skipped category + match_skipped_names)."""
	if not match_skipped_names:
		return False
	fs_path = _filesystem_path_for_skip_check(path)
	try:
		relative = fs_path.resolve().relative_to(search_root.resolve())
	except ValueError:
		relative = fs_path
	parts = relative.parts
	if not parts:
		return False
	for part in parts[:-1]:
		if _dirname_is_skipped_category(
			part,
			skip_hidden_folders=skip_hidden_folders,
			skip_noise_folders=skip_noise_folders,
		):
			return True
	return _filename_is_skipped_category(
		parts[-1],
		skip_hidden_folders=skip_hidden_folders,
		skip_noise_files=skip_noise_files,
	)


def iter_files(
	root: Path,
	*,
	skip_hidden_folders: bool = True,
	skip_noise_folders: bool = True,
	skip_noise_files: bool = True,
	match_skipped_names: bool = False,
	include_archives: bool = False,
	include_subdirectories: bool = True,
) -> Iterator[Path]:
	if root.is_file():
		yield root
		return
	if not root.is_dir():
		return

	for dirpath, dirnames, filenames in os.walk(root):
		if not include_subdirectories:
			dirnames[:] = []
		else:
			dirnames[:] = [
				name
				for name in dirnames
				if not _should_skip_dirname(
					name,
					skip_hidden_folders=skip_hidden_folders,
					skip_noise_folders=skip_noise_folders,
					match_skipped_names=match_skipped_names,
				)
			]
		current = Path(dirpath)
		for filename in filenames:
			if _should_skip_filename(
				filename,
				skip_hidden_folders=skip_hidden_folders,
				skip_noise_files=skip_noise_files,
				match_skipped_names=match_skipped_names,
			):
				continue
			file_path = current / filename
			yield file_path
			if include_archives and is_standalone_archive(file_path):
				for member in list_archive_members(file_path):
					yield archive_member_path(file_path, member)


def collect_files(
	root: Path,
	*,
	skip_hidden_folders: bool = True,
	skip_noise_folders: bool = True,
	skip_noise_files: bool = True,
	match_skipped_names: bool = False,
	include_archives: bool = False,
	include_subdirectories: bool = True,
) -> list[Path]:
	return list(
		iter_files(
			root,
			skip_hidden_folders=skip_hidden_folders,
			skip_noise_folders=skip_noise_folders,
			skip_noise_files=skip_noise_files,
			match_skipped_names=match_skipped_names,
			include_archives=include_archives,
			include_subdirectories=include_subdirectories,
		)
	)


class DefaultFileWalker:
	"""FileWalkerPort over local filesystem and archive member paths."""

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
	) -> Iterator[Path]:
		yield from iter_files(
			root,
			skip_hidden_folders=skip_hidden_folders,
			skip_noise_folders=skip_noise_folders,
			skip_noise_files=skip_noise_files,
			match_skipped_names=match_skipped_names,
			include_archives=include_archives,
			include_subdirectories=include_subdirectories,
		)

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
	) -> list[Path]:
		return collect_files(
			root,
			skip_hidden_folders=skip_hidden_folders,
			skip_noise_folders=skip_noise_folders,
			skip_noise_files=skip_noise_files,
			match_skipped_names=match_skipped_names,
			include_archives=include_archives,
			include_subdirectories=include_subdirectories,
		)

	def is_searchable(self, path: Path) -> bool:
		return is_searchable_path(path)

	def is_archive_member(self, path: Path) -> bool:
		return is_archive_member_path(path)
