"""Easy-to-read help copy for installer options (same tone as the main GUI)."""

from __future__ import annotations

from srxy.i18n import tr


_HELP_KEYS = {
	"tesseract": "installer.help.tesseract",
	"ffmpeg": "installer.help.ffmpeg",
	"semantic": "installer.help.semantic",
	"models": "installer.help.models",
	"path": "installer.help.path",
	"no_gpu": "installer.help.no_gpu",
}


def help_text(key: str) -> str:
	catalog_key = _HELP_KEYS.get(key)
	if catalog_key is None:
		return tr("help.option_title")
	return tr(catalog_key)


__all__ = ["help_text"]
