from __future__ import annotations

from srxy.models import FileSearchResult
from srxy.semantic_image import DEFAULT_SEMANTIC_IMAGE_THRESHOLD
from srxy.transcribe_text import DEFAULT_TRANSCRIBE_THRESHOLD


# Search options modal: checkbox id -> (label, optional hint)
OPTION_LABELS: dict[str, tuple[str, str | None]] = {
	"so-names": ("File names", "Match the path and filename"),
	"so-content": ("File contents", "Text inside documents, tags, and metadata"),
	"so-semantic": ("Similar meaning", "Find related words, not just exact spelling"),
	"so-ocr": ("Text in images", "Read text in photos, scans, and PDF pages"),
	"so-transcribe": ("Spoken words", "Search speech in audio and video"),
	"so-semantic-image": ("Visual description", "Match what an image looks like (CLIP)"),
	"so-enable-all": ("All advanced matching", "Turn on all four options above"),
	"so-hidden": ("Hidden files & folders", "Include dotfiles and hidden directories"),
	"so-noise": ("Cache & vendor folders", "Include __pycache__, node_modules, etc."),
	"so-archives": ("Inside zip/tar files", "Search within compressed archives"),
}

CLASSIC_MATCHING_HINT = "Fuzzy, phonetic, and substring matching (always on)"

SEARCH_OPTIONS_SECTION_WHERE = "Where to search"
SEARCH_OPTIONS_SECTION_HOW = "How to match"
SEARCH_OPTIONS_SECTION_SCAN = "Which files to scan"

SUMMARY_WHERE_NAMES = "Names"
SUMMARY_WHERE_CONTENT = "Content"
SUMMARY_HOW_SEMANTIC = "Meaning"
SUMMARY_HOW_OCR = "Image text"
SUMMARY_HOW_TRANSCRIBE = "Speech"
SUMMARY_HOW_SEMANTIC_IMAGE = "Visual"
SUMMARY_SCAN_HIDDEN = "Hidden"
SUMMARY_SCAN_NOISE = "Cache dirs"
SUMMARY_SCAN_ARCHIVES = "Archives"

SUMMARY_PREFIX_WHERE = "Where"
SUMMARY_PREFIX_HOW = "How"
SUMMARY_PREFIX_SCAN = "Scan"

MATCH_SOURCE_LABELS: dict[str, str] = {
	"name": "filename",
	"content": "content",
	"ocr": "image text",
	"transcript": "speech",
	"image semantic": "visual",
	"tag": "tags",
	"match": "match",
}

FILTER_SECTION_LIMITS = "Limits"
FILTER_SECTION_SENSITIVITY = "Sensitivity"

FILTER_LABEL_MAX_RESULTS = "Max results (empty = no limit)"
FILTER_LABEL_HITS_PER_FILE = "Hits shown per file"
FILTER_LABEL_DOCUMENT_SIZE = "Document size limit (MiB, 0 = unlimited)"
FILTER_LABEL_IMAGE_TEXT_SIZE = "Image text size limit (MiB)"
FILTER_LABEL_AUDIO_VIDEO_SIZE = "Audio/video size limit (MiB)"
FILTER_LABEL_MIN_MATCH = "Minimum match %"
FILTER_LABEL_VISUAL_MIN = "Visual match minimum %"
FILTER_LABEL_SPEECH_MIN = "Speech match minimum %"

QUERY_ADD_TERM = "Add term"
QUERY_TERM_PLACEHOLDER = "Type a word or phrase"
QUERY_ADVANCED_PLACEHOLDER = "e.g. revenue | amphibian & person"


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
	from srxy.cli import match_labels

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
