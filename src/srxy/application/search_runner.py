"""Run file search from argparse-style args (shared by CLI / TUI / GUI)."""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable

from srxy.application.search_control import SearchCancelled
from srxy.domain.file_query import FileQ, coerce_file_query, file_q_from_dict
from srxy.domain.models import FileSearchResult, SkippedFile
from srxy.domain.progress import ActivityCallback


def resolve_search_modes(args: argparse.Namespace) -> tuple[bool, bool]:
	if args.names_only:
		return True, False
	if args.content_only:
		return False, True

	search_names = True if args.search_names is None else args.search_names
	search_contents = True if args.search_contents is None else args.search_contents
	return search_names, search_contents


def resolve_file_query(args: argparse.Namespace) -> FileQ:
	if getattr(args, "query_expr", None) is not None:
		value = args.query_expr
		if isinstance(value, FileQ):
			return value
		if isinstance(value, dict):
			return file_q_from_dict(value)
	query = args.query or ""
	return coerce_file_query(query)


def apply_args_to_env(args: argparse.Namespace):
	if args.semantic_all:
		os.environ["SRXY_SEMANTIC"] = "1"
		os.environ["SRXY_OCR"] = "1"
		os.environ["SRXY_SEMANTIC_IMAGE"] = "1"
		os.environ["SRXY_TRANSCRIBE"] = "1"
	else:
		_set_mode_env("SRXY_SEMANTIC", args.semantic)
		_set_mode_env("SRXY_OCR", args.ocr)
		_set_mode_env("SRXY_SEMANTIC_IMAGE", args.semantic_image)
		_set_mode_env("SRXY_TRANSCRIBE", args.transcribe)
	if args.max_ocr_file_size is not None:
		os.environ["SRXY_OCR_MAX_FILE_SIZE"] = str(args.max_ocr_file_size)
	if args.max_transcribe_file_size is not None:
		os.environ["SRXY_TRANSCRIBE_MAX_FILE_SIZE"] = str(args.max_transcribe_file_size)
	if args.transcribe_model is not None:
		os.environ["SRXY_TRANSCRIBE_MODEL"] = args.transcribe_model
	os.environ["SRXY_TRANSCRIBE_THRESHOLD"] = str(args.transcribe_threshold)


def _set_mode_env(name: str, enabled: bool):
	if enabled:
		os.environ[name] = "1"
	else:
		os.environ.pop(name, None)


def normalize_max_file_size(value: int | None) -> int | None:
	if value is not None and value <= 0:
		return None
	return value


def execute_search(
	args: argparse.Namespace,
	*,
	skipped_files: list[SkippedFile] | None = None,
	on_progress: Callable[[int, int], None] | None = None,
	on_activity: ActivityCallback | None = None,
	on_result: Callable[[FileSearchResult], None] | None = None,
	cancel_check: Callable[[], bool] | None = None,
	allow_process_pool: bool = False,
) -> tuple[list[FileSearchResult], list[SkippedFile]]:
	from srxy.adapters.outbound.ocr.ocr_text import ocr_requested
	from srxy.adapters.outbound.transcribe.transcribe_text import transcribe_requested
	from srxy.application.use_cases.search_files import magic_file_search

	search_names, search_contents = resolve_search_modes(args)
	raw_docs = getattr(args, "search_docs_tags", None)
	search_docs_tags = True if raw_docs is None else bool(raw_docs)
	if not search_contents:
		search_docs_tags = False
	effective_skipped = skipped_files if skipped_files is not None else []
	query_expr = resolve_file_query(args)
	ocr = ocr_requested(None) if search_contents else False
	transcribe = transcribe_requested(None) if search_contents else False
	try:
		results = magic_file_search(
			args.path,
			query_expr,
			search_names=search_names,
			search_contents=search_contents,
			search_docs_tags=search_docs_tags,
			threshold=args.threshold,
			semantic_image_threshold=args.semantic_image_threshold,
			transcribe_threshold=args.transcribe_threshold,
			limit=args.limit,
			max_file_size=normalize_max_file_size(args.max_file_size),
			max_matches=args.max_matches,
			skip_hidden_folders=not args.include_hidden,
			skip_noise_folders=not args.include_noise,
			skip_noise_files=not bool(getattr(args, "include_noise_files", False)),
			match_skipped_names=bool(getattr(args, "match_skipped_names", False)) and search_names,
			include_archives=bool(getattr(args, "include_archives", False)),
			include_subdirectories=bool(getattr(args, "include_subdirectories", True)),
			skipped_files=effective_skipped,
			ocr=ocr,
			transcribe=transcribe,
			on_progress=on_progress,
			on_activity=on_activity,
			on_result=on_result,
			cancel_check=cancel_check,
			allow_process_pool=allow_process_pool,
		)
	except SearchCancelled as error:
		if error.skipped_files:
			effective_skipped.extend(error.skipped_files)
		raise SearchCancelled(results=error.results, skipped_files=effective_skipped) from error
	return results, effective_skipped


class FileSearchService:
	"""Inbound-port implementation wrapping ``execute_search``."""

	def execute(
		self,
		args: argparse.Namespace,
		*,
		skipped_files: list[SkippedFile] | None = None,
		on_progress: Callable[[int, int], None] | None = None,
		on_activity: ActivityCallback | None = None,
		on_result: Callable[[FileSearchResult], None] | None = None,
		cancel_check: Callable[[], bool] | None = None,
		allow_process_pool: bool = False,
	) -> tuple[list[FileSearchResult], list[SkippedFile]]:
		return execute_search(
			args,
			skipped_files=skipped_files,
			on_progress=on_progress,
			on_activity=on_activity,
			on_result=on_result,
			cancel_check=cancel_check,
			allow_process_pool=allow_process_pool,
		)
