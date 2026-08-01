"""Filesystem walker for searchable paths (including archive members)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from srxy.adapters.outbound.archive.archive_search import (
	archive_member_path,
	is_archive_member_path,
	is_searchable_path,
	is_standalone_archive,
	list_archive_members,
)


_NOISE_DIR_NAMES = frozenset({"__pycache__", "node_modules"})


def _is_hidden_path_part(name: str) -> bool:
	return name.startswith(".")


def _should_skip_dirname(
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


def iter_files(
	root: Path,
	*,
	skip_hidden_folders: bool = True,
	skip_noise_folders: bool = True,
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
				)
			]
		current = Path(dirpath)
		for filename in filenames:
			if skip_hidden_folders and _is_hidden_path_part(filename):
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
	include_archives: bool = False,
	include_subdirectories: bool = True,
) -> list[Path]:
	return list(
		iter_files(
			root,
			skip_hidden_folders=skip_hidden_folders,
			skip_noise_folders=skip_noise_folders,
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
		include_archives: bool = False,
		include_subdirectories: bool = True,
	) -> Iterator[Path]:
		yield from iter_files(
			root,
			skip_hidden_folders=skip_hidden_folders,
			skip_noise_folders=skip_noise_folders,
			include_archives=include_archives,
			include_subdirectories=include_subdirectories,
		)

	def collect_files(
		self,
		root: Path,
		*,
		skip_hidden_folders: bool = True,
		skip_noise_folders: bool = True,
		include_archives: bool = False,
		include_subdirectories: bool = True,
	) -> list[Path]:
		return collect_files(
			root,
			skip_hidden_folders=skip_hidden_folders,
			skip_noise_folders=skip_noise_folders,
			include_archives=include_archives,
			include_subdirectories=include_subdirectories,
		)

	def is_searchable(self, path: Path) -> bool:
		return is_searchable_path(path)

	def is_archive_member(self, path: Path) -> bool:
		return is_archive_member_path(path)
