"""Shared UI copy for search options/filters summaries (UI-agnostic)."""

from __future__ import annotations


SUMMARY_WHERE_NAMES = "Names"
SUMMARY_WHERE_CONTENT = "Content"
SUMMARY_HOW_DOCS_TAGS = "Docs & tags"
SUMMARY_HOW_SEMANTIC = "Meaning"
SUMMARY_HOW_OCR = "Image text"
SUMMARY_HOW_TRANSCRIBE = "Speech"
SUMMARY_HOW_SEMANTIC_IMAGE = "Visual"
SUMMARY_SCAN_HIDDEN = "Hidden"
SUMMARY_SCAN_NOISE = "Cache dirs"
SUMMARY_SCAN_NOISE_FILES = "Junk files"
SUMMARY_SCAN_SKIPPED_NAMES = "Skipped names"
SUMMARY_SCAN_ARCHIVES = "Archives"
SUMMARY_SCAN_TOP_LEVEL = "This folder only"

RESULTS_EMPTY_BEFORE_SEARCH = "Run a search to see matching files"
RESULTS_EMPTY_SEARCHING = "Searching…"
RESULTS_EMPTY_NO_MATCHES = "No matching files"

SUMMARY_PREFIX_WHERE = "Where"
SUMMARY_PREFIX_HOW = "How"
SUMMARY_PREFIX_SCAN = "Scan"

# Back-compat alias from when docs/tags lived under Where/How as SUMMARY_HOW_CONTENT.
SUMMARY_HOW_CONTENT = SUMMARY_HOW_DOCS_TAGS

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
