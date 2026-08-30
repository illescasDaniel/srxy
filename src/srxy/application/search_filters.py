from __future__ import annotations

import argparse
from dataclasses import dataclass

from srxy.application.labels import (
	filter_label_hits_per_file,
	filter_label_max_results,
	filter_label_min_match,
	filter_label_speech_min,
	filter_label_visual_min,
)
from srxy.application.search_defaults import (
	DEFAULT_MAX_FILE_SIZE,
	DEFAULT_OCR_MAX_FILE_SIZE,
	DEFAULT_SEMANTIC_IMAGE_THRESHOLD,
	DEFAULT_TRANSCRIBE_MAX_FILE_SIZE,
	DEFAULT_TRANSCRIBE_THRESHOLD,
)
from srxy.application.size_limits import (
	SizeLimits,
	apply_size_limits_to_args,
	bytes_to_mib_text,
	size_limits_from_args,
	validate_size_limits,
)


_DEFAULT_THRESHOLD = 0.35
GUI_DEFAULT_RESULT_LIMIT = 5000


@dataclass(frozen=True, slots=True)
class SearchFilters:
	top_files: str
	max_matches: str
	size_limits: SizeLimits
	threshold: str
	semantic_image_threshold: str
	transcribe_threshold: str


def _percent_text(value: float) -> str:
	return str(round(value * 100))


def default_search_filters() -> SearchFilters:
	"""Factory defaults for filters dialog Reset (empty top_files = all / GUI limit)."""
	return SearchFilters(
		top_files="",
		max_matches="50",
		size_limits=SizeLimits(
			text_mib=bytes_to_mib_text(DEFAULT_MAX_FILE_SIZE, allow_zero=True),
			ocr_mib=bytes_to_mib_text(DEFAULT_OCR_MAX_FILE_SIZE),
			transcribe_mib=bytes_to_mib_text(DEFAULT_TRANSCRIBE_MAX_FILE_SIZE),
		),
		threshold=_percent_text(_DEFAULT_THRESHOLD),
		semantic_image_threshold=_percent_text(DEFAULT_SEMANTIC_IMAGE_THRESHOLD),
		transcribe_threshold=_percent_text(DEFAULT_TRANSCRIBE_THRESHOLD),
	)


def search_filters_from_args(args: argparse.Namespace) -> SearchFilters:
	top_files = "" if args.limit is None else str(args.limit)
	return SearchFilters(
		top_files=top_files,
		max_matches=str(args.max_matches),
		size_limits=size_limits_from_args(args),
		threshold=_percent_text(args.threshold),
		semantic_image_threshold=_percent_text(args.semantic_image_threshold),
		transcribe_threshold=_percent_text(args.transcribe_threshold),
	)


def apply_search_filters_to_args(args: argparse.Namespace, filters: SearchFilters):
	limit, max_matches = parse_search_filter_limits(filters)
	threshold, semantic_image_threshold, transcribe_threshold = parse_search_filter_thresholds(filters)
	args.limit = limit
	args.max_matches = max_matches
	args.threshold = threshold
	args.semantic_image_threshold = semantic_image_threshold
	args.transcribe_threshold = transcribe_threshold
	apply_size_limits_to_args(args, filters.size_limits)


def format_search_filters_summary(filters: SearchFilters) -> str:
	from srxy.i18n import tr

	top = filters.top_files.strip()
	if top:
		files_label = tr("filters.summary.top", n=top)
	else:
		files_label = tr("filters.summary.all_files")
	per_file = filters.max_matches.strip() or "50"
	text_mib = filters.size_limits.text_mib.strip() or "100"
	match_threshold = filters.threshold.strip() or _percent_text(_DEFAULT_THRESHOLD)
	return tr(
		"filters.summary.body",
		files=files_label,
		per_file=per_file,
		text_mib=text_mib,
		match=match_threshold,
		image=filters.semantic_image_threshold.strip() or _percent_text(DEFAULT_SEMANTIC_IMAGE_THRESHOLD),
		transcript=filters.transcribe_threshold.strip() or _percent_text(DEFAULT_TRANSCRIBE_THRESHOLD),
	)


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


def _parse_threshold_percent(raw: str, *, field_name: str) -> float:
	text = raw.strip()
	if not text:
		raise ValueError(f"{field_name} is required")
	try:
		value = float(text)
	except ValueError as error:
		raise ValueError(f"{field_name} must be a number between 0 and 100") from error
	if value < 0.0 or value > 100.0:
		raise ValueError(f"{field_name} must be between 0 and 100")
	return value / 100.0


def parse_search_filter_limits(filters: SearchFilters) -> tuple[int | None, int]:
	limit = (
		_parse_optional_positive_int(filters.top_files, field_name=filter_label_max_results())
		if filters.top_files.strip()
		else None
	)
	max_matches = _parse_optional_positive_int(filters.max_matches, field_name=filter_label_hits_per_file()) or 50
	return limit, max_matches


def parse_search_filter_thresholds(filters: SearchFilters) -> tuple[float, float, float]:
	threshold = _parse_threshold_percent(
		filters.threshold or _percent_text(_DEFAULT_THRESHOLD),
		field_name=filter_label_min_match(),
	)
	semantic_image_threshold = _parse_threshold_percent(
		filters.semantic_image_threshold or _percent_text(DEFAULT_SEMANTIC_IMAGE_THRESHOLD),
		field_name=filter_label_visual_min(),
	)
	transcribe_threshold = _parse_threshold_percent(
		filters.transcribe_threshold or _percent_text(DEFAULT_TRANSCRIBE_THRESHOLD),
		field_name=filter_label_speech_min(),
	)
	return threshold, semantic_image_threshold, transcribe_threshold


def validate_search_filters(filters: SearchFilters):
	parse_search_filter_limits(filters)
	parse_search_filter_thresholds(filters)
	validate_size_limits(filters.size_limits)
