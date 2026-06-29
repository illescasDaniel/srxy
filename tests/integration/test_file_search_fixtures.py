"""Integration tests against tests/fixtures/file_search/."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from srxy.cache import reset_cache_connection, reset_run_file_hashes
from srxy.file_search import magic_file_search
from srxy.matchers.semantic import reset_semantic_model
from srxy.ocr_text import tesseract_available
from srxy.semantic_image import reset_semantic_image_model


pytestmark = pytest.mark.integration


def _srxy(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
	merged = os.environ.copy()
	merged["CI"] = "true"
	if env:
		merged.update(env)
	return subprocess.run(
		[sys.executable, "-m", "srxy.cli", *args, "--no-tui", "--no-progress"],
		capture_output=True,
		text=True,
		env=merged,
		check=False,
	)


@pytest.fixture(autouse=True)
def reset_models():
	reset_semantic_model()
	reset_semantic_image_model()
	reset_cache_connection()
	reset_run_file_hashes()
	yield
	reset_semantic_model()
	reset_semantic_image_model()


def test_given_notes_txt_when_searching_axolotl_then_finds_content(file_search_root: Path):
	# when
	results = magic_file_search(file_search_root / "notes.txt", "axolotl", search_names=False)

	# then
	assert results
	assert "axolotl" in results[0].lines[0].text.lower()


@pytest.mark.semantic
def test_given_minimal_jpeg_when_semantic_image_photo_then_finds_image(file_search_root: Path):
	# when
	results = magic_file_search(
		file_search_root,
		"photograph",
		search_names=False,
		semantic_image=True,
		semantic_image_threshold=0.15,
		limit=10,
	)

	# then
	assert results
	assert any(r.path.suffix.lower() in {".jpg", ".jpeg"} for r in results)


@pytest.mark.ocr
@pytest.mark.skipif(not tesseract_available(), reason="tesseract not on PATH")
def test_given_ocr_pdf_fixture_when_searching_revenue_then_finds_ocr(file_search_root: Path):
	# when
	results = magic_file_search(
		file_search_root / "ocr",
		"revenue",
		search_names=False,
		ocr=True,
	)

	# then
	assert results
	assert any(line.location_kind == "ocr" for r in results for line in r.lines)


def test_given_office_docs_when_searching_tokens_then_finds_each_format(file_search_samples: Path):
	# given
	cases = [
		("fixture_docx_token", "sample.docx"),
		("fixture_xlsx_token", "sample.xlsx"),
		("fixture_pptx_token", "sample.pptx"),
	]

	for token, filename in cases:
		# when
		results = magic_file_search(file_search_samples / "documents", token, search_names=False)

		# then
		assert results, f"no match for {token}"
		assert results[0].path.name == filename


@pytest.mark.transcribe
def test_given_minimal_mp3_when_transcribe_then_finds_audio_metadata(file_search_root: Path):
	# when — minimal.mp3 has ID3 tags but no usable speech for Whisper
	results = magic_file_search(
		file_search_root,
		"Beatles",
		search_names=False,
		transcribe=True,
		limit=5,
	)

	# then
	assert results
	assert any(r.path.name == "minimal.mp3" for r in results)
	assert any(line.location_kind == "tag" for r in results for line in r.lines)


@pytest.mark.ocr
@pytest.mark.skipif(not tesseract_available(), reason="tesseract not on PATH")
def test_given_generated_ocr_image_when_searching_token_then_finds_ocr_line(file_search_samples: Path):
	# when
	results = magic_file_search(file_search_samples / "ocr", "fixture_ocr_token", search_names=False, ocr=True)

	# then
	assert results
	assert any(line.location_kind == "ocr" for line in results[0].lines)


def test_given_cli_json_output_when_searching_then_emits_valid_json(file_search_root: Path):
	# when
	proc = _srxy("axolotl", str(file_search_root), "--content-only", "--json")

	# then
	assert proc.returncode == 0
	payload = json.loads(proc.stdout)
	assert isinstance(payload, list)
	assert payload


def test_given_unquoted_or_phrases_when_searching_then_finds_matches(file_search_root: Path):
	# when
	results = magic_file_search(file_search_root, "axolotl|fixture_docx_token", search_names=False)

	# then
	assert results
	names = {r.path.name for r in results}
	assert "notes.txt" in names or "sample.docx" in names


def test_given_srxy_transcribe_env_without_transcribe_flag_when_basic_search_then_succeeds(
	file_search_root: Path,
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given — env persistence must not block or enable transcribe without CLI flag
	cache = tmp_path / "empty-cache"
	monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
	proc = _srxy(
		"axolotl",
		str(file_search_root),
		"--content-only",
		env={"SRXY_TRANSCRIBE": "1", "SRXY_CACHE_DIR": str(cache), "SRXY_AUTO_DOWNLOAD": "0"},
	)

	# then
	assert proc.returncode == 0
	assert "axolotl" in proc.stdout.lower()


def test_given_hidden_file_when_include_hidden_then_finds_secret(file_search_samples: Path):
	# when
	results = magic_file_search(
		file_search_samples / "edge",
		"hidden_secret",
		search_names=False,
		skip_hidden_folders=False,
	)

	# then
	assert results
	assert any(".hidden_secret" in r.path.name for r in results)


def test_given_noise_file_when_searching_token_then_finds_content(file_search_samples: Path):
	# when
	results = magic_file_search(
		file_search_samples / "edge",
		"noise_content_token",
		search_names=False,
	)

	# then
	assert results
	assert any("noise_notes.txt" in r.path.name for r in results)


@pytest.mark.integration_full
@pytest.mark.semantic
def test_given_portrait_when_semantic_image_person_then_finds_image(file_search_root: Path):
	photo = file_search_root / "portrait.jpg"
	assert photo.is_file(), f"missing portrait fixture: {photo}"
	# when
	results = magic_file_search(
		photo,
		"person",
		search_names=False,
		search_contents=False,
		semantic_image=True,
		limit=10,
	)

	# then
	assert results
	assert results[0].path.suffix.lower() in {".jpg", ".jpeg", ".dng"}


@pytest.mark.integration_full
@pytest.mark.ocr
def test_given_ocr_pdf_when_searching_revenue_then_finds_embedded_text(file_search_root: Path):
	# when
	results = magic_file_search(
		file_search_root / "ocr",
		"revenue",
		search_names=False,
		ocr=True,
	)

	# then
	assert results
	assert any(line.location_kind == "ocr" for r in results for line in r.lines)


@pytest.mark.integration_full
@pytest.mark.transcribe
def test_given_speech_sample_when_transcribe_then_finds_mp3(file_search_samples: Path):
	audio = file_search_samples / "audio" / "speech_sample.mp3"
	assert audio.is_file(), f"missing speech fixture: {audio}"
	# when
	results = magic_file_search(
		audio,
		"thank you very much",
		search_names=False,
		transcribe=True,
		limit=10,
	)

	# then
	assert results
	assert results[0].path.suffix.lower() == ".mp3"
	assert any(line.location_kind == "transcript" for r in results for line in r.lines)


@pytest.mark.integration_full
@pytest.mark.transcribe
def test_given_minimal_mp4_when_searching_by_name_then_finds_video(file_search_root: Path):
	mp4 = file_search_root / "minimal.mp4"
	assert mp4.is_file(), f"missing minimal mp4 fixture: {mp4}"
	# when
	results = magic_file_search(
		mp4,
		"minimal",
		search_names=True,
		search_contents=False,
		limit=5,
	)

	# then
	assert results
	assert results[0].path.suffix.lower() == ".mp4"


@pytest.mark.integration_full
@pytest.mark.semantic
def test_given_semantic_all_when_searching_axolotl_then_finds_text(file_search_root: Path):
	# when
	results = magic_file_search(
		file_search_root,
		"axolotl",
		search_names=False,
		ocr=True,
		transcribe=True,
		semantic_image=True,
		limit=5,
	)

	# then
	assert results


@pytest.mark.integration_full
@pytest.mark.transcribe
@pytest.mark.transcribe_device_matrix
def test_given_speech_sample_when_device_matrix_then_finds_matches(
	device: str,
	file_search_samples: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setenv("SRXY_TRANSCRIBE_DEVICE", device)
	audio = file_search_samples / "audio" / "speech_sample.mp3"
	assert audio.is_file(), f"missing speech fixture: {audio}"

	# when
	results = magic_file_search(
		audio,
		"thank you very much",
		search_names=False,
		transcribe=True,
		limit=5,
	)

	# then
	assert results, f"no results on device={device}"
