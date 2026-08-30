"""Snapshot and kind helpers for the GUI Settings maintenance dialog."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from srxy.adapters.outbound.cache.cache import cache_db_path, cache_key_path
from srxy.adapters.outbound.models.model_store import (
	clear_all_models,
	clear_semantic_image_model,
	clear_semantic_text_model,
	clear_transcribe_model,
	is_model_installed,
	semantic_image_model_dir,
	semantic_text_model_dir,
	transcribe_faster_whisper_model_dir,
	transcribe_model_root,
	transcribe_transformers_model_dir,
)
from srxy.application.disk_usage import format_byte_size, path_size_bytes
from srxy.application.model_preflight import (
	PendingModelDownload,
	format_download_prompt,
	semantic_image_model_label,
	semantic_text_model_label,
	transcribe_model_download_info,
)
from srxy.i18n import tr


SETTINGS_MODEL_KINDS = ("semantic_text", "semantic_image", "transcribe", "all")


def _active_transcribe_dir() -> Path:
	_label, _hint, target = transcribe_model_download_info()
	return target


def _model_label(kind: str) -> str:
	if kind == "semantic_text":
		return semantic_text_model_label()
	if kind == "semantic_image":
		return semantic_image_model_label()
	if kind == "transcribe":
		label, _hint, _path = transcribe_model_download_info()
		return label
	if kind == "all":
		return tr("settings.model.all")
	raise ValueError(f"Unknown settings model kind: {kind!r}")


def _model_path(kind: str) -> Path:
	if kind == "semantic_text":
		return semantic_text_model_dir()
	if kind == "semantic_image":
		return semantic_image_model_dir()
	if kind == "transcribe":
		return transcribe_model_root()
	if kind == "all":
		from srxy.application.install_paths import models_root

		return models_root()
	raise ValueError(f"Unknown settings model kind: {kind!r}")


def _model_installed(kind: str) -> bool:
	if kind == "semantic_text":
		return is_model_installed(semantic_text_model_dir())
	if kind == "semantic_image":
		return is_model_installed(semantic_image_model_dir())
	if kind == "transcribe":
		return is_model_installed(_active_transcribe_dir())
	if kind == "all":
		return any(_model_installed(k) for k in ("semantic_text", "semantic_image", "transcribe"))
	raise ValueError(f"Unknown settings model kind: {kind!r}")


def _model_size_bytes(kind: str) -> int:
	if kind == "semantic_text":
		return path_size_bytes(semantic_text_model_dir())
	if kind == "semantic_image":
		return path_size_bytes(semantic_image_model_dir())
	if kind == "transcribe":
		# Include both backends under the shared root when present.
		root = transcribe_model_root()
		if root.is_dir():
			return path_size_bytes(root)
		return path_size_bytes(transcribe_faster_whisper_model_dir()) + path_size_bytes(
			transcribe_transformers_model_dir()
		)
	if kind == "all":
		return sum(_model_size_bytes(k) for k in ("semantic_text", "semantic_image", "transcribe"))
	raise ValueError(f"Unknown settings model kind: {kind!r}")


def _model_status_text(kind: str) -> str:
	installed = _model_installed(kind)
	if not installed:
		return tr("settings.status.not_installed")
	size = format_byte_size(_model_size_bytes(kind))
	return tr("settings.status.installed", size=size)


def _cache_size_bytes() -> int:
	return path_size_bytes(cache_db_path()) + path_size_bytes(cache_key_path())


def _cache_present() -> bool:
	return cache_db_path().exists() or cache_key_path().exists()


def build_settings_snapshot(*, busy: bool) -> dict[str, Any]:
	from srxy.application.settings import settings_file_present, settings_path

	models: list[dict[str, Any]] = []
	for kind in SETTINGS_MODEL_KINDS:
		installed = _model_installed(kind)
		models.append(
			{
				"kind": kind,
				"label": _model_label(kind),
				"installed": installed,
				"statusText": _model_status_text(kind),
				"path": str(_model_path(kind)),
			}
		)
	cache_present = _cache_present()
	cache_size = _cache_size_bytes()
	if cache_present:
		cache_status = tr("settings.status.present", size=format_byte_size(cache_size))
	else:
		cache_status = tr("settings.status.empty")
	prefs_present = settings_file_present()
	prefs_path = settings_path()
	if prefs_present:
		prefs_status = tr("settings.status.preferences_present")
	else:
		prefs_status = tr("settings.status.preferences_absent")
	return {
		"models": models,
		"cache": {
			"path": str(cache_db_path()),
			"present": cache_present,
			"statusText": cache_status,
			"pathLabel": tr("settings.cache.path", path=cache_db_path()),
		},
		"preferences": {
			"path": str(prefs_path),
			"present": prefs_present,
			"statusText": prefs_status,
			"pathLabel": tr("settings.preferences.path", path=prefs_path),
		},
		"busy": busy,
	}


def clear_model_kind(kind: str):
	if kind == "semantic_text":
		clear_semantic_text_model()
		return
	if kind == "semantic_image":
		clear_semantic_image_model()
		return
	if kind == "transcribe":
		clear_transcribe_model()
		return
	if kind == "all":
		clear_all_models()
		return
	raise ValueError(f"Unknown settings model kind: {kind!r}")


def pending_downloads_for_kind(kind: str) -> list[PendingModelDownload]:
	"""Build download queue entries (even when already installed — download wipes first)."""
	if kind == "all":
		items: list[PendingModelDownload] = []
		for single in ("semantic_text", "semantic_image", "transcribe"):
			items.extend(pending_downloads_for_kind(single))
		return items
	if kind == "semantic_text":
		label = semantic_text_model_label()
		return [
			PendingModelDownload(
				kind="semantic_text",
				label=label,
				prompt=format_download_prompt(label, semantic_text_model_dir()),
			)
		]
	if kind == "semantic_image":
		label = semantic_image_model_label()
		return [
			PendingModelDownload(
				kind="semantic_image",
				label=label,
				prompt=format_download_prompt(label, semantic_image_model_dir()),
			)
		]
	if kind == "transcribe":
		label, size_hint, target = transcribe_model_download_info()
		return [
			PendingModelDownload(
				kind="transcribe",
				label=label,
				prompt=format_download_prompt(label, target, size_hint=size_hint),
			)
		]
	raise ValueError(f"Unknown settings model kind: {kind!r}")


def clear_confirm_message(kind: str) -> str:
	if kind == "all":
		return tr("settings.confirm.clear_all_models")
	label = _model_label(kind)
	return tr("settings.confirm.clear_model", label=label, path=_model_path(kind))


def cache_clear_confirm_message() -> str:
	return tr("settings.confirm.clear_cache", path=cache_db_path())


def preferences_reset_confirm_message() -> str:
	from srxy.application.settings import settings_path

	return tr("settings.confirm.reset_preferences", path=settings_path())


def download_all_confirm_message() -> str:
	return tr("settings.confirm.download_all")


__all__ = [
	"SETTINGS_MODEL_KINDS",
	"build_settings_snapshot",
	"cache_clear_confirm_message",
	"clear_confirm_message",
	"clear_model_kind",
	"download_all_confirm_message",
	"pending_downloads_for_kind",
	"preferences_reset_confirm_message",
]
