from __future__ import annotations

import argparse
from dataclasses import dataclass


def search_source_required_message() -> str:
	from srxy.i18n import tr

	return tr("error.search_source_required")


@dataclass(frozen=True, slots=True)
class SearchOptions:
	search_names: bool = True
	search_contents: bool = True
	search_docs_tags: bool = True
	semantic: bool = False
	semantic_image: bool = False
	ocr: bool = False
	transcribe: bool = False
	include_hidden: bool = False
	include_noise: bool = False
	include_noise_files: bool = False
	match_skipped_names: bool = False
	include_archives: bool = False
	include_subdirectories: bool = True


def content_match_sources_enabled(options: SearchOptions) -> bool:
	return bool(options.search_docs_tags or options.ocr or options.transcribe or options.semantic_image)


def has_search_source(options: SearchOptions) -> bool:
	if options.search_names:
		return True
	return bool(options.search_contents and content_match_sources_enabled(options))


def effective_search_options(options: SearchOptions) -> SearchOptions:
	"""Return options with inactive flags cleared for summary / effective run state.

	Preferred ticks are kept in the stored ``SearchOptions`` for UI round-trips;
	use this when summarizing or reasoning about what will actually run.
	"""
	match_skipped_names = bool(options.match_skipped_names and options.search_names)
	if options.search_contents and match_skipped_names == options.match_skipped_names:
		return options
	if options.search_contents:
		return SearchOptions(
			search_names=options.search_names,
			search_contents=True,
			search_docs_tags=options.search_docs_tags,
			semantic=options.semantic,
			semantic_image=options.semantic_image,
			ocr=options.ocr,
			transcribe=options.transcribe,
			include_hidden=options.include_hidden,
			include_noise=options.include_noise,
			include_noise_files=options.include_noise_files,
			match_skipped_names=match_skipped_names,
			include_archives=options.include_archives,
			include_subdirectories=options.include_subdirectories,
		)
	return SearchOptions(
		search_names=options.search_names,
		search_contents=False,
		search_docs_tags=False,
		semantic=options.semantic,
		semantic_image=False,
		ocr=False,
		transcribe=False,
		include_hidden=options.include_hidden,
		include_noise=options.include_noise,
		include_noise_files=options.include_noise_files,
		match_skipped_names=match_skipped_names,
		include_archives=options.include_archives,
		include_subdirectories=options.include_subdirectories,
	)


# Back-compat alias for older imports.
normalize_content_dependent_options = effective_search_options


def search_options_from_args(args: argparse.Namespace) -> SearchOptions:
	search_names, search_contents = _resolve_search_modes(args)
	raw_docs = getattr(args, "search_docs_tags", None)
	search_docs_tags = True if raw_docs is None else bool(raw_docs)
	return SearchOptions(
		search_names=search_names,
		search_contents=search_contents,
		search_docs_tags=search_docs_tags,
		semantic=bool(args.semantic or args.semantic_all),
		semantic_image=bool(args.semantic_image or args.semantic_all),
		ocr=bool(args.ocr or args.semantic_all),
		transcribe=bool(args.transcribe or args.semantic_all),
		include_hidden=bool(args.include_hidden),
		include_noise=bool(args.include_noise),
		include_noise_files=bool(getattr(args, "include_noise_files", False)),
		match_skipped_names=bool(getattr(args, "match_skipped_names", False)),
		include_archives=bool(getattr(args, "include_archives", False)),
		include_subdirectories=bool(getattr(args, "include_subdirectories", True)),
	)


def sync_options_to_args(
	args: argparse.Namespace,
	*,
	search_names: bool,
	search_contents: bool,
	search_docs_tags: bool = True,
	semantic: bool,
	semantic_image: bool,
	ocr: bool,
	transcribe: bool,
	include_hidden: bool,
	include_noise: bool,
	include_noise_files: bool = False,
	match_skipped_names: bool = False,
	include_archives: bool,
	include_subdirectories: bool = True,
):
	args.names_only = search_names and not search_contents
	args.content_only = search_contents and not search_names
	args.search_names = search_names
	args.search_contents = search_contents
	args.search_docs_tags = search_docs_tags
	args.semantic = semantic
	args.semantic_image = semantic_image
	args.semantic_all = False
	args.ocr = ocr
	args.transcribe = transcribe
	args.include_hidden = include_hidden
	args.include_noise = include_noise
	args.include_noise_files = include_noise_files
	args.match_skipped_names = match_skipped_names
	args.include_archives = include_archives
	args.include_subdirectories = include_subdirectories


def apply_search_options_to_args(args: argparse.Namespace, options: SearchOptions):
	sync_options_to_args(
		args,
		search_names=options.search_names,
		search_contents=options.search_contents,
		search_docs_tags=options.search_docs_tags,
		semantic=options.semantic,
		semantic_image=options.semantic_image,
		ocr=options.ocr,
		transcribe=options.transcribe,
		include_hidden=options.include_hidden,
		include_noise=options.include_noise,
		include_noise_files=options.include_noise_files,
		match_skipped_names=options.match_skipped_names,
		include_archives=options.include_archives,
		include_subdirectories=options.include_subdirectories,
	)


def format_search_options_summary(options: SearchOptions) -> str:
	from srxy.i18n import tr

	effective = effective_search_options(options)
	segments: list[str] = []

	where_labels: list[str] = []
	if effective.search_names:
		where_labels.append(tr("summary.where.names"))
	if effective.search_contents:
		where_labels.append(tr("summary.where.content"))
	if where_labels:
		segments.append(f"{tr('summary.prefix.where')}: {', '.join(where_labels)}")

	how_labels: list[str] = []
	if effective.search_docs_tags:
		how_labels.append(tr("summary.how.docs_tags"))
	if effective.semantic:
		how_labels.append(tr("summary.how.semantic"))
	if effective.ocr:
		how_labels.append(tr("summary.how.ocr"))
	if effective.transcribe:
		how_labels.append(tr("summary.how.transcribe"))
	if effective.semantic_image:
		how_labels.append(tr("summary.how.semantic_image"))
	if how_labels:
		segments.append(f"{tr('summary.prefix.how')}: {', '.join(how_labels)}")

	scan_labels: list[str] = []
	if not effective.include_subdirectories:
		scan_labels.append(tr("summary.scan.top_level"))
	if effective.include_hidden:
		scan_labels.append(tr("summary.scan.hidden"))
	if effective.include_noise:
		scan_labels.append(tr("summary.scan.noise"))
	if effective.include_noise_files:
		scan_labels.append(tr("summary.scan.noise_files"))
	if effective.match_skipped_names:
		scan_labels.append(tr("summary.scan.skipped_names"))
	if effective.include_archives:
		scan_labels.append(tr("summary.scan.archives"))
	if scan_labels:
		segments.append(f"{tr('summary.prefix.scan')}: {', '.join(scan_labels)}")

	if not segments:
		return tr("summary.none")
	return " · ".join(segments)


def _resolve_search_modes(args: argparse.Namespace) -> tuple[bool, bool]:
	if args.names_only:
		return True, False
	if args.content_only:
		return False, True
	search_names = True if args.search_names is None else args.search_names
	search_contents = True if args.search_contents is None else args.search_contents
	return search_names, search_contents
