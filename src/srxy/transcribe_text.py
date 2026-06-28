from __future__ import annotations

import ctypes
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

from srxy.device import (
	resolve_transcribe_device,
	transcribe_backend_for_device,
	transcribe_compute_type,
	warn_if_cpu_device,
)
from srxy.media_metadata import AUDIO_SUFFIXES, VIDEO_SUFFIXES


_TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})
DEFAULT_TRANSCRIBE_MODEL = "base"
DEFAULT_TRANSCRIBE_THRESHOLD = 0.25
TRANSCRIBE_SUFFIXES = AUDIO_SUFFIXES | VIDEO_SUFFIXES

_TRANSCRIBE_DEPS_UNAVAILABLE_MESSAGE = "Transcription requires the optional dependency: pip install 'srxy[semantic]'"

_FFMPEG_UNAVAILABLE_MESSAGE = (
	"ffmpeg is not available. Install the ffmpeg binary on PATH "
	"(e.g. ffmpeg on Debian/Ubuntu, ffmpeg on Arch, brew install ffmpeg on macOS)."
)

_faster_whisper_model: object | None = None
_transformers_pipeline: object | None = None
_ctranslate2_cuda_libs_loaded = False


def transcribe_env_enabled() -> bool:
	value = os.environ.get("SRXY_TRANSCRIBE", "").strip().lower()
	return value in _TRUTHY_ENV_VALUES


def transcribe_requested(transcribe: bool | None) -> bool:
	if transcribe is not None:
		return transcribe
	return transcribe_env_enabled()


def transcribe_deps_installed() -> bool:
	return (
		importlib.util.find_spec("faster_whisper") is not None and importlib.util.find_spec("transformers") is not None
	)


def ffmpeg_available() -> bool:
	return shutil.which("ffmpeg") is not None


def is_transcribe_available() -> bool:
	return transcribe_deps_installed() and ffmpeg_available()


def is_transcribe_active(transcribe: bool | None = None) -> bool:
	return transcribe_requested(transcribe) and is_transcribe_available()


def transcribe_max_file_size() -> int | None:
	raw = os.environ.get("SRXY_TRANSCRIBE_MAX_FILE_SIZE", "").strip()
	if not raw:
		return None
	try:
		return int(raw)
	except ValueError:
		return None


def transcribe_model_name() -> str:
	raw = os.environ.get("SRXY_TRANSCRIBE_MODEL", DEFAULT_TRANSCRIBE_MODEL).strip()
	return raw or DEFAULT_TRANSCRIBE_MODEL


def transcribe_threshold_value() -> float:
	raw = os.environ.get("SRXY_TRANSCRIBE_THRESHOLD", "").strip()
	if raw:
		try:
			return float(raw)
		except ValueError:
			pass
	return DEFAULT_TRANSCRIBE_THRESHOLD


def is_transcribe_path(path: Path) -> bool:
	return path.suffix.lower() in TRANSCRIBE_SUFFIXES


def transcribe_unavailable_message() -> str:
	return _TRANSCRIBE_DEPS_UNAVAILABLE_MESSAGE


def ffmpeg_unavailable_message() -> str:
	return _FFMPEG_UNAVAILABLE_MESSAGE


def ensure_transcribe_available():
	if not transcribe_deps_installed():
		raise RuntimeError(_TRANSCRIBE_DEPS_UNAVAILABLE_MESSAGE)
	if not ffmpeg_available():
		raise RuntimeError(_FFMPEG_UNAVAILABLE_MESSAGE)


def reset_transcribe_models():
	global _faster_whisper_model, _transformers_pipeline, _ctranslate2_cuda_libs_loaded
	_faster_whisper_model = None
	_transformers_pipeline = None
	_ctranslate2_cuda_libs_loaded = False


def _ensure_ctranslate2_cuda_libs():
	global _ctranslate2_cuda_libs_loaded
	if _ctranslate2_cuda_libs_loaded:
		return
	_ctranslate2_cuda_libs_loaded = True
	try:
		import nvidia.cublas.lib  # type: ignore[import-untyped]
	except ImportError:
		return
	module_file = nvidia.cublas.lib.__file__
	if module_file is None:
		return
	lib_dir = Path(module_file).resolve().parent
	for name in ("libcublas.so.12", "libcublasLt.so.12"):
		library = lib_dir / name
		if library.is_file():
			ctypes.CDLL(str(library), mode=ctypes.RTLD_GLOBAL)


def _maybe_warn_transcribe_cpu(device: str):
	warn_if_cpu_device(device, context="transcription")


def _cache_variant(device: str, backend: str) -> str:
	return f"{transcribe_model_name()}-{device}-{backend}"


def format_transcript_timestamp(seconds: int) -> str:
	total = max(0, int(seconds))
	minutes, secs = divmod(total, 60)
	return f"{minutes:02d}:{secs:02d}"


def _segment_at(start: float, text: str) -> tuple[int, str] | None:
	clean = text.strip()
	if not clean:
		return None
	return int(start), clean


def _encode_transcript_cache_line(seconds: int, text: str) -> str:
	return f"{seconds}\t{text}"


def _decode_transcript_cache_line(raw_line: str) -> tuple[int, str] | None:
	stripped = raw_line.strip()
	if not stripped or "\t" not in stripped:
		return None
	seconds_str, text = stripped.split("\t", 1)
	return int(seconds_str), text


def _extract_audio_wav(source: Path, destination: Path) -> bool:
	ffmpeg = shutil.which("ffmpeg")
	if ffmpeg is None:
		return False
	result = subprocess.run(  # noqa: S603
		[
			ffmpeg,
			"-nostdin",
			"-hide_banner",
			"-loglevel",
			"error",
			"-y",
			"-i",
			str(source),
			"-ac",
			"1",
			"-ar",
			"16000",
			"-vn",
			str(destination),
		],
		capture_output=True,
		check=False,
	)
	return result.returncode == 0 and destination.is_file() and destination.stat().st_size > 0


def _with_normalized_audio(path: Path) -> Iterator[Path]:
	with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
		wav_path = Path(handle.name)
	try:
		if _extract_audio_wav(path, wav_path):
			yield wav_path
	finally:
		wav_path.unlink(missing_ok=True)


def _faster_whisper_model_path() -> str:
	from srxy.model_store import transcribe_faster_whisper_model_dir, transcribe_faster_whisper_repo_id

	directory = transcribe_faster_whisper_model_dir()
	if directory.is_dir() and any(directory.iterdir()):
		return str(directory)
	return transcribe_faster_whisper_repo_id()


def _get_faster_whisper_model(device: str):
	global _faster_whisper_model
	if _faster_whisper_model is not None:
		return _faster_whisper_model

	if device == "cuda":
		_ensure_ctranslate2_cuda_libs()

	from faster_whisper import WhisperModel  # type: ignore[import-untyped]

	from srxy.model_store import transcribe_faster_whisper_model_dir

	whisper_device = "cuda" if device == "cuda" else "cpu"
	model_source = _faster_whisper_model_path()
	_faster_whisper_model = WhisperModel(
		model_source,
		device=whisper_device,
		compute_type=transcribe_compute_type(device),
		download_root=str(transcribe_faster_whisper_model_dir().parent),
	)
	return _faster_whisper_model


def _get_transformers_pipeline(device: str):
	global _transformers_pipeline
	if _transformers_pipeline is not None:
		return _transformers_pipeline

	from transformers import pipeline  # type: ignore[import-untyped]

	from srxy.model_store import transcribe_transformers_model_dir, transcribe_transformers_model_id

	model_path = transcribe_transformers_model_dir()
	model_id = (
		str(model_path) if model_path.is_dir() and any(model_path.iterdir()) else transcribe_transformers_model_id()
	)
	_transformers_pipeline = pipeline(
		"automatic-speech-recognition",
		model=model_id,
		device=device,
		chunk_length_s=30,
	)
	return _transformers_pipeline


def _iter_faster_whisper_segments(wav_path: Path, device: str) -> Iterator[tuple[int, str]]:
	model = _get_faster_whisper_model(device)
	segments, _info = model.transcribe(  # type: ignore[union-attr]
		str(wav_path),
		beam_size=1,
		vad_filter=False,
		language=None,
	)
	for segment in segments:
		item = _segment_at(segment.start, segment.text)
		if item is not None:
			yield item


def _iter_transformers_segments(wav_path: Path, device: str) -> Iterator[tuple[int, str]]:
	pipe = _get_transformers_pipeline(device)
	result = pipe(str(wav_path), return_timestamps=True)  # type: ignore[operator]

	chunks = result.get("chunks") if isinstance(result, dict) else None
	if chunks:
		for chunk in chunks:
			if not isinstance(chunk, dict):
				continue
			text = str(chunk.get("text", "")).strip()
			if not text:
				continue
			timestamp = chunk.get("timestamp")
			start = 0.0
			if isinstance(timestamp, (list, tuple)) and timestamp:
				start = float(timestamp[0] or 0.0)
			item = _segment_at(start, text)
			if item is not None:
				yield item
		return

	text = str(result.get("text", "") if isinstance(result, dict) else result).strip()
	if text:
		item = _segment_at(0.0, text)
		if item is not None:
			yield item


def _iter_transformers_segment_lines(wav_path: Path, device: str) -> list[tuple[int, str]]:
	return list(_iter_transformers_segments(wav_path, device))


def _iter_faster_whisper_segment_lines(wav_path: Path, device: str) -> list[tuple[int, str]]:
	return list(_iter_faster_whisper_segments(wav_path, device))


def _transcribe_wav_segments(
	wav_path: Path,
	*,
	device: str,
	backend: str,
) -> tuple[str, list[tuple[int, str]]]:
	_maybe_warn_transcribe_cpu(device)
	if backend == "transformers":
		return "transformers", _iter_transformers_segment_lines(wav_path, device)

	try:
		segments = _iter_faster_whisper_segment_lines(wav_path, device)
		if segments:
			return "faster-whisper", segments
		print(
			"warning: faster-whisper produced no speech segments; falling back to transformers.",
			file=sys.stderr,
		)
		return "transformers", _iter_transformers_segment_lines(wav_path, device)
	except RuntimeError as exc:
		if device != "cuda":
			raise
		print(
			f"warning: faster-whisper CUDA failed ({exc}); falling back to transformers on CUDA.",
			file=sys.stderr,
		)
		global _faster_whisper_model
		_faster_whisper_model = None
		return "transformers", _iter_transformers_segment_lines(wav_path, device)


def _cached_transcript_lines(
	content_hash: str,
	transcribe: Callable[[], tuple[str, list[tuple[int, str]]]],
) -> list[tuple[int, str]]:
	from srxy.cache import CACHE_KIND_TRANSCRIPT, cache_get, cache_put

	device = resolve_transcribe_device()
	planned_backend = transcribe_backend_for_device(device)
	cached = cache_get(CACHE_KIND_TRANSCRIPT, content_hash, _cache_variant(device, planned_backend))
	if cached is not None:
		lines: list[tuple[int, str]] = []
		for raw_line in cached.decode("utf-8").splitlines():
			item = _decode_transcript_cache_line(raw_line)
			if item is not None:
				lines.append(item)
		if lines:
			return lines

	backend, segments = transcribe()
	variant = _cache_variant(device, backend)
	if backend != planned_backend:
		cached = cache_get(CACHE_KIND_TRANSCRIPT, content_hash, variant)
		if cached is not None:
			lines = []
			for raw_line in cached.decode("utf-8").splitlines():
				item = _decode_transcript_cache_line(raw_line)
				if item is not None:
					lines.append(item)
			if lines:
				return lines

	if not segments:
		print(
			f"warning: transcription produced no speech segments for cached content {content_hash[:12]}",
			file=sys.stderr,
		)
		return []

	payload = "\n".join(_encode_transcript_cache_line(seconds, text) for seconds, text in segments).encode("utf-8")
	cache_put(CACHE_KIND_TRANSCRIPT, content_hash, variant, payload)
	return segments


def iter_transcript_lines(path: Path) -> Iterator[tuple[int, str]]:
	from srxy.cache import get_file_content_hash

	try:
		content_hash = get_file_content_hash(path)
		device = resolve_transcribe_device()
		active_backend = transcribe_backend_for_device(device)

		def transcribe() -> tuple[str, list[tuple[int, str]]]:
			segments: list[tuple[int, str]] = []
			backend_in_use = active_backend
			for wav_path in _with_normalized_audio(path):
				backend_in_use, wav_segments = _transcribe_wav_segments(
					wav_path,
					device=device,
					backend=backend_in_use,
				)
				segments.extend(wav_segments)
			return backend_in_use, segments

		for timestamp_seconds, text in _cached_transcript_lines(content_hash, transcribe):
			yield timestamp_seconds, text
	except Exception as exc:
		print(f"warning: transcription failed for {path}: {exc}", file=sys.stderr)
