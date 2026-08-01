from __future__ import annotations

from srxy.adapters.outbound.semantic.semantic_image import DEFAULT_SEMANTIC_IMAGE_THRESHOLD
from srxy.adapters.outbound.transcribe.transcribe_text import DEFAULT_TRANSCRIBE_THRESHOLD
from srxy.application.labels import (
	FILTER_LABEL_AUDIO_VIDEO_SIZE,
	FILTER_LABEL_DOCUMENT_SIZE,
	FILTER_LABEL_HITS_PER_FILE,
	FILTER_LABEL_IMAGE_TEXT_SIZE,
	FILTER_LABEL_MAX_RESULTS,
	FILTER_LABEL_MIN_MATCH,
	FILTER_LABEL_SPEECH_MIN,
	FILTER_LABEL_VISUAL_MIN,
	FILTER_SECTION_LIMITS,
	FILTER_SECTION_SENSITIVITY,
	SUMMARY_HOW_CONTENT,
	SUMMARY_HOW_DOCS_TAGS,
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
from srxy.domain.models import FileSearchResult


# Search options modal: checkbox id -> (label, optional hint)
OPTION_LABELS: dict[str, tuple[str, str | None]] = {
	"so-names": ("File names", "Match the path and filename"),
	"so-content": ("File contents", "Search inside files (docs, images, audio, …)"),
	"so-docs-tags": (
		"Docs, tags & metadata (recommended ON)",
		"Text inside documents, tags, and metadata",
	),
	"so-semantic": ("Similar meaning", "Find related words, not just exact spelling"),
	"so-ocr": ("Text in images", "Read text in photos, scans, and PDF pages"),
	"so-transcribe": ("Spoken words", "Search speech in audio and video"),
	"so-semantic-image": ("Visual description", "Match what an image looks like (CLIP)"),
	"so-enable-all": ("All advanced matching", "Turn on Similar meaning, Text in images, Spoken words, and Visual"),
	"so-hidden": ("Hidden files & folders", "Include dotfiles and hidden directories"),
	"so-noise": ("Cache & vendor folders", "Include __pycache__, node_modules, etc."),
	"so-archives": ("Inside zip/tar files", "Search within compressed archives"),
	"so-subdirs": ("Include subdirectories", "Also search folders nested under the path"),
}

CLASSIC_MATCHING_HINT = "Fuzzy, phonetic, and substring matching (always on)"

SEARCH_OPTIONS_SECTION_WHERE = "Where to search"
SEARCH_OPTIONS_SECTION_HOW = "How to match"
SEARCH_OPTIONS_SECTION_SCAN = "Which files to scan"

MATCH_SOURCE_LABELS: dict[str, str] = {
	"name": "filename",
	"content": "content",
	"ocr": "image text",
	"transcript": "speech",
	"image semantic": "visual",
	"tag": "tags",
	"match": "match",
}

QUERY_ADD_TERM = "Add term"
QUERY_TERM_PLACEHOLDER = "Type a word or phrase"
QUERY_ADVANCED_PLACEHOLDER = "e.g. revenue | amphibian & person"

__all__ = [
	"CLASSIC_MATCHING_HINT",
	"FILTER_LABEL_AUDIO_VIDEO_SIZE",
	"FILTER_LABEL_DOCUMENT_SIZE",
	"FILTER_LABEL_HITS_PER_FILE",
	"FILTER_LABEL_IMAGE_TEXT_SIZE",
	"FILTER_LABEL_MAX_RESULTS",
	"FILTER_LABEL_MIN_MATCH",
	"FILTER_LABEL_SPEECH_MIN",
	"FILTER_LABEL_VISUAL_MIN",
	"FILTER_SECTION_LIMITS",
	"FILTER_SECTION_SENSITIVITY",
	"MATCH_SOURCE_LABELS",
	"OPTION_LABELS",
	"QUERY_ADD_TERM",
	"QUERY_ADVANCED_PLACEHOLDER",
	"QUERY_TERM_PLACEHOLDER",
	"SEARCH_OPTIONS_SECTION_HOW",
	"SEARCH_OPTIONS_SECTION_SCAN",
	"SEARCH_OPTIONS_SECTION_WHERE",
	"SUMMARY_HOW_CONTENT",
	"SUMMARY_HOW_DOCS_TAGS",
	"SUMMARY_HOW_OCR",
	"SUMMARY_HOW_SEMANTIC",
	"SUMMARY_HOW_SEMANTIC_IMAGE",
	"SUMMARY_HOW_TRANSCRIBE",
	"SUMMARY_PREFIX_HOW",
	"SUMMARY_PREFIX_SCAN",
	"SUMMARY_PREFIX_WHERE",
	"SUMMARY_SCAN_ARCHIVES",
	"SUMMARY_SCAN_HIDDEN",
	"SUMMARY_SCAN_NOISE",
	"SUMMARY_SCAN_TOP_LEVEL",
	"SUMMARY_WHERE_CONTENT",
	"SUMMARY_WHERE_NAMES",
	"format_tui_match_labels",
	"option_hint",
	"option_label",
]


def option_label(checkbox_id: str) -> str:
	return OPTION_LABELS[checkbox_id][0]


def option_hint(checkbox_id: str) -> str | None:
	return OPTION_LABELS[checkbox_id][1]


def format_tui_match_labels(
	result: FileSearchResult,
	*,
	threshold: float = 0.35,
	semantic_image_threshold: float = DEFAULT_SEMANTIC_IMAGE_THRESHOLD,
	transcribe_threshold: float = DEFAULT_TRANSCRIBE_THRESHOLD,
) -> str:
	from srxy.adapters.inbound.cli.cli import match_labels

	raw = match_labels(
		result,
		threshold=threshold,
		semantic_image_threshold=semantic_image_threshold,
		transcribe_threshold=transcribe_threshold,
	)
	if not raw:
		return MATCH_SOURCE_LABELS["match"]
	parts = [part.strip() for part in raw.split(",")]
	return ", ".join(MATCH_SOURCE_LABELS.get(part, part) for part in parts)
