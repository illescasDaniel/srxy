from __future__ import annotations

import argparse
from dataclasses import dataclass

from srxy.application.labels import (
	SUMMARY_HOW_OCR,
	SUMMARY_HOW_SEMANTIC,
	SUMMARY_HOW_SEMANTIC_IMAGE,
	SUMMARY_HOW_TRANSCRIBE,
	SUMMARY_PREFIX_HOW,
	SUMMARY_PREFIX_SCAN,
	SUMMARY_PREFIX_WHERE,
	SUMMARY_SCAN_ARCHIVES,
	SUMMARY_SCAN_HIDDEN,
	SUMMARY_SCAN_NOISE,
	SUMMARY_SCAN_TOP_LEVEL,
	SUMMARY_WHERE_CONTENT,
	SUMMARY_WHERE_NAMES,
)


@dataclass(frozen=True, slots=True)
class SearchOptions:
	search_names: bool = True
	search_contents: bool = True
	semantic: bool = False
	semantic_image: bool = False
	ocr: bool = False
	transcribe: bool = False
	include_hidden: bool = False
	include_noise: bool = False
	include_archives: bool = False
	include_subdirectories: bool = True


def search_options_from_args(args: argparse.Namespace) -> SearchOptions:
	search_names, search_contents = _resolve_search_modes(args)
	return SearchOptions(
		search_names=search_names,
		search_contents=search_contents,
		semantic=bool(args.semantic or args.semantic_all),
		semantic_image=bool(args.semantic_image or args.semantic_all),
		ocr=bool(args.ocr or args.semantic_all),
		transcribe=bool(args.transcribe or args.semantic_all),
		include_hidden=bool(args.include_hidden),
		include_noise=bool(args.include_noise),
		include_archives=bool(getattr(args, "include_archives", False)),
		include_subdirectories=bool(getattr(args, "include_subdirectories", True)),
	)


def sync_options_to_args(
	args: argparse.Namespace,
	*,
	search_names: bool,
	search_contents: bool,
	semantic: bool,
	semantic_image: bool,
	ocr: bool,
	transcribe: bool,
	include_hidden: bool,
	include_noise: bool,
	include_archives: bool,
	include_subdirectories: bool = True,
):
	args.names_only = search_names and not search_contents
	args.content_only = search_contents and not search_names
	args.search_names = search_names
	args.search_contents = search_contents
	args.semantic = semantic
	args.semantic_image = semantic_image
	args.semantic_all = False
	args.ocr = ocr
	args.transcribe = transcribe
	args.include_hidden = include_hidden
	args.include_noise = include_noise
	args.include_archives = include_archives
	args.include_subdirectories = include_subdirectories


def apply_search_options_to_args(args: argparse.Namespace, options: SearchOptions):
	sync_options_to_args(
		args,
		search_names=options.search_names,
		search_contents=options.search_contents,
		semantic=options.semantic,
		semantic_image=options.semantic_image,
		ocr=options.ocr,
		transcribe=options.transcribe,
		include_hidden=options.include_hidden,
		include_noise=options.include_noise,
		include_archives=options.include_archives,
		include_subdirectories=options.include_subdirectories,
	)


def format_search_options_summary(options: SearchOptions) -> str:
	segments: list[str] = []

	where_labels: list[str] = []
	if options.search_names:
		where_labels.append(SUMMARY_WHERE_NAMES)
	if options.search_contents:
		where_labels.append(SUMMARY_WHERE_CONTENT)
	if where_labels:
		segments.append(f"{SUMMARY_PREFIX_WHERE}: {', '.join(where_labels)}")

	how_labels: list[str] = []
	if options.semantic:
		how_labels.append(SUMMARY_HOW_SEMANTIC)
	if options.ocr:
		how_labels.append(SUMMARY_HOW_OCR)
	if options.transcribe:
		how_labels.append(SUMMARY_HOW_TRANSCRIBE)
	if options.semantic_image:
		how_labels.append(SUMMARY_HOW_SEMANTIC_IMAGE)
	if how_labels:
		segments.append(f"{SUMMARY_PREFIX_HOW}: {', '.join(how_labels)}")

	scan_labels: list[str] = []
	if not options.include_subdirectories:
		scan_labels.append(SUMMARY_SCAN_TOP_LEVEL)
	if options.include_hidden:
		scan_labels.append(SUMMARY_SCAN_HIDDEN)
	if options.include_noise:
		scan_labels.append(SUMMARY_SCAN_NOISE)
	if options.include_archives:
		scan_labels.append(SUMMARY_SCAN_ARCHIVES)
	if scan_labels:
		segments.append(f"{SUMMARY_PREFIX_SCAN}: {', '.join(scan_labels)}")

	if not segments:
		return "None enabled"
	text = " · ".join(segments)
	if len(text) > 72:
		return f"{text[:69]}…"
	return text


def _resolve_search_modes(args: argparse.Namespace) -> tuple[bool, bool]:
	if args.names_only:
		return True, False
	if args.content_only:
		return False, True
	search_names = True if args.search_names is None else args.search_names
	search_contents = True if args.search_contents is None else args.search_contents
	return search_names, search_contents
