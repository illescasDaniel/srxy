from __future__ import annotations

from srxy.application.search_defaults import (
	DEFAULT_SEMANTIC_IMAGE_THRESHOLD,
	DEFAULT_TRANSCRIBE_THRESHOLD,
)
from srxy.application.search_formatting import match_labels
from srxy.domain.models import FileSearchResult
from srxy.i18n import tr


_OPTION_KEYS: dict[str, tuple[str, str]] = {
	"so-names": ("gui.options.file_names", "tui.hint.file_names"),
	"so-content": ("gui.options.file_contents", "tui.hint.file_contents"),
	"so-docs-tags": ("tui.options.docs_tags", "tui.hint.docs_tags"),
	"so-semantic": ("gui.options.semantic", "tui.hint.semantic"),
	"so-ocr": ("gui.options.ocr", "tui.hint.ocr"),
	"so-transcribe": ("gui.options.transcribe", "tui.hint.transcribe"),
	"so-semantic-image": ("gui.options.semantic_image", "tui.hint.semantic_image"),
	"so-enable-all": ("tui.options.enable_all", "tui.hint.enable_all"),
	"so-hidden": ("gui.options.hidden", "tui.hint.hidden"),
	"so-noise": ("gui.options.noise", "tui.hint.noise"),
	"so-noise-files": ("gui.options.noise_files", "tui.hint.noise_files"),
	"so-match-skipped-names": ("gui.options.match_skipped", "tui.hint.match_skipped_names"),
	"so-archives": ("gui.options.archives", "tui.hint.archives"),
	"so-subdirs": ("gui.options.subdirs", "tui.hint.subdirs"),
}

_MATCH_SOURCE_KEYS = {
	"name": "tui.match.filename",
	"content": "tui.match.content",
	"ocr": "tui.match.image_text",
	"transcript": "tui.match.speech",
	"image semantic": "tui.match.visual",
	"tag": "tui.match.tags",
	"match": "tui.match.generic",
}


def option_label(checkbox_id: str) -> str:
	label_key, _hint_key = _OPTION_KEYS[checkbox_id]
	return tr(label_key)


def option_hint(checkbox_id: str) -> str | None:
	_label_key, hint_key = _OPTION_KEYS[checkbox_id]
	return tr(hint_key)


def classic_matching_hint() -> str:
	return tr("tui.hint.classic")


def binary_skip_hint() -> str:
	return tr("tui.hint.binary_skip")


def search_options_section_where() -> str:
	return tr("tui.section.where")


def search_options_section_how() -> str:
	return tr("tui.section.how")


def search_options_section_scan() -> str:
	return tr("tui.section.scan")


def search_options_subsection_noisy() -> str:
	return tr("tui.section.noisy")


def query_add_term() -> str:
	return tr("gui.add_term")


def query_term_placeholder() -> str:
	return tr("gui.term_placeholder")


def query_advanced_placeholder() -> str:
	return tr("gui.advanced_placeholder")


def format_tui_match_labels(
	result: FileSearchResult,
	*,
	threshold: float = 0.35,
	semantic_image_threshold: float = DEFAULT_SEMANTIC_IMAGE_THRESHOLD,
	transcribe_threshold: float = DEFAULT_TRANSCRIBE_THRESHOLD,
) -> str:
	raw = match_labels(
		result,
		threshold=threshold,
		semantic_image_threshold=semantic_image_threshold,
		transcribe_threshold=transcribe_threshold,
	)
	if not raw:
		return tr("tui.match.generic")
	parts = [part.strip() for part in raw.split(",")]
	return ", ".join(tr(_MATCH_SOURCE_KEYS.get(part, part)) for part in parts)


__all__ = [
	"binary_skip_hint",
	"classic_matching_hint",
	"format_tui_match_labels",
	"option_hint",
	"option_label",
	"query_add_term",
	"query_advanced_placeholder",
	"query_term_placeholder",
	"search_options_section_how",
	"search_options_section_scan",
	"search_options_section_where",
	"search_options_subsection_noisy",
]
