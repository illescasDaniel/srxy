"""Release QA integration tests against tests/fixtures/qa_corpus/."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from srxy.cache import reset_cache_connection, reset_run_file_hashes
from srxy.file_search import magic_file_search
from srxy.matchers.semantic import reset_semantic_model
from srxy.semantic_image import reset_semantic_image_model


pytestmark = [pytest.mark.integration, pytest.mark.qa]


def _srxy(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
	merged = os.environ.copy()
	merged["CI"] = "true"
	if env:
		merged.update(env)
	return subprocess.run(
		["srxy", *args, "--no-tui", "--no-progress"],
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


def test_given_notes_txt_when_searching_axolotl_then_finds_content(qa_docs: Path):
	# when
	results = magic_file_search(qa_docs / "notes.txt", "axolotl", search_names=False)

	# then
	assert results
	assert "axolotl" in results[0].lines[0].text.lower()


@pytest.mark.semantic
def test_given_minimal_jpeg_when_semantic_image_photo_then_finds_image(qa_docs: Path):
	# when
	results = magic_file_search(
		qa_docs,
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
def test_given_ocr_pdf_fixture_when_searching_revenue_then_finds_ocr(qa_docs: Path):
	# when
	results = magic_file_search(
		qa_docs / "ocr",
		"revenue",
		search_names=False,
		ocr=True,
	)

	# then
	assert results
	assert any(line.location_kind == "ocr" for r in results for line in r.lines)


def test_given_office_docs_when_searching_tokens_then_finds_each_format(qa_downloads: Path):
	# given
	cases = [
		("qa_docx_token", "sample.docx"),
		("qa_xlsx_token", "sample.xlsx"),
		("qa_pptx_token", "sample.pptx"),
	]

	for token, filename in cases:
		# when
		results = magic_file_search(qa_downloads / "documents", token, search_names=False)

		# then
		assert results, f"no match for {token}"
		assert results[0].path.name == filename


@pytest.mark.transcribe
def test_given_minimal_mp3_when_transcribe_then_finds_audio_metadata(qa_docs: Path):
	# when — minimal.mp3 has ID3 tags but no usable speech for Whisper
	results = magic_file_search(
		qa_docs,
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
def test_given_generated_ocr_image_when_searching_token_then_finds_ocr_line(qa_downloads: Path):
	# when
	results = magic_file_search(qa_downloads / "ocr", "qa_ocr_token", search_names=False, ocr=True)

	# then
	assert results
	assert any(line.location_kind == "ocr" for line in results[0].lines)


def test_given_cli_json_output_when_searching_then_emits_valid_json(qa_docs: Path):
	# when
	proc = _srxy("axolotl", str(qa_docs), "--content-only", "--json")

	# then
	assert proc.returncode == 0
	payload = json.loads(proc.stdout)
	assert isinstance(payload, list)
	assert payload


def test_given_unquoted_or_phrases_when_searching_then_finds_matches(qa_root: Path):
	# when
	results = magic_file_search(qa_root, "axolotl|qa_docx_token", search_names=False)

	# then
	assert results
	names = {r.path.name for r in results}
	assert "notes.txt" in names or "sample.docx" in names


def test_given_srxy_transcribe_env_without_transcribe_flag_when_basic_search_then_succeeds(
	qa_docs: Path,
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given — env persistence must not block or enable transcribe without CLI flag
	cache = tmp_path / "empty-cache"
	monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
	proc = _srxy(
		"axolotl",
		str(qa_docs),
		"--content-only",
		env={"SRXY_TRANSCRIBE": "1", "SRXY_CACHE_DIR": str(cache), "SRXY_AUTO_DOWNLOAD": "0"},
	)

	# then
	assert proc.returncode == 0
	assert "axolotl" in proc.stdout.lower()


@pytest.mark.qa_full
@pytest.mark.semantic
def test_given_full_photos_when_semantic_image_person_then_finds_images(qa_docs: Path):
	photo = qa_docs / "IMG_20260223_184931.jpg"
	assert photo.is_file(), f"missing QA photo fixture: {photo}"
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


@pytest.mark.qa_full
@pytest.mark.ocr
def test_given_full_pdf_when_ocr_normalize_then_finds_embedded_screenshot(qa_docs: Path):
	# when
	results = magic_file_search(
		qa_docs / "ocr",
		"revenue",
		search_names=False,
		ocr=True,
	)

	# then
	assert results
	assert any(line.location_kind == "ocr" for r in results for line in r.lines)


@pytest.mark.qa_full
@pytest.mark.transcribe
@pytest.mark.skip(reason="pending replacement transcribe audio fixture")
def test_given_full_audio_when_transcribe_all_i_know_then_finds_flac(qa_docs: Path):
	# when
	results = magic_file_search(
		qa_docs,
		"all i know",
		search_names=False,
		transcribe=True,
		limit=10,
	)

	# then
	assert results
	assert any(r.path.suffix.lower() == ".flac" for r in results)
	assert any(line.location_kind == "transcript" for r in results for line in r.lines)


@pytest.mark.qa_full
@pytest.mark.transcribe
def test_given_full_video_when_transcribe_then_finds_mp4(qa_root: Path):
	mp4 = qa_root / "IMG_20260222_181128.mp4"
	assert mp4.is_file(), f"missing QA video fixture: {mp4}"
	# when
	results = magic_file_search(
		mp4,
		"you",
		search_names=False,
		transcribe=True,
		limit=5,
	)

	# then
	assert results
	assert results[0].path.suffix.lower() == ".mp4"


@pytest.mark.qa_full
@pytest.mark.semantic
@pytest.mark.skip(reason="pending replacement semantic audio fixture")
def test_given_full_semantic_all_when_searching_linkin_then_finds_audio(qa_docs: Path):
	# when
	results = magic_file_search(
		qa_docs,
		"linkin",
		search_names=False,
		ocr=True,
		transcribe=True,
		semantic_image=True,
		limit=5,
	)

	# then
	assert results


@pytest.mark.qa_full
@pytest.mark.transcribe
@pytest.mark.transcribe_device_matrix
@pytest.mark.skip(reason="pending replacement transcribe audio fixture")
def test_given_full_transcribe_when_device_matrix_then_finds_matches(
	device: str,
	qa_docs: Path,
	monkeypatch: pytest.MonkeyPatch,
):
	# given
	monkeypatch.setenv("SRXY_TRANSCRIBE_DEVICE", device)

	# when
	results = magic_file_search(
		qa_docs,
		"all i know",
		search_names=False,
		transcribe=True,
		limit=5,
	)

	# then
	assert results, f"no results on device={device}"
