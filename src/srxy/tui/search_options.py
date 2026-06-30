from __future__ import annotations

import argparse
from dataclasses import dataclass


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
	)


def apply_search_options_to_args(args: argparse.Namespace, options: SearchOptions):
	from srxy.cli import sync_options_to_args

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
	)


def format_search_options_summary(options: SearchOptions) -> str:
	labels: list[str] = []
	if options.search_names:
		labels.append("Names")
	if options.search_contents:
		labels.append("Content")
	if options.semantic:
		labels.append("Semantic")
	if options.semantic_image:
		labels.append("Image semantic")
	if options.ocr:
		labels.append("OCR")
	if options.transcribe:
		labels.append("Transcribe")
	if options.include_hidden:
		labels.append("Hidden")
	if options.include_noise:
		labels.append("Noise")
	if options.include_archives:
		labels.append("Archives")
	if not labels:
		return "None enabled"
	text = ", ".join(labels)
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
