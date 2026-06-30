from __future__ import annotations

from pathlib import Path
from typing import BinaryIO
from unittest.mock import patch

import pytest
from tests.fixture_xmp import (
	FIXTURE_AUTHOR,
	FIXTURE_SOFTWARE,
	FIXTURE_TITLE,
)
from tests.helpers import PHOTOSHOP_XMP_JPEG_FIXTURE, require_file_search_fixtures

from srxy.media_metadata import is_media_path, iter_media_metadata_lines


pytestmark = pytest.mark.unit


def test_given_arw_suffix_when_checking_media_path_then_returns_true():
	# given
	path = Path("/photos/DSC02995.ARW")

	# when / then
	assert is_media_path(path) is True


def test_given_exifread_tags_when_iterating_metadata_lines_then_maps_make_and_model(tmp_path: Path):
	# given
	raw_file = tmp_path / "photo.arw"
	raw_file.write_bytes(b"\x00")

	class FakeTag:
		def __init__(self, value: str):
			self._value = value

		def __str__(self) -> str:
			return self._value

	def fake_process_file(handle: BinaryIO, details: bool = False):
		return {
			"Image Make": FakeTag("SONY"),
			"Image Model": FakeTag("ILCE-7C"),
			"JPEGThumbnail": FakeTag("skip me"),
		}

	# when
	with patch("exifread.process_file", fake_process_file):
		lines = list(iter_media_metadata_lines(raw_file))

	# then
	assert "[Make] SONY" in lines[0][1]
	assert any("[Model] ILCE-7C" in line[1] for line in lines)


_XMP_WITH_TITLE = """\
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/">
      <dc:title>Desert sunset</dc:title>
      <dc:description>Joshua tree at golden hour</dc:description>
      <dc:subject>landscape</dc:subject>
      <xmpMM:InstanceID xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/">xmp.iid:abc</xmpMM:InstanceID>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
"""


def test_given_xmp_with_title_and_description_when_collecting_tags_then_extracts_human_fields(
	tmp_path: Path,
):
	# given
	image_path = tmp_path / "photo.png"
	image_path.write_bytes(b"\x89PNG\r\n\x1a\n")

	class FakeImage:
		info = {"XML:com.adobe.xmp": _XMP_WITH_TITLE}

		def __enter__(self):
			return self

		def __exit__(self, *_args: object):
			return False

		def getexif(self):
			return {}

	def fake_open_image(_path: Path):
		return FakeImage()

	# when
	with (
		patch("srxy.media_metadata.open_image", fake_open_image),
		patch("srxy.media_metadata.register_image_openers"),
	):
		lines = [text for _line, text in iter_media_metadata_lines(image_path)]

	# then
	assert any("[Title] Desert sunset" in line for line in lines)
	assert any("[Description] Joshua tree at golden hour" in line for line in lines)
	assert any("[Keywords] landscape" in line for line in lines)
	assert not any("InstanceID" in line for line in lines)


def test_given_uuid_only_xmp_when_collecting_tags_then_returns_no_xmp_lines(tmp_path: Path):
	# given
	image_path = tmp_path / "photo.png"
	image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
	xmp = """<x:xmpmeta><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <rdf:Description xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/">
         <xmpMM:DocumentID>xmp.did:037b65ab-2723-4e66-8a30-3cd0d7c73417</xmpMM:DocumentID>
         <rdf:Seq><rdf:li><stEvt:action>saved</stEvt:action></rdf:li></rdf:Seq>
      </rdf:Description>
   </rdf:RDF></x:xmpmeta>"""

	class FakeImage:
		info = {"xmp": xmp}

		def __enter__(self):
			return self

		def __exit__(self, *_args: object):
			return False

		def getexif(self):
			return {}

	# when
	with (
		patch("srxy.media_metadata.open_image", lambda _path: FakeImage()),
		patch("srxy.media_metadata.register_image_openers"),
	):
		lines = [text for _line, text in iter_media_metadata_lines(image_path)]

	# then
	assert lines == []


def test_given_existing_software_tag_when_merging_xmp_then_skips_duplicate_software(tmp_path: Path):
	# given
	image_path = tmp_path / "photo.png"
	image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
	xmp = """<x:xmpmeta><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/">
         <xmp:CreatorTool>Adobe Photoshop CC 2018 (Macintosh)</xmp:CreatorTool>
      </rdf:Description>
   </rdf:RDF></xmpmeta>"""

	class FakeImage:
		info = {"xmp": xmp}

		def __enter__(self):
			return self

		def __exit__(self, *_args: object):
			return False

		def getexif(self):
			from PIL import Image as PILImage

			exif = PILImage.Exif()
			exif[305] = "Adobe Photoshop CC 2018 (Macintosh)"
			return exif

	# when
	with (
		patch("srxy.media_metadata.open_image", lambda _path: FakeImage()),
		patch("srxy.media_metadata.register_image_openers"),
	):
		lines = [text for _line, text in iter_media_metadata_lines(image_path)]

	# then
	software_lines = [line for line in lines if line.startswith("[Software]")]
	assert len(software_lines) == 1


def test_given_utf16le_xp_comment_when_collecting_tags_then_decodes_searchable_text(tmp_path: Path):
	# given
	image_path = tmp_path / "photo.jpg"
	image_path.write_bytes(b"\xff\xd8\xff")

	class FakeImage:
		info = {
			"xpcomment": "a\x00c\x00o\x00m\x00m\x00e\x00n\x00t",
			"xptitle": "s\x00o\x00m\x00e\x00w\x00h\x00e\x00r\x00e",
		}

		def __enter__(self):
			return self

		def __exit__(self, *_args: object):
			return False

		def getexif(self):
			return {}

	# when
	with (
		patch("srxy.media_metadata.open_image", lambda _path: FakeImage()),
		patch("srxy.media_metadata.register_image_openers"),
	):
		lines = [text for _line, text in iter_media_metadata_lines(image_path)]

	# then
	assert any(line == "[Comment] acomment" for line in lines)
	assert any(line == "[Title] somewhere" for line in lines)


def test_given_photoshop_xmp_fixture_when_iterating_metadata_then_indexes_sanitized_fields_not_raw_xml():
	# given
	require_file_search_fixtures()
	fixture = PHOTOSHOP_XMP_JPEG_FIXTURE
	assert fixture.is_file()

	# when
	lines = [text for _line, text in iter_media_metadata_lines(fixture)]
	joined = "\n".join(lines)

	# then
	assert any(line == f"[Software] {FIXTURE_SOFTWARE}" for line in lines)
	assert any(line == f"[Title] {FIXTURE_TITLE}" for line in lines)
	assert any(line == f"[Creator] {FIXTURE_AUTHOR}" for line in lines)
	assert "Adobe" not in joined
	assert "Photoshop" not in joined
	assert "037b65ab" not in joined
	assert "<x:xmpmeta" not in joined
	assert "Xml:Com.Adobe.Xmp" not in joined
