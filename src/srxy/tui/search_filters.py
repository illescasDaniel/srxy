from __future__ import annotations

import argparse
from dataclasses import dataclass

from srxy.tui.size_limits import (
	SizeLimits,
	apply_size_limits_to_args,
	size_limits_from_args,
	validate_size_limits,
)


@dataclass(frozen=True, slots=True)
class SearchFilters:
	top_files: str
	max_matches: str
	size_limits: SizeLimits


def search_filters_from_args(args: argparse.Namespace) -> SearchFilters:
	top_files = "" if args.limit is None else str(args.limit)
	return SearchFilters(
		top_files=top_files,
		max_matches=str(args.max_matches),
		size_limits=size_limits_from_args(args),
	)


def apply_search_filters_to_args(args: argparse.Namespace, filters: SearchFilters):
	limit, max_matches = parse_search_filter_limits(filters)
	args.limit = limit
	args.max_matches = max_matches
	apply_size_limits_to_args(args, filters.size_limits)


def format_search_filters_summary(filters: SearchFilters) -> str:
	top = filters.top_files.strip()
	if top:
		files_label = f"Top {top}"
	else:
		files_label = "All files"
	per_file = filters.max_matches.strip() or "50"
	text_mib = filters.size_limits.text_mib.strip() or "100"
	return f"{files_label} · {per_file}/file · text {text_mib} MiB"


def _parse_optional_positive_int(raw: str, *, field_name: str) -> int | None:
	text = raw.strip()
	if not text:
		return None
	try:
		value = int(text)
	except ValueError as error:
		raise ValueError(f"{field_name} must be a positive integer") from error
	if value < 1:
		raise ValueError(f"{field_name} must be at least 1")
	return value


def parse_search_filter_limits(filters: SearchFilters) -> tuple[int | None, int]:
	limit = (
		_parse_optional_positive_int(filters.top_files, field_name="Top files") if filters.top_files.strip() else None
	)
	max_matches = _parse_optional_positive_int(filters.max_matches, field_name="Matches per file") or 50
	return limit, max_matches


def validate_search_filters(filters: SearchFilters):
	parse_search_filter_limits(filters)
	validate_size_limits(filters.size_limits)
