"""Shared UI copy for search options/filters summaries (UI-agnostic)."""

from __future__ import annotations

from srxy.i18n import tr


def results_empty_before_search() -> str:
	return tr("results.empty.before")


def results_empty_searching() -> str:
	return tr("results.empty.searching")


def results_empty_no_matches() -> str:
	return tr("results.empty.none")


def filter_label_max_results() -> str:
	return tr("filters.label.max_results")


def filter_label_hits_per_file() -> str:
	return tr("filters.label.hits_per_file")


def filter_label_document_size() -> str:
	return tr("filters.label.document_size")


def filter_label_image_text_size() -> str:
	return tr("filters.label.image_text_size")


def filter_label_audio_video_size() -> str:
	return tr("filters.label.audio_video_size")


def filter_label_min_match() -> str:
	return tr("filters.label.min_match")


def filter_label_visual_min() -> str:
	return tr("filters.label.visual_min")


def filter_label_speech_min() -> str:
	return tr("filters.label.speech_min")


def filter_section_limits() -> str:
	return tr("filters.section.limits")


def filter_section_sensitivity() -> str:
	return tr("filters.section.sensitivity")
