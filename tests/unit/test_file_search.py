from __future__ import annotations

import plistlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from tests.helpers import (
	copy_media_fixture,
	file_search_root,
	require_file_search_fixtures,
	set_windows_tags,
	write_docx_with_text,
	write_mp4_with_tags,
	write_pdf_with_text,
	write_pptx_with_text,
	write_xlsx_with_text,
)

from srxy import FileQ, magic_file_search
from srxy.cli import match_labels
from srxy.models import FileSearchResult, MatchType, SkippedFile
from srxy.progress import ActivityUpdate
from srxy.windows_metadata import windows_tags_supported, windows_tags_writable
from srxy.xattr_metadata import finder_tag_xattr_writable, set_xattr, xattr_supported


pytestmark = pytest.mark.unit


def test_given_directory_with_matching_filename_when_searching_names_then_returns_file(tmp_path: Path):
	# given
	(tmp_path / "notes.txt").write_text("unrelated", encoding="utf-8")
	(tmp_path / "budget-2024.md").write_text("figures", encoding="utf-8")
	query = "budget"

	# when
	results = magic_file_search(tmp_path, query, search_contents=False, threshold=0.5)

	# then
	assert len(results) == 1
	assert results[0].path.name == "budget-2024.md"
	assert results[0].score >= 0.5
	assert "name" in results[0].breakdown


def test_given_directory_with_matching_content_when_searching_contents_then_returns_file(tmp_path: Path):
	# given
	(tmp_path / "notes.txt").write_text("quarterly revenue projections", encoding="utf-8")
	(tmp_path / "other.txt").write_text("hello world", encoding="utf-8")
	query = "revenue"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path.name == "notes.txt"
	assert results[0].breakdown["content"] >= 0.25
	assert len(results[0].lines) == 1
	assert results[0].lines[0].line_number == 1
	assert "revenue" in results[0].lines[0].text


def test_given_multiline_file_when_searching_contents_then_returns_matching_line_numbers(tmp_path: Path):
	# given
	(tmp_path / "notes.txt").write_text("alpha\nquarterly revenue projections\nomega\n", encoding="utf-8")
	query = "revenue"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert len(results[0].lines) == 1
	assert results[0].lines[0].line_number == 2
	assert "revenue" in results[0].lines[0].text


def test_given_weak_lines_when_searching_contents_then_excludes_lines_below_threshold(tmp_path: Path):
	# given
	(tmp_path / "notes.txt").write_text("alpha\nbeta\n", encoding="utf-8")
	query = "zzzzzzzz"

	# when
	results = magic_file_search(tmp_path, query, search_names=False, threshold=0.9)

	# then
	assert results == []


def test_given_many_matching_lines_when_searching_contents_then_respects_max_matches(tmp_path: Path):
	# given
	lines = "\n".join(f"token line {index}" for index in range(100))
	(tmp_path / "many.txt").write_text(lines, encoding="utf-8")
	query = "token"

	# when
	results = magic_file_search(tmp_path, query, search_names=False, max_matches=3, threshold=0.25)

	# then
	assert len(results) == 1
	assert len(results[0].lines) == 3


def test_given_max_line_matches_alias_when_searching_then_emits_deprecation_warning(tmp_path: Path):
	# given
	(tmp_path / "many.txt").write_text("token line", encoding="utf-8")
	query = "token"

	# when / then
	with pytest.warns(DeprecationWarning, match="max_line_matches is deprecated"):
		results = magic_file_search(tmp_path, query, search_names=False, max_line_matches=1, threshold=0.25)
	assert len(results[0].lines) == 1


def test_given_single_file_path_when_searching_then_returns_that_file(tmp_path: Path):
	# given
	file_path = tmp_path / "alpha.py"
	file_path.write_text("def alpha_handler(): pass", encoding="utf-8")
	query = "alpha"

	# when
	results = magic_file_search(file_path, query)

	# then
	assert len(results) == 1
	assert results[0].path == file_path.resolve()


def test_given_hidden_directory_when_searching_then_skips_hidden_entries(tmp_path: Path):
	# given
	hidden_dir = tmp_path / ".git"
	hidden_dir.mkdir()
	(hidden_dir / "config").write_text("secret token", encoding="utf-8")
	(tmp_path / "visible.txt").write_text("token", encoding="utf-8")
	query = "token"

	# when
	results = magic_file_search(tmp_path, query, skip_hidden_folders=True)

	# then
	assert len(results) == 1
	assert results[0].path.name == "visible.txt"


def test_given_hidden_directory_when_skip_hidden_folders_disabled_then_includes_hidden_entries(tmp_path: Path):
	# given
	hidden_dir = tmp_path / ".git"
	hidden_dir.mkdir()
	(hidden_dir / "config").write_text("secret token", encoding="utf-8")
	(tmp_path / "visible.txt").write_text("token", encoding="utf-8")
	query = "token"

	# when
	results = magic_file_search(tmp_path, query, skip_hidden_folders=False)

	# then
	assert len(results) == 2
	path_names = {result.path.name for result in results}
	assert path_names == {"config", "visible.txt"}


def test_given_noise_directory_when_searching_then_skips_noise_entries(tmp_path: Path):
	# given
	noise_dir = tmp_path / "__pycache__"
	noise_dir.mkdir()
	(noise_dir / "module.cpython-312.pyc").write_bytes(b"needle bytecode")
	(tmp_path / "visible.txt").write_text("needle", encoding="utf-8")
	query = "needle"

	# when
	results = magic_file_search(tmp_path, query, skip_noise_folders=True)

	# then
	assert len(results) == 1
	assert results[0].path.name == "visible.txt"


def test_given_noise_directory_when_skip_noise_folders_disabled_then_includes_noise_entries(tmp_path: Path):
	# given
	noise_dir = tmp_path / "node_modules"
	noise_dir.mkdir()
	(noise_dir / "package.txt").write_text("needle dependency", encoding="utf-8")
	(tmp_path / "visible.txt").write_text("needle", encoding="utf-8")
	query = "needle"

	# when
	results = magic_file_search(tmp_path, query, skip_noise_folders=False)

	# then
	assert len(results) == 2
	path_names = {result.path.name for result in results}
	assert path_names == {"package.txt", "visible.txt"}


def test_given_hidden_and_noise_directories_when_both_skip_flags_disabled_then_includes_all_entries(
	tmp_path: Path,
):
	# given
	hidden_dir = tmp_path / ".git"
	hidden_dir.mkdir()
	(hidden_dir / "config").write_text("secret token", encoding="utf-8")
	noise_dir = tmp_path / "__pycache__"
	noise_dir.mkdir()
	(noise_dir / "cache.txt").write_text("token cache", encoding="utf-8")
	(tmp_path / "visible.txt").write_text("token", encoding="utf-8")
	query = "token"

	# when
	results = magic_file_search(tmp_path, query, skip_hidden_folders=False, skip_noise_folders=False)

	# then
	assert len(results) == 3
	path_names = {result.path.name for result in results}
	assert path_names == {"cache.txt", "config", "visible.txt"}


def test_given_binary_file_when_searching_contents_then_skips_binary(tmp_path: Path):
	# given
	(tmp_path / "data.bin").write_bytes(b"\x00\x01secret\xff")
	(tmp_path / "plain.txt").write_text("secret sauce", encoding="utf-8")
	query = "secret"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path.name == "plain.txt"


def test_given_oversized_file_when_searching_contents_then_skips_content_match(tmp_path: Path):
	# given
	large_file = tmp_path / "large.txt"
	large_file.write_text("needle " + ("x" * 2_000_000), encoding="utf-8")
	query = "needle"

	# when
	results = magic_file_search(tmp_path, query, search_names=False, max_file_size=1024)

	# then
	assert results == []


def test_given_large_text_file_when_searching_without_size_limit_then_finds_match(tmp_path: Path):
	# given
	large_file = tmp_path / "large.txt"
	large_file.write_text("needle " + ("x" * 2_000_000), encoding="utf-8")
	query = "needle"

	# when
	results = magic_file_search(tmp_path, query, search_names=False, max_file_size=None)

	# then
	assert len(results) == 1
	assert results[0].path == large_file


def test_given_high_threshold_when_searching_weak_match_then_returns_empty(tmp_path: Path):
	# given
	(tmp_path / "item.txt").write_text("hello", encoding="utf-8")
	query = "helo"

	# when
	results = magic_file_search(tmp_path, query, threshold=0.99)

	# then
	assert results == []


def test_given_empty_query_when_searching_files_then_returns_empty_list(tmp_path: Path):
	# given
	(tmp_path / "item.txt").write_text("hello", encoding="utf-8")

	# when
	results = magic_file_search(tmp_path, "   ")

	# then
	assert results == []


def test_given_missing_path_when_searching_then_raises_file_not_found(tmp_path: Path):
	# given
	missing = tmp_path / "missing"

	# when
	with pytest.raises(FileNotFoundError, match="does not exist"):
		magic_file_search(missing, "test")

	# then
	assert True


def test_given_no_search_modes_when_searching_then_raises_value_error(tmp_path: Path):
	# given
	(tmp_path / "item.txt").write_text("hello", encoding="utf-8")

	# when
	with pytest.raises(ValueError, match="search_names, search_contents, or semantic_image"):
		magic_file_search(tmp_path, "hello", search_names=False, search_contents=False)

	# then
	assert True


def test_given_pdf_with_matching_content_when_searching_contents_then_returns_file(tmp_path: Path):
	# given
	write_pdf_with_text(tmp_path / "report.pdf", "quarterly revenue projections")
	(tmp_path / "other.txt").write_text("hello world", encoding="utf-8")
	query = "revenue"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path.name == "report.pdf"
	assert results[0].breakdown["content"] >= 0.25
	assert len(results[0].lines) == 1
	assert results[0].lines[0].line_number == 1
	assert "revenue" in results[0].lines[0].text


def test_given_docx_with_matching_content_when_searching_contents_then_returns_file(tmp_path: Path):
	# given
	write_docx_with_text(tmp_path / "memo.docx", "quarterly revenue projections")
	query = "revenue"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path.name == "memo.docx"
	assert results[0].lines[0].line_number == 1
	assert "revenue" in results[0].lines[0].text


def test_given_xlsx_with_matching_content_when_searching_contents_then_returns_file(tmp_path: Path):
	# given
	write_xlsx_with_text(tmp_path / "budget.xlsx", "quarterly revenue")
	query = "revenue"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path.name == "budget.xlsx"
	assert results[0].lines[0].line_number == 1
	assert "revenue" in results[0].lines[0].text
	assert "[Summary]" in results[0].lines[0].text


def test_given_pptx_with_matching_content_when_searching_contents_then_returns_file(tmp_path: Path):
	# given
	write_pptx_with_text(tmp_path / "deck.pptx", "quarterly revenue projections")
	query = "revenue"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path.name == "deck.pptx"
	assert results[0].lines[0].line_number == 1
	assert "revenue" in results[0].lines[0].text


def test_given_corrupt_pdf_when_searching_contents_then_skips_gracefully(tmp_path: Path):
	# given
	(tmp_path / "broken.pdf").write_bytes(b"\x00not-a-real-pdf\xff")
	(tmp_path / "plain.txt").write_text("secret sauce", encoding="utf-8")
	query = "secret"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path.name == "plain.txt"


def test_given_oversized_file_when_collecting_skipped_then_reports_file(tmp_path: Path):
	# given
	large_file = tmp_path / "large.txt"
	large_file.write_text("needle " + ("x" * 2_000_000), encoding="utf-8")
	skipped: list[SkippedFile] = []
	query = "needle"

	# when
	results = magic_file_search(tmp_path, query, search_names=False, max_file_size=1024, skipped_files=skipped)

	# then
	assert results == []
	assert len(skipped) == 1
	assert skipped[0].path == large_file
	assert skipped[0].size_bytes > 1024


def test_given_oversized_media_when_searching_contents_then_does_not_skip_for_size(tmp_path: Path):
	# given
	copy_media_fixture("minimal.mp3", tmp_path / "large.mp3")
	large_mp3 = tmp_path / "large.mp3"
	with large_mp3.open("ab") as handle:
		handle.write(b"\x00" * 2_000_000)
	skipped: list[SkippedFile] = []
	query = "beatles"

	# when
	results = magic_file_search(tmp_path, query, search_names=False, max_file_size=1024, skipped_files=skipped)

	# then
	assert skipped == []
	assert len(results) == 1
	assert results[0].path.name == "large.mp3"


def test_given_directory_when_searching_with_callbacks_then_streams_progress_and_results(tmp_path: Path):
	# given
	(tmp_path / "alpha.txt").write_text("hello", encoding="utf-8")
	(tmp_path / "beta.txt").write_text("revenue report", encoding="utf-8")
	(tmp_path / "gamma.txt").write_text("goodbye", encoding="utf-8")
	progress_calls: list[tuple[int, int]] = []
	streamed_paths: list[str] = []

	def on_progress(current: int, total: int) -> None:
		progress_calls.append((current, total))

	def on_result(result: FileSearchResult):
		streamed_paths.append(result.path.name)

	# when
	results = magic_file_search(
		tmp_path,
		"revenue",
		search_names=False,
		on_progress=on_progress,
		on_result=on_result,
	)

	# then
	assert progress_calls == [(1, 3), (2, 3), (3, 3)]
	assert streamed_paths == ["beta.txt"]
	assert len(results) == 1
	assert results[0].path.name == "beta.txt"


def test_given_jpeg_with_exif_title_when_searching_contents_then_returns_file(tmp_path: Path):
	# given
	copy_media_fixture("minimal.jpg", tmp_path / "photo.jpg")
	query = "vacation"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path.name == "photo.jpg"
	assert results[0].lines[0].location_kind == "tag"
	assert "vacation" in results[0].lines[0].text


def test_given_oversized_arw_with_sony_make_when_searching_contents_then_returns_file(tmp_path: Path):
	# given
	arw_file = tmp_path / "DSC02995.ARW"
	arw_file.write_bytes(b"\x00" * 2_000_000)

	class FakeTag:
		def __init__(self, value: str):
			self._value = value

		def __str__(self) -> str:
			return self._value

	def fake_process_file(handle: object, details: bool = False):
		return {"Image Make": FakeTag("SONY"), "Image Model": FakeTag("ILCE-7C")}

	skipped: list[SkippedFile] = []
	query = "sony"

	# when
	with patch("exifread.process_file", fake_process_file):
		results = magic_file_search(tmp_path, query, search_names=False, skipped_files=skipped)

	# then
	assert skipped == []
	assert len(results) == 1
	assert results[0].path.name == "DSC02995.ARW"
	assert results[0].lines[0].location_kind == "tag"
	assert "[Make] SONY" in results[0].lines[0].text


def test_given_mp3_with_artist_tag_when_searching_contents_then_returns_file(tmp_path: Path):
	# given
	copy_media_fixture("minimal.mp3", tmp_path / "track.mp3")
	query = "beatles"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path.name == "track.mp3"
	assert results[0].lines[0].location_kind == "tag"
	assert "Beatles" in results[0].lines[0].text


@pytest.mark.transcribe
def test_given_mp3_with_mocked_transcript_when_transcribing_then_returns_transcript_line(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	from tests.helpers import copy_media_fixture

	copy_media_fixture("minimal.mp3", tmp_path / "podcast.mp3")
	query = "all the other boys"

	with patch(
		"srxy.file_search.iter_transcript_lines",
		return_value=iter([(160, "And all the other boys")]),
	):
		# when
		results = magic_file_search(tmp_path, query, search_names=False, transcribe=True)

	# then
	assert len(results) == 1
	assert results[0].path.name == "podcast.mp3"
	transcript_lines = [line for line in results[0].lines if line.location_kind == "transcript"]
	assert len(transcript_lines) == 1
	assert transcript_lines[0].line_number == 160
	assert "all the other boys" in transcript_lines[0].text
	assert "02:40" not in transcript_lines[0].text


def test_given_transcript_at_two_forty_when_searching_for_minute_token_then_does_not_match(
	tmp_path: Path,
):
	# given
	from tests.helpers import copy_media_fixture

	copy_media_fixture("minimal.mp3", tmp_path / "song.flac")

	with patch(
		"srxy.file_search.iter_transcript_lines",
		return_value=iter([(160, "And all the other boys")]),
	):
		# when
		results = magic_file_search(tmp_path, "02", search_names=False, transcribe=True)

	# then
	assert results == []


def test_given_mp4_with_title_tag_when_searching_contents_then_returns_file(tmp_path: Path):
	# given
	copy_media_fixture("minimal.mp4", tmp_path / "clip.mp4")
	query = "revenue"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path.name == "clip.mp4"
	assert results[0].lines[0].location_kind == "tag"
	assert "revenue" in results[0].lines[0].text


def test_given_oversized_mp4_with_tags_when_searching_contents_then_still_matches(tmp_path: Path):
	# given
	write_mp4_with_tags(tmp_path / "large.mp4", title="blockbuster premiere", min_size=2_000_000)
	skipped: list[SkippedFile] = []
	query = "blockbuster"

	# when
	results = magic_file_search(tmp_path, query, search_names=False, skipped_files=skipped)

	# then
	assert skipped == []
	assert len(results) == 1
	assert results[0].path.name == "large.mp4"
	assert "blockbuster" in results[0].lines[0].text


def test_given_corrupt_jpeg_when_searching_contents_then_skips_gracefully(tmp_path: Path):
	# given
	(tmp_path / "broken.jpg").write_bytes(b"\xff\xd8\xff\xe0not-a-real-jpeg")
	(tmp_path / "plain.txt").write_text("secret sauce", encoding="utf-8")
	query = "secret"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path.name == "plain.txt"


@pytest.mark.linux_xattr
@pytest.mark.skipif(not xattr_supported(), reason="extended attributes are not supported on this platform")
def test_given_xdg_tag_on_mp4_when_searching_contents_then_returns_file(tmp_path: Path):
	# given
	copy_media_fixture("minimal.mp4", tmp_path / "untitled.mp4")
	set_xattr(tmp_path / "untitled.mp4", "user.xdg.tags", b"cursor")
	query = "cursor"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path.name == "untitled.mp4"
	assert results[0].lines[0].location_kind == "tag"
	assert "cursor" in results[0].lines[0].text


@pytest.mark.linux_xattr
@pytest.mark.skipif(not xattr_supported(), reason="extended attributes are not supported on this platform")
def test_given_xdg_tag_on_oversized_file_when_searching_contents_then_still_matches(tmp_path: Path):
	# given
	large_file = tmp_path / "large.bin"
	large_file.write_bytes(b"\x00" * 2_000_000)
	set_xattr(large_file, "user.xdg.tags", b"cursor")
	skipped: list[SkippedFile] = []
	query = "cursor"

	# when
	results = magic_file_search(tmp_path, query, search_names=False, skipped_files=skipped)

	# then
	assert skipped == []
	assert len(results) == 1
	assert results[0].path.name == "large.bin"
	assert "cursor" in results[0].lines[0].text


@pytest.mark.linux_xattr
@pytest.mark.skipif(not xattr_supported(), reason="extended attributes are not supported on this platform")
def test_given_xdg_comment_on_jpeg_when_searching_contents_then_returns_file(tmp_path: Path):
	# given
	copy_media_fixture("minimal.jpg", tmp_path / "wallpaper.jpg")
	set_xattr(tmp_path / "wallpaper.jpg", "user.xdg.comment", b"mytag")
	query = "mytag"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path.name == "wallpaper.jpg"
	assert results[0].lines[0].location_kind == "tag"
	assert "[XDG comment] mytag" in results[0].lines[0].text


@pytest.mark.linux_xattr
@pytest.mark.skipif(not xattr_supported(), reason="extended attributes are not supported on this platform")
def test_given_xdg_comment_on_oversized_file_when_searching_contents_then_still_matches(tmp_path: Path):
	# given
	large_file = tmp_path / "large.bin"
	large_file.write_bytes(b"\x00" * 2_000_000)
	set_xattr(large_file, "user.xdg.comment", b"mytag")
	skipped: list[SkippedFile] = []
	query = "mytag"

	# when
	results = magic_file_search(tmp_path, query, search_names=False, skipped_files=skipped)

	# then
	assert skipped == []
	assert len(results) == 1
	assert results[0].path.name == "large.bin"
	assert "[XDG comment] mytag" in results[0].lines[0].text


_FINDER_TAG_ATTR = "com.apple.metadata:_kMDItemUserTags"


@pytest.mark.macos_finder
@pytest.mark.skipif(
	not xattr_supported() or not finder_tag_xattr_writable(),
	reason="macOS Finder tag extended attributes are not writable on this platform",
)
def test_given_finder_tag_on_file_when_searching_contents_then_returns_file(tmp_path: Path):
	# given
	tagged_file = tmp_path / "notes.txt"
	tagged_file.write_text("unrelated body", encoding="utf-8")
	set_xattr(
		tagged_file,
		_FINDER_TAG_ATTR,
		plistlib.dumps(["cursor"], fmt=plistlib.FMT_BINARY),
	)
	query = "cursor"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path.name == "notes.txt"
	assert results[0].lines[0].location_kind == "tag"
	assert "[Finder tag] cursor" in results[0].lines[0].text


@pytest.mark.macos_finder
@pytest.mark.skipif(
	not xattr_supported() or not finder_tag_xattr_writable(),
	reason="macOS Finder tag extended attributes are not writable on this platform",
)
def test_given_finder_tag_with_color_suffix_when_searching_contents_then_matches_tag_name(tmp_path: Path):
	# given
	tagged_file = tmp_path / "report.pdf"
	tagged_file.write_bytes(b"%PDF-1.4\n")
	set_xattr(
		tagged_file,
		_FINDER_TAG_ATTR,
		plistlib.dumps(["Important\n6", "Red\n6"], fmt=plistlib.FMT_BINARY),
	)
	query = "important"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path.name == "report.pdf"
	assert any("[Finder tag] Important" in line.text for line in results[0].lines)

	red_results = magic_file_search(tmp_path, "red", search_names=False)
	assert len(red_results) == 1
	assert any("[Finder tag] Red" in line.text for line in red_results[0].lines)


@pytest.mark.macos_finder
@pytest.mark.skipif(
	not xattr_supported() or not finder_tag_xattr_writable(),
	reason="macOS Finder tag extended attributes are not writable on this platform",
)
def test_given_finder_tag_on_oversized_file_when_searching_contents_then_still_matches(tmp_path: Path):
	# given
	large_file = tmp_path / "large.bin"
	large_file.write_bytes(b"\x00" * 2_000_000)
	set_xattr(
		large_file,
		_FINDER_TAG_ATTR,
		plistlib.dumps(["cursor"], fmt=plistlib.FMT_BINARY),
	)
	skipped: list[SkippedFile] = []
	query = "cursor"

	# when
	results = magic_file_search(tmp_path, query, search_names=False, skipped_files=skipped)

	# then
	assert skipped == []
	assert len(results) == 1
	assert results[0].path.name == "large.bin"
	assert "[Finder tag] cursor" in results[0].lines[0].text


@pytest.mark.windows_tags
@pytest.mark.skipif(
	not windows_tags_supported() or not windows_tags_writable(),
	reason="Windows Explorer tags are not available or writable on this platform",
)
def test_given_windows_tag_on_jpeg_when_searching_contents_then_returns_file(tmp_path: Path):
	# given
	tagged_file = tmp_path / "wallpaper.jpg"
	copy_media_fixture("minimal.jpg", tagged_file)
	set_windows_tags(tagged_file, ["cursor"])
	query = "cursor"

	# when
	results = magic_file_search(tmp_path, query, search_names=False)

	# then
	assert len(results) == 1
	assert results[0].path.name == "wallpaper.jpg"
	assert results[0].lines[0].location_kind == "tag"
	assert "[Windows tag] cursor" in results[0].lines[0].text


@pytest.mark.windows_tags
@pytest.mark.skipif(
	not windows_tags_supported() or not windows_tags_writable(),
	reason="Windows Explorer tags are not available or writable on this platform",
)
def test_given_windows_tag_on_oversized_file_when_searching_contents_then_still_matches(tmp_path: Path):
	# given
	large_file = tmp_path / "large.jpg"
	copy_media_fixture("minimal.jpg", large_file)
	large_file.write_bytes(large_file.read_bytes() + b"\x00" * 2_000_000)
	set_windows_tags(large_file, ["cursor"])
	skipped: list[SkippedFile] = []
	query = "cursor"

	# when
	results = magic_file_search(tmp_path, query, search_names=False, skipped_files=skipped)

	# then
	assert skipped == []
	assert len(results) == 1
	assert results[0].path.name == "large.jpg"


def test_given_image_with_ocr_text_when_searching_without_ocr_then_skips_pixel_text(tmp_path: Path):
	# given
	image_path = tmp_path / "scan.png"
	Image.new("L", (20, 20), color=255).save(image_path)
	query = "invoice"

	with patch("srxy.ocr_text.ocr_pil_image", return_value="invoice total due"):
		# when
		results = magic_file_search(tmp_path, query, search_names=False, ocr=False)

	# then
	assert results == []


def test_given_image_with_ocr_text_when_searching_with_ocr_then_returns_match(tmp_path: Path):
	# given
	image_path = tmp_path / "scan.png"
	Image.new("L", (20, 20), color=255).save(image_path)
	query = "invoice"

	with (
		patch("srxy.ocr_text.is_ocr_available", return_value=True),
		patch("srxy.ocr_text.ocr_pil_image", return_value="invoice total due"),
	):
		# when
		results = magic_file_search(tmp_path, query, search_names=False, ocr=True)

	# then
	assert len(results) == 1
	assert results[0].path.name == "scan.png"
	assert results[0].lines[0].location_kind == "ocr"
	assert "invoice" in results[0].lines[0].text


def test_given_pdf_with_sparse_page_when_searching_with_ocr_then_uses_image_ocr(tmp_path: Path):
	# given
	pdf_path = tmp_path / "scan.pdf"
	pdf_path.write_bytes(b"%PDF-1.4\n")
	query = "revenue"
	fake_page = MagicMock()
	fake_page.extract_text.return_value = "   "

	with (
		patch("srxy.ocr_text.is_ocr_available", return_value=True),
		patch("pypdf.PdfReader") as reader_cls,
		patch("srxy.ocr_text.ocr_pdf_page_images", return_value="quarterly revenue projections") as ocr_images,
	):
		reader_cls.return_value.pages = [fake_page]

		# when
		results = magic_file_search(tmp_path, query, search_names=False, ocr=True)

	# then
	ocr_images.assert_called_once_with(fake_page)
	assert len(results) == 1
	assert results[0].path.name == "scan.pdf"
	assert results[0].lines[0].location_kind == "ocr"
	assert "revenue" in results[0].lines[0].text


def test_given_pdf_with_embedded_text_when_searching_with_ocr_then_supplements_with_image_ocr(tmp_path: Path):
	# given
	write_pdf_with_text(tmp_path / "report.pdf", "quarterly revenue projections embedded")
	query = "revenue"

	with (
		patch("srxy.ocr_text.is_ocr_available", return_value=True),
		patch("srxy.ocr_text.ocr_pdf_page_images", return_value="extra chart label") as ocr_images,
	):
		# when
		results = magic_file_search(tmp_path, query, search_names=False, ocr=True)

	# then
	ocr_images.assert_called_once()
	assert len(results) == 1
	assert results[0].path.name == "report.pdf"
	assert results[0].lines[0].location_kind == "page"
	assert "embedded" in results[0].lines[0].text


def test_given_embedded_pdf_when_searching_without_ocr_then_uses_page_kind(tmp_path: Path):
	# given
	write_pdf_with_text(tmp_path / "report.pdf", "quarterly revenue projections")
	query = "revenue"

	# when
	results = magic_file_search(tmp_path, query, search_names=False, ocr=False)

	# then
	assert len(results) == 1
	assert results[0].lines[0].location_kind == "page"


def test_given_oversized_image_when_searching_with_ocr_then_records_skip(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
	# given
	image_path = tmp_path / "large.png"
	image_path.write_bytes(b"\x00" * 25_000_000)
	skipped: list[SkippedFile] = []
	query = "invoice"
	monkeypatch.setenv("SRXY_OCR_MAX_FILE_SIZE", "20971520")

	with patch("srxy.ocr_text.is_ocr_available", return_value=True):
		# when
		results = magic_file_search(
			tmp_path,
			query,
			search_names=False,
			ocr=True,
			skipped_files=skipped,
		)

	# then
	assert results == []
	assert len(skipped) == 1
	assert skipped[0].reason == "ocr_too_large"
	assert skipped[0].path == image_path


def test_given_image_when_searching_with_semantic_image_then_adds_breakdown_score(tmp_path: Path):
	# given
	image_path = tmp_path / "beach.png"
	image_path.write_bytes(b"png")
	query = "sunset beach"

	with (
		patch("srxy.file_search.is_semantic_image_active", return_value=True),
		patch("srxy.file_search.encode_semantic_image_query", return_value=[1.0, 0.0]),
		patch("srxy.file_search.score_image", return_value=0.71) as score_image,
	):
		# when
		results = magic_file_search(
			tmp_path,
			query,
			search_names=False,
			search_contents=False,
			semantic_image=True,
		)

	# then
	score_image.assert_called_once()
	assert len(results) == 1
	assert results[0].path == image_path
	assert results[0].breakdown["semantic_image"] == pytest.approx(0.71)
	assert len(results[0].lines) == 1
	assert results[0].lines[0].location_kind == "semantic_image"
	assert results[0].lines[0].text == "(visual match)"


def test_given_ocr_near_match_when_semantic_image_wins_then_includes_ocr_preview_line(tmp_path: Path):
	# given
	image_path = tmp_path / "family.jpg"
	image_path.write_bytes(b"jpg")
	query = "sibling"

	with (
		patch("srxy.file_search.is_semantic_image_active", return_value=True),
		patch("srxy.file_search.is_semantic_image_path", return_value=True),
		patch("srxy.file_search.encode_semantic_image_query", return_value=[1.0, 0.0]),
		patch("srxy.file_search.score_image", return_value=0.27),
		patch(
			"srxy.file_search._iter_searchable_lines",
			return_value=[(1, "Sister (=)", "ocr")],
		),
		patch("srxy.file_search.CompositeMatcher") as composite_matcher,
	):
		composite_matcher.return_value.score_with_breakdown.side_effect = lambda q, value: (
			(0.291, {"semantic": 0.75, "fuzzy": 0.4}) if value == "sister" else (0.0, {})
		)

		# when
		results = magic_file_search(
			tmp_path,
			query,
			search_names=False,
			search_contents=True,
			semantic_image=True,
		)

	# then
	assert len(results) == 1
	assert results[0].breakdown["semantic_image"] == pytest.approx(0.27)
	assert len(results[0].lines) == 1
	assert results[0].lines[0].text == "(visual match)"
	assert results[0].lines[0].location_kind == "semantic_image"
	assert results[0].lines[0].score == pytest.approx(0.27)


def test_given_semantic_query_when_content_line_is_related_synonym_then_matches(tmp_path: Path):
	# given
	text_path = tmp_path / "things.txt"
	text_path.write_text("recents\n", encoding="utf-8")

	with (
		patch("srxy.file_search.CompositeMatcher") as composite_matcher,
		patch("srxy.matchers.registry.is_matcher_available", return_value=True),
	):
		composite_matcher.return_value.score_with_breakdown.side_effect = lambda q, value: (
			(0.245, {"semantic": 0.56, "fuzzy": 0.38}) if value == "recents" else (0.0, {})
		)

		# when
		results = magic_file_search(
			tmp_path,
			"new",
			search_names=False,
			search_contents=True,
		)

	# then
	assert len(results) == 1
	assert results[0].path == text_path
	assert results[0].score == pytest.approx(0.56)
	assert results[0].lines[0].location_kind == "line"
	assert results[0].lines[0].text == "recents"


def test_given_exif_tag_key_when_searching_sibling_then_does_not_match_tag_line(tmp_path: Path):
	# given
	image_path = tmp_path / "photo.jpg"
	image_path.write_bytes(b"jpg")
	query = "sibling"

	with patch(
		"srxy.file_search._iter_searchable_lines",
		return_value=[(11, "[Ycbcrpositioning] 1", "tag")],
	):
		# when
		results = magic_file_search(
			tmp_path,
			query,
			search_names=False,
			search_contents=True,
			threshold=0.18,
		)

	# then
	assert results == []


def test_given_short_transcript_when_searching_sibling_then_does_not_match(tmp_path: Path):
	# given
	audio_path = tmp_path / "song.flac"
	audio_path.write_bytes(b"flac")
	query = "sibling"

	with patch(
		"srxy.file_search._iter_searchable_lines",
		return_value=[(0, "I", "transcript")],
	):
		# when
		results = magic_file_search(
			tmp_path,
			query,
			search_names=False,
			search_contents=True,
			threshold=0.18,
		)

	# then
	assert results == []


def test_given_focusing_transcript_when_searching_sibling_then_does_not_match(tmp_path: Path):
	# given
	audio_path = tmp_path / "song.flac"
	audio_path.write_bytes(b"flac")
	query = "sibling"

	with (
		patch(
			"srxy.file_search._iter_searchable_lines",
			return_value=[(40, "A little pace that they're focusing", "transcript")],
		),
		patch("srxy.file_search.CompositeMatcher") as composite_matcher,
		patch(
			"srxy.matchers.registry.is_matcher_available",
			lambda match_type: match_type == MatchType.SEMANTIC,
		),
	):
		composite_matcher.return_value.score_with_breakdown.side_effect = lambda q, value: (
			(0.297, {"semantic": 0.20, "fuzzy": 0.63}) if value == "focusing" else (0.0, {})
		)

		# when
		results = magic_file_search(
			tmp_path,
			query,
			search_names=False,
			search_contents=True,
			threshold=0.18,
		)

	# then
	assert results == []


def test_given_semantic_image_below_text_threshold_when_searching_then_uses_image_threshold(
	tmp_path: Path,
):
	# given
	image_path = tmp_path / "beach.png"
	image_path.write_bytes(b"png")
	query = "person"

	with (
		patch("srxy.file_search.is_semantic_image_active", return_value=True),
		patch("srxy.file_search.encode_semantic_image_query", return_value=[1.0, 0.0]),
		patch("srxy.file_search.score_image", return_value=0.198),
	):
		# when
		results = magic_file_search(
			tmp_path,
			query,
			search_names=False,
			search_contents=False,
			semantic_image=True,
			threshold=0.35,
		)

	# then
	assert len(results) == 1
	assert results[0].breakdown["semantic_image"] == pytest.approx(0.198)


def test_given_text_only_path_when_searching_with_semantic_image_then_skips_query_encoding(tmp_path: Path):
	# given
	text_path = tmp_path / "things.txt"
	text_path.write_text("recents\n", encoding="utf-8")

	with (
		patch("srxy.file_search.is_semantic_image_active", return_value=True),
		patch("srxy.file_search.encode_semantic_image_query") as encode_query,
	):
		# when
		results = magic_file_search(
			text_path,
			"recent",
			search_names=False,
			search_contents=True,
			semantic_image=True,
		)

	# then
	encode_query.assert_not_called()
	assert len(results) == 1
	assert results[0].path == text_path


def test_given_semantic_image_when_searching_with_on_activity_then_reports_phases(tmp_path: Path):
	# given
	image_path = tmp_path / "beach.png"
	image_path.write_bytes(b"png")
	activities: list[ActivityUpdate | None] = []

	with (
		patch("srxy.file_search.is_semantic_image_active", return_value=True),
		patch("srxy.file_search.encode_semantic_image_query", return_value=[1.0, 0.0]),
		patch("srxy.file_search.score_image", return_value=0.71),
	):
		# when
		magic_file_search(
			tmp_path,
			"sunset",
			search_names=False,
			search_contents=False,
			semantic_image=True,
			on_activity=activities.append,
		)

	# then
	assert any(activity is not None and activity.label == "Encoding image query…" for activity in activities)
	assert any(
		activity is not None and activity.label is not None and activity.label.startswith("CLIP ·")
		for activity in activities
	)
	assert activities[-1] is None


def test_given_multiple_matching_lines_when_searching_then_returns_lines_in_descending_score_order(
	tmp_path: Path,
):
	# given
	(tmp_path / "doc.txt").write_text(
		"unrelated\nbeta revenue mention\nrevenue revenue revenue\n",
		encoding="utf-8",
	)
	query = "revenue"

	# when
	results = magic_file_search(tmp_path, query, search_names=False, threshold=0.1)

	# then
	assert len(results) == 1
	scores = [line.score for line in results[0].lines]
	assert scores == sorted(scores, reverse=True)


def test_given_multiple_files_when_searching_with_limit_then_returns_top_scores_sorted(tmp_path: Path):
	# given
	(tmp_path / "zzz-rev.txt").write_text("x", encoding="utf-8")
	(tmp_path / "revenue-report.txt").write_text("y", encoding="utf-8")
	(tmp_path / "revenue.txt").write_text("z", encoding="utf-8")
	query = "revenue"

	# when
	results = magic_file_search(
		tmp_path,
		query,
		search_names=True,
		search_contents=False,
		threshold=0.1,
		limit=2,
	)

	# then
	assert len(results) == 2
	assert results[0].score >= results[1].score
	assert results[0].path.name == "revenue.txt"


def test_given_or_query_when_searching_contents_then_matches_either_term(tmp_path: Path):
	# given
	(tmp_path / "alpha.txt").write_text("only alpha appears here", encoding="utf-8")
	(tmp_path / "beta.txt").write_text("only beta appears here", encoding="utf-8")
	(tmp_path / "gamma.txt").write_text("nothing useful", encoding="utf-8")
	query = "alpha|beta"

	# when
	results = magic_file_search(tmp_path, query, search_names=False, threshold=0.35)

	# then
	names = {result.path.name for result in results}
	assert names == {"alpha.txt", "beta.txt"}


def test_given_and_query_when_searching_contents_then_requires_both_terms(tmp_path: Path):
	# given
	(tmp_path / "both.txt").write_text("alpha and beta together", encoding="utf-8")
	(tmp_path / "alpha-only.txt").write_text("alpha alone", encoding="utf-8")
	(tmp_path / "beta-only.txt").write_text("beta alone", encoding="utf-8")
	query = "alpha&beta"

	# when
	results = magic_file_search(tmp_path, query, search_names=False, threshold=0.35)

	# then
	assert len(results) == 1
	assert results[0].path.name == "both.txt"


def test_given_and_query_with_terms_on_different_lines_when_searching_then_matches_file(tmp_path: Path):
	# given
	(tmp_path / "notes.txt").write_text("alpha on line one\nbeta on line two\n", encoding="utf-8")
	query = "alpha&beta"

	# when
	results = magic_file_search(tmp_path, query, search_names=False, threshold=0.35)

	# then
	assert len(results) == 1
	assert results[0].path.name == "notes.txt"
	assert len(results[0].lines) >= 1


def test_given_and_query_when_terms_match_different_lines_then_line_scores_use_term_scores(tmp_path: Path):
	# given
	(tmp_path / "song.txt").write_text("linkin park on one line\nlyrics mention in the end here\n", encoding="utf-8")
	query = FileQ.leaf("linkin park") & FileQ.leaf("in the end")

	# when
	results = magic_file_search(tmp_path, query, search_names=False, threshold=0.35)

	# then
	assert len(results) == 1
	assert len(results[0].lines) == 2
	assert all(line.score > 0.0 for line in results[0].lines)


def test_given_and_query_when_terms_match_different_surfaces_then_lines_record_matched_term(tmp_path: Path):
	# given
	(tmp_path / "song.txt").write_text("linkin park on one line\nlyrics mention in the end here\n", encoding="utf-8")
	query = FileQ.leaf("linkin park") & FileQ.leaf("in the end")

	# when
	results = magic_file_search(tmp_path, query, search_names=False, threshold=0.35)

	# then
	assert len(results) == 1
	terms = {line.matched_term for line in results[0].lines}
	assert "linkin park" in terms
	assert "in the end" in terms


def test_given_or_query_on_fixtures_when_match_labels_then_uses_per_term_surfaces():
	# given
	require_file_search_fixtures()
	query = "amphibianis|minimal"

	# when
	results = magic_file_search(file_search_root(), query, threshold=0.35)
	by_name = {result.path.name: result for result in results}

	# then
	assert "minimal.mp3" in by_name
	assert match_labels(by_name["minimal.mp3"]) == "name"
	assert "notes.txt" in by_name
	assert match_labels(by_name["notes.txt"]) == "content"


def test_given_xmp_seq_token_when_searching_sig_on_tag_then_does_not_match(tmp_path: Path):
	# given
	image = tmp_path / "photo.png"
	Image.new("RGB", (8, 8), "white").save(image)

	# when
	with patch(
		"srxy.file_search.iter_media_metadata_lines",
		return_value=iter([(1, "[Metadata] Seq")]),
	):
		results = magic_file_search(
			tmp_path,
			"sig",
			search_names=False,
			search_contents=True,
			threshold=0.18,
		)

	# then
	assert results == []


def test_given_low_quality_ocr_text_when_searching_image_then_skips_match(tmp_path: Path):
	# given
	image = tmp_path / "chart.png"
	Image.new("RGB", (8, 8), "white").save(image)
	query = "sig"

	# when
	with (
		patch("srxy.ocr_text.is_ocr_available", return_value=True),
		patch("srxy.ocr_text.ocr_pil_image", return_value="e gl A\n.\n¥\n| SRR LA 56 T P ) > e \\"),
	):
		results = magic_file_search(tmp_path, query, search_names=False, ocr=True, threshold=0.18)

	# then
	assert results == []


def test_given_photoshop_xmp_fixture_when_searching_sig_then_does_not_match(tmp_path: Path):
	# given
	require_file_search_fixtures()
	copy_media_fixture("samples/images/photoshop_xmp.jpg", tmp_path / "tree.jpg")

	# when
	results = magic_file_search(
		tmp_path,
		"SIG",
		search_names=False,
		search_contents=True,
		ocr=False,
		semantic_image=False,
		threshold=0.18,
	)

	# then
	assert results == []
