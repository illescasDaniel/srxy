from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from srxy.transcribe_text import (
	ffmpeg_available,
	ffmpeg_unavailable_message,
	is_transcribe_active,
	is_transcribe_available,
	is_transcribe_path,
	iter_transcript_lines,
	reset_transcribe_models,
	transcribe_deps_installed,
	transcribe_max_file_size,
	transcribe_requested,
	transcribe_unavailable_message,
)


pytestmark = pytest.mark.unit


def test_given_transcribe_param_true_when_requesting_then_returns_true():
	# when / then
	assert transcribe_requested(True) is True


def test_given_transcribe_env_set_when_requesting_then_returns_true(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_TRANSCRIBE", "1")

	# when / then
	assert transcribe_requested(None) is True


def test_given_no_transcribe_signal_when_active_then_returns_false(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.delenv("SRXY_TRANSCRIBE", raising=False)

	# when / then
	assert is_transcribe_active() is False


def test_given_mp3_suffix_when_checking_transcribe_path_then_returns_true():
	# when / then
	assert is_transcribe_path(Path("track.mp3")) is True


def test_given_txt_suffix_when_checking_transcribe_path_then_returns_false():
	# when / then
	assert is_transcribe_path(Path("notes.txt")) is False


def test_given_transcribe_max_file_size_env_when_reading_then_returns_int(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_TRANSCRIBE_MAX_FILE_SIZE", "5000000")

	# when / then
	assert transcribe_max_file_size() == 5_000_000


def test_given_ffmpeg_unavailable_message_when_reading_then_mentions_ffmpeg():
	# when / then
	assert "ffmpeg" in ffmpeg_unavailable_message()


def test_given_semantic_deps_missing_message_when_reading_then_mentions_semantic_extra():
	# when / then
	assert "srxy[semantic]" in transcribe_unavailable_message()


def test_given_deps_and_ffmpeg_when_checking_available_then_returns_true(monkeypatch: pytest.MonkeyPatch):
	# given
	with (
		patch("srxy.transcribe_text.transcribe_deps_installed", return_value=True),
		patch("srxy.transcribe_text.ffmpeg_available", return_value=True),
	):
		# when / then
		assert is_transcribe_available() is True


@pytest.mark.transcribe
def test_given_mocked_transcription_when_iterating_lines_then_yields_segments(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	audio = tmp_path / "clip.mp3"
	audio.write_bytes(b"not-a-real-mp3")
	monkeypatch.setenv("SRXY_TRANSCRIBE", "1")
	reset_transcribe_models()

	def fake_transcribe_wav_segments(_wav_path: Path, *, device: str, backend: str):
		return backend, [
			(0, "quarterly earnings"),
			(5, "revenue growth"),
		]

	with (
		patch("srxy.transcribe_text.transcribe_deps_installed", return_value=True),
		patch("srxy.transcribe_text.ffmpeg_available", return_value=True),
		patch("srxy.transcribe_text._with_normalized_audio", return_value=iter([tmp_path / "audio.wav"])),
		patch("srxy.transcribe_text._transcribe_wav_segments", side_effect=fake_transcribe_wav_segments),
		patch("srxy.transcribe_text._cached_transcript_lines", side_effect=lambda _hash, fn: fn()[1]),
	):
		# when
		lines = list(iter_transcript_lines(audio))

	# then
	assert lines == [
		(0, "quarterly earnings"),
		(5, "revenue growth"),
	]


def test_given_ffmpeg_on_path_when_checking_available_then_uses_which(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setattr(
		"srxy.transcribe_text.shutil.which", lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None
	)

	# when / then
	assert ffmpeg_available() is True


def test_given_transcribe_threshold_env_when_reading_then_returns_float(monkeypatch: pytest.MonkeyPatch):
	# given
	monkeypatch.setenv("SRXY_TRANSCRIBE_THRESHOLD", "0.31")

	# when / then
	from srxy.transcribe_text import transcribe_threshold_value

	assert transcribe_threshold_value() == 0.31


def test_given_transcribe_deps_installed_when_checking_then_uses_find_spec(monkeypatch: pytest.MonkeyPatch):
	# given
	def fake_find_spec(name: str):
		if name in {"faster_whisper", "transformers"}:
			return object()
		return None

	monkeypatch.setattr("srxy.transcribe_text.importlib.util.find_spec", fake_find_spec)

	# when / then
	assert transcribe_deps_installed() is True


@pytest.mark.transcribe
def test_given_cached_transcript_when_iterating_twice_then_transcribes_once(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	audio = tmp_path / "clip.mp3"
	audio.write_bytes(b"cached-audio")
	monkeypatch.setenv("SRXY_CACHE_DIR", str(tmp_path / "cache"))
	reset_transcribe_models()

	def fake_transcribe(_wav_path: Path, *, device: str, backend: str):
		return backend, [(42, "call me maybe")]

	with (
		patch("srxy.transcribe_text._with_normalized_audio", return_value=iter([tmp_path / "audio.wav"])),
		patch("srxy.transcribe_text._transcribe_wav_segments", side_effect=fake_transcribe) as transcribe_mock,
	):
		# when
		first = list(iter_transcript_lines(audio))
		second = list(iter_transcript_lines(audio))

	# then
	assert first == [(42, "call me maybe")]
	assert second == [(42, "call me maybe")]
	transcribe_mock.assert_called_once()


@pytest.mark.transcribe
def test_given_empty_transcript_when_caching_then_does_not_store_empty_payload(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	audio = tmp_path / "clip.mp3"
	audio.write_bytes(b"empty-audio")
	monkeypatch.setenv("SRXY_CACHE_DIR", str(tmp_path / "cache"))
	reset_transcribe_models()

	def fake_transcribe(_wav_path: Path, *, device: str, backend: str):
		return backend, []

	with (
		patch("srxy.transcribe_text._with_normalized_audio", return_value=iter([tmp_path / "audio.wav"])),
		patch("srxy.transcribe_text._transcribe_wav_segments", side_effect=fake_transcribe) as transcribe_mock,
	):
		# when
		first = list(iter_transcript_lines(audio))
		second = list(iter_transcript_lines(audio))

	# then
	assert first == []
	assert second == []
	assert transcribe_mock.call_count >= 1
	from srxy.cache import CACHE_KIND_TRANSCRIPT, cache_get, get_file_content_hash

	content_hash = get_file_content_hash(audio)
	cached = cache_get(CACHE_KIND_TRANSCRIPT, content_hash, "cpu:faster-whisper")
	assert cached is None


def test_given_cuda_faster_whisper_failure_when_transcribing_then_falls_back_to_transformers(
	tmp_path: Path,
	capsys: pytest.CaptureFixture[str],
):
	# given
	wav = tmp_path / "audio.wav"
	wav.write_bytes(b"wav")

	def boom(_wav_path: Path, device: str) -> list[tuple[int, str]]:
		raise RuntimeError("Library libcublas.so.12 is not found or cannot be loaded")

	def transformers(_wav_path: Path, device: str) -> list[tuple[int, str]]:
		return [(0, "fallback transcript")]

	with (
		patch("srxy.transcribe_text.resolve_transcribe_device", return_value="cuda"),
		patch("srxy.transcribe_text._iter_faster_whisper_segment_lines", side_effect=boom),
		patch("srxy.transcribe_text._iter_transformers_segment_lines", side_effect=transformers),
		patch("srxy.transcribe_text.transcribe_backend_for_device", return_value="faster-whisper"),
	):
		from srxy.transcribe_text import _transcribe_wav_segments  # pyright: ignore[reportPrivateUsage]

		# when
		backend, segments = _transcribe_wav_segments(wav, device="cuda", backend="faster-whisper")

	# then
	assert backend == "transformers"
	assert segments == [(0, "fallback transcript")]
	assert "falling back to transformers on CUDA" in capsys.readouterr().err


def test_given_cpu_faster_whisper_empty_when_transcribing_then_falls_back_to_transformers(
	tmp_path: Path,
	capsys: pytest.CaptureFixture[str],
):
	# given
	wav = tmp_path / "audio.wav"
	wav.write_bytes(b"wav")

	def empty(_wav_path: Path, device: str) -> list[tuple[int, str]]:
		return []

	def transformers(_wav_path: Path, device: str) -> list[tuple[int, str]]:
		return [(0, "quiet audio transcript")]

	with (
		patch("srxy.transcribe_text._iter_faster_whisper_segment_lines", side_effect=empty),
		patch("srxy.transcribe_text._iter_transformers_segment_lines", side_effect=transformers),
	):
		from srxy.transcribe_text import _transcribe_wav_segments  # pyright: ignore[reportPrivateUsage]

		# when
		backend, segments = _transcribe_wav_segments(wav, device="cpu", backend="faster-whisper")

	# then
	assert backend == "transformers"
	assert segments == [(0, "quiet audio transcript")]
	assert "falling back to transformers" in capsys.readouterr().err


def test_given_seconds_when_formatting_transcript_timestamp_then_uses_mm_ss():
	# when / then
	from srxy.transcribe_text import format_transcript_timestamp

	assert format_transcript_timestamp(0) == "00:00"
	assert format_transcript_timestamp(160) == "02:40"


def test_given_segment_text_when_building_segment_then_omits_timestamp_from_text():
	# given
	from srxy.transcribe_text import _segment_at  # pyright: ignore[reportPrivateUsage]

	# when
	item = _segment_at(160.4, "  And all the other boys  ")

	# then
	assert item == (160, "And all the other boys")


def test_given_transcript_cache_payload_when_round_tripping_then_preserves_timestamp_and_text(
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	from srxy.cache import CACHE_KIND_TRANSCRIPT, cache_get, cache_put, hash_bytes, reset_cache_connection
	from srxy.transcribe_text import _cached_transcript_lines  # pyright: ignore[reportPrivateUsage]

	reset_cache_connection()
	content_hash = hash_bytes(b"audio")
	variant = "base-cuda-faster-whisper"
	cache_put(CACHE_KIND_TRANSCRIPT, content_hash, variant, b"160\tAnd all the other boys")

	def transcribe():
		raise AssertionError("should not transcribe on cache hit")

	with (
		patch("srxy.transcribe_text.resolve_transcribe_device", return_value="cuda"),
		patch("srxy.transcribe_text.transcribe_backend_for_device", return_value="faster-whisper"),
	):
		# when
		lines = _cached_transcript_lines(content_hash, transcribe)

	# then
	assert lines == [(160, "And all the other boys")]
	assert cache_get(CACHE_KIND_TRANSCRIPT, content_hash, variant) is not None


def test_given_nvidia_cublas_lib_when_ensuring_cuda_libs_then_preloads_library(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	import types

	import srxy.transcribe_text as module

	lib_dir = tmp_path / "nvidia" / "cublas" / "lib"
	lib_dir.mkdir(parents=True)
	(lib_dir / "libcublas.so.12").write_bytes(b"\x7fELF")
	fake_cublas = types.ModuleType("nvidia.cublas.lib")
	fake_cublas.__file__ = str(lib_dir / "__init__.py")
	fake_cublas_pkg = types.ModuleType("nvidia.cublas")
	fake_cublas_pkg.lib = fake_cublas
	fake_nvidia = types.ModuleType("nvidia")
	fake_nvidia.cublas = fake_cublas_pkg
	monkeypatch.setitem(sys.modules, "nvidia", fake_nvidia)
	monkeypatch.setitem(sys.modules, "nvidia.cublas", fake_cublas_pkg)
	monkeypatch.setitem(sys.modules, "nvidia.cublas.lib", fake_cublas)
	monkeypatch.setattr(module, "_ctranslate2_cuda_libs_loaded", False)
	loaded: list[str] = []
	monkeypatch.setattr(module.ctypes, "CDLL", lambda path, mode=0: loaded.append(path))

	# when
	module._ensure_ctranslate2_cuda_libs()  # pyright: ignore[reportPrivateUsage]

	# then
	assert loaded == [str(lib_dir / "libcublas.so.12")]
