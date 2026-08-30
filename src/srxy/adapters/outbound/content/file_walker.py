"""Filesystem walker for searchable paths (including archive members)."""

from __future__ import annotations

import fnmatch
import os
from collections.abc import Callable, Iterator
from pathlib import Path

from srxy.adapters.outbound.archive.archive_search import (
	archive_member_path,
	is_archive_member_path,
	is_searchable_path,
	is_standalone_archive,
	list_archive_members,
	split_archive_member_path,
)
from srxy.adapters.outbound.content.path_access import append_permission_skip, is_access_denied
from srxy.application.search_control import SearchCancelled
from srxy.domain.models import SkippedFile


_NOISE_DIR_NAMES = frozenset({"__pycache__", "node_modules"})

# Skip kernel pseudo-filesystems when walking from filesystem root.
_PSEUDO_FS_DIR_NAMES = frozenset({"proc", "sys", "dev", "run"})

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
	resolved_search_root: Path | None = None,
) -> bool:
	"""True when path is only searchable for names (skipped category + match_skipped_names)."""
	if not match_skipped_names:
		return False
	fs_path = _filesystem_path_for_skip_check(path)
	resolved_root = resolved_search_root if resolved_search_root is not None else search_root.resolve()
	try:
		relative = fs_path.resolve().relative_to(resolved_root)
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


def _filter_dirnames(
	dirnames: list[str],
	*,
	at_filesystem_root: bool,
	skip_hidden_folders: bool,
	skip_noise_folders: bool,
	match_skipped_names: bool,
) -> list[str]:
	filtered: list[str] = []
	for name in dirnames:
		if at_filesystem_root and name in _PSEUDO_FS_DIR_NAMES:
			continue
		if _should_skip_dirname(
			name,
			skip_hidden_folders=skip_hidden_folders,
			skip_noise_folders=skip_noise_folders,
			match_skipped_names=match_skipped_names,
		):
			continue
		filtered.append(name)
	return filtered


def iter_files(
	root: Path,
	*,
	skip_hidden_folders: bool = True,
	skip_noise_folders: bool = True,
	skip_noise_files: bool = True,
	match_skipped_names: bool = False,
	include_archives: bool = False,
	include_subdirectories: bool = True,
	cancel_check: Callable[[], bool] | None = None,
	skipped_files: list[SkippedFile] | None = None,
) -> Iterator[Path]:
	try:
		root_is_file = root.is_file()
		root_is_dir = root.is_dir()
	except OSError as exc:
		if is_access_denied(exc):
			append_permission_skip(skipped_files, root)
			return
		raise
	if root_is_file:
		yield root
		return
	if not root_is_dir:
		return

	listed = 0
	recorded_denied_dirs: set[str] = set()

	def onerror(err: OSError):
		# os.walk calls this when listdir/scandir fails; default is silent prune.
		if not is_access_denied(err) or err.filename is None:
			return
		key = os.path.normcase(os.path.abspath(err.filename))
		if key in recorded_denied_dirs:
			return
		recorded_denied_dirs.add(key)
		append_permission_skip(skipped_files, Path(err.filename))

	try:
		at_filesystem_root = root.resolve() == Path("/")
	except OSError:
		at_filesystem_root = False
	for dirpath, dirnames, filenames in os.walk(root, onerror=onerror):
		if cancel_check is not None and cancel_check():
			raise SearchCancelled()
		if not include_subdirectories:
			dirnames[:] = []
		else:
			dirnames[:] = _filter_dirnames(
				dirnames,
				at_filesystem_root=at_filesystem_root and Path(dirpath).resolve() == Path("/"),
				skip_hidden_folders=skip_hidden_folders,
				skip_noise_folders=skip_noise_folders,
				match_skipped_names=match_skipped_names,
			)
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
			listed += 1
			if cancel_check is not None and cancel_check():
				raise SearchCancelled()
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
	cancel_check: Callable[[], bool] | None = None,
	skipped_files: list[SkippedFile] | None = None,
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
			cancel_check=cancel_check,
			skipped_files=skipped_files,
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
		cancel_check: Callable[[], bool] | None = None,
		skipped_files: list[SkippedFile] | None = None,
	) -> Iterator[Path]:
		yield from iter_files(
			root,
			skip_hidden_folders=skip_hidden_folders,
			skip_noise_folders=skip_noise_folders,
			skip_noise_files=skip_noise_files,
			match_skipped_names=match_skipped_names,
			include_archives=include_archives,
			include_subdirectories=include_subdirectories,
			cancel_check=cancel_check,
			skipped_files=skipped_files,
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
		cancel_check: Callable[[], bool] | None = None,
		skipped_files: list[SkippedFile] | None = None,
	) -> list[Path]:
		return collect_files(
			root,
			skip_hidden_folders=skip_hidden_folders,
			skip_noise_folders=skip_noise_folders,
			skip_noise_files=skip_noise_files,
			match_skipped_names=match_skipped_names,
			include_archives=include_archives,
			include_subdirectories=include_subdirectories,
			cancel_check=cancel_check,
			skipped_files=skipped_files,
		)

	def is_searchable(self, path: Path) -> bool:
		return is_searchable_path(path)

	def is_archive_member(self, path: Path) -> bool:
		return is_archive_member_path(path)
