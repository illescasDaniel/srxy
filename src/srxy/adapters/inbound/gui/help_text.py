"""Help copy for GUI search options and filters."""

from __future__ import annotations

from srxy.application.install_method import (
	ffmpeg_enable_hint,
	ocr_enable_hint,
	semantic_enable_hint,
)
from srxy.i18n import tr


_HELP_KEYS = {
	"search_names": "gui.help.search_names",
	"search_contents": "gui.help.search_contents",
	"search_docs_tags": "gui.help.search_docs_tags",
	"semantic": "gui.help.semantic",
	"ocr": "gui.help.ocr",
	"transcribe": "gui.help.transcribe",
	"semantic_image": "gui.help.semantic_image",
	"include_hidden": "gui.help.include_hidden",
	"include_noise": "gui.help.include_noise",
	"include_noise_files": "gui.help.include_noise_files",
	"match_skipped_names": "gui.help.match_skipped_names",
	"include_archives": "gui.help.include_archives",
	"include_subdirectories": "gui.help.include_subdirectories",
	"top_files": "gui.help.top_files",
	"max_matches": "gui.help.max_matches",
	"threshold": "gui.help.threshold",
	"semantic_image_threshold": "gui.help.semantic_image_threshold",
	"transcribe_threshold": "gui.help.transcribe_threshold",
	"text_mib": "gui.help.text_mib",
	"ocr_mib": "gui.help.ocr_mib",
	"transcribe_mib": "gui.help.transcribe_mib",
}


def help_text(key: str) -> str:
	catalog_key = _HELP_KEYS.get(key)
	if catalog_key is None:
		return tr("help.not_available")
	if key == "semantic":
		return tr(catalog_key, semantic_hint=semantic_enable_hint())
	if key == "ocr":
		return tr(catalog_key, ocr_hint=ocr_enable_hint())
	if key in {"transcribe", "semantic_image"}:
		return tr(
			catalog_key,
			semantic_hint=semantic_enable_hint(),
			ffmpeg_hint=ffmpeg_enable_hint(),
		)
	return tr(catalog_key)


__all__ = [
	"help_text",
]
