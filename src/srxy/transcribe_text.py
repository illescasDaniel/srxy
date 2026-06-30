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
from srxy.progress import ActivityCallback, emit_activity


_TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})
DEFAULT_TRANSCRIBE_MODEL = "base"
DEFAULT_TRANSCRIBE_THRESHOLD = 0.25
DEFAULT_TRANSCRIBE_MAX_FILE_SIZE = 500 * 1024 * 1024
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
		return DEFAULT_TRANSCRIBE_MAX_FILE_SIZE
	try:
		return int(raw)
	except ValueError:
		return DEFAULT_TRANSCRIBE_MAX_FILE_SIZE


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


def _cublas_library_dir() -> Path | None:
	try:
		import nvidia.cublas.lib as cublas_lib  # type: ignore[import-untyped]
	except ImportError:
		cublas_lib = None
	if cublas_lib is not None:
		module_file = cublas_lib.__file__
		if module_file is not None:
			return Path(module_file).resolve().parent

	import importlib.util

	spec = importlib.util.find_spec("nvidia.cublas")
	if spec is None or not spec.submodule_search_locations:
		return None
	bin_dir = Path(spec.submodule_search_locations[0]) / "bin"
	if bin_dir.is_dir():
		return bin_dir
	return None


def _ensure_ctranslate2_cuda_libs():
	global _ctranslate2_cuda_libs_loaded
	if _ctranslate2_cuda_libs_loaded:
		return
	_ctranslate2_cuda_libs_loaded = True
	lib_dir = _cublas_library_dir()
	if lib_dir is None:
		return
	if sys.platform == "win32":
		if hasattr(os, "add_dll_directory"):
			os.add_dll_directory(str(lib_dir))
		for name in ("cublas64_12.dll", "cublasLt64_12.dll"):
			library = lib_dir / name
			if library.is_file():
				ctypes.CDLL(str(library))
		return
	for name in ("libcublas.so.12", "libcublasLt.so.12"):
		library = lib_dir / name
		if library.is_file():
			ctypes.CDLL(str(library), mode=ctypes.RTLD_GLOBAL)


def transcribe_activity_label(
	path: Path,
	*,
	phase: str = "Transcribe",
	device: str | None = None,
	backend: str | None = None,
) -> str:
	base = f"{phase} · {path.name}"
	if device is None:
		return base
	stack = f"{device}/{backend}" if backend else device
	return f"{base} · {stack}"


def _maybe_warn_transcribe_cpu(device: str):
	warn_if_cpu_device(device, context="transcription")


def _emit_transcribe_fallback(
	on_activity: ActivityCallback | None,
	*,
	path: Path,
	device: str,
	backend: str,
	error: Exception,
):
	message = f"warning: faster-whisper {device} failed ({error}); falling back to {backend} on {device}."
	print(message, file=sys.stderr)
	if on_activity is not None:
		emit_activity(
			on_activity,
			transcribe_activity_label(path, device=device, backend=f"{backend} (fallback)"),
		)


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


def _wav_duration_seconds(wav_path: Path) -> float | None:
	try:
		import wave

		with wave.open(str(wav_path), "rb") as handle:
			rate = handle.getframerate()
			if rate <= 0:
				return None
			return handle.getnframes() / rate
	except (OSError, wave.Error):
		return None


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
	)
	return _transformers_pipeline


def _iter_faster_whisper_segments(
	wav_path: Path,
	device: str,
	*,
	on_activity: ActivityCallback | None = None,
	label: str | None = None,
) -> Iterator[tuple[int, str]]:
	if on_activity is not None and label is not None:
		loading_label = label.replace("Transcribe ·", "Loading model ·", 1)
		emit_activity(on_activity, loading_label)
	model = _get_faster_whisper_model(device)
	segments, info = model.transcribe(  # type: ignore[union-attr]
		str(wav_path),
		beam_size=1,
		vad_filter=False,
		language=None,
	)
	duration = float(getattr(info, "duration", 0.0) or 0.0)
	total = int(duration) if duration > 0 else None
	for segment in segments:
		if on_activity is not None and label is not None:
			if total is not None:
				emit_activity(on_activity, label, current=min(int(segment.end), total), total=total)
			else:
				emit_activity(on_activity, label)
		item = _segment_at(segment.start, segment.text)
		if item is not None:
			yield item


def _iter_transformers_segments(
	wav_path: Path,
	device: str,
	*,
	on_activity: ActivityCallback | None = None,
	label: str | None = None,
) -> Iterator[tuple[int, str]]:
	if on_activity is not None and label is not None:
		emit_activity(on_activity, label)
	pipe = _get_transformers_pipeline(device)
	duration = _wav_duration_seconds(wav_path)
	chunk_length_s = 30 if duration is not None and duration > 30 else None
	if chunk_length_s is not None:
		result = pipe(str(wav_path), return_timestamps=True, chunk_length_s=chunk_length_s)  # type: ignore[call-arg]
	else:
		result = pipe(str(wav_path), return_timestamps=True)  # type: ignore[operator]

	chunks = result.get("chunks") if isinstance(result, dict) else None
	if chunks:
		chunk_limit = len(chunks)
		if duration is not None and duration < 5:
			chunk_limit = min(chunk_limit, max(1, int(duration) + 1))
		for chunk in chunks[:chunk_limit]:
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


def _iter_transformers_segment_lines(
	wav_path: Path,
	device: str,
	*,
	on_activity: ActivityCallback | None = None,
	label: str | None = None,
) -> list[tuple[int, str]]:
	return list(
		_iter_transformers_segments(wav_path, device, on_activity=on_activity, label=label),
	)


def _iter_faster_whisper_segment_lines(
	wav_path: Path,
	device: str,
	*,
	on_activity: ActivityCallback | None = None,
	label: str | None = None,
) -> list[tuple[int, str]]:
	return list(
		_iter_faster_whisper_segments(wav_path, device, on_activity=on_activity, label=label),
	)


def _transcribe_wav_segments(
	wav_path: Path,
	*,
	source_path: Path,
	device: str,
	backend: str,
	on_activity: ActivityCallback | None = None,
	label: str | None = None,
) -> tuple[str, list[tuple[int, str]]]:
	_maybe_warn_transcribe_cpu(device)
	if backend == "transformers":
		return "transformers", _iter_transformers_segment_lines(
			wav_path,
			device,
			on_activity=on_activity,
			label=label,
		)

	try:
		segments = _iter_faster_whisper_segment_lines(
			wav_path,
			device,
			on_activity=on_activity,
			label=label,
		)
		if segments:
			return "faster-whisper", segments
		print(
			"warning: faster-whisper produced no speech segments; falling back to transformers.",
			file=sys.stderr,
		)
		if on_activity is not None:
			emit_activity(
				on_activity,
				transcribe_activity_label(source_path, device=device, backend="transformers (fallback)"),
			)
		return "transformers", _iter_transformers_segment_lines(
			wav_path,
			device,
			on_activity=on_activity,
			label=label,
		)
	except RuntimeError as exc:
		if device != "cuda":
			raise
		_emit_transcribe_fallback(
			on_activity,
			path=source_path,
			device=device,
			backend="transformers",
			error=exc,
		)
		global _faster_whisper_model
		_faster_whisper_model = None
		return "transformers", _iter_transformers_segment_lines(
			wav_path,
			device,
			on_activity=on_activity,
			label=label,
		)


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


def iter_transcript_lines(path: Path, *, on_activity: ActivityCallback | None = None):
	from srxy.cache import get_file_content_hash

	device = resolve_transcribe_device()
	active_backend = transcribe_backend_for_device(device)
	label = transcribe_activity_label(path, device=device, backend=active_backend)
	try:
		content_hash = get_file_content_hash(path)
		_maybe_warn_transcribe_cpu(device)

		def transcribe() -> tuple[str, list[tuple[int, str]]]:
			segments: list[tuple[int, str]] = []
			backend_in_use = active_backend
			emit_activity(
				on_activity,
				transcribe_activity_label(path, device=device, backend=active_backend, phase="Preparing audio"),
			)
			for wav_path in _with_normalized_audio(path):
				emit_activity(on_activity, label)
				backend_in_use, wav_segments = _transcribe_wav_segments(
					wav_path,
					source_path=path,
					device=device,
					backend=backend_in_use,
					on_activity=on_activity,
					label=label,
				)
				segments.extend(wav_segments)
			return backend_in_use, segments

		for timestamp_seconds, text in _cached_transcript_lines(content_hash, transcribe):
			yield timestamp_seconds, text
	except Exception as exc:
		print(f"warning: transcription failed for {path}: {exc}", file=sys.stderr)
