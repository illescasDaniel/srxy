from __future__ import annotations

import re
from typing import TYPE_CHECKING


if TYPE_CHECKING:
	from PIL.Image import Exif

FIXTURE_SOFTWARE = "MockEditor 2.0 (Linux)"
FIXTURE_AUTHOR = "Fixture Author"
FIXTURE_TITLE = "Joshua tree test"
FIXTURE_DESCRIPTION = "Desert landscape photo"
FIXTURE_DATETIME_EXIF = "2020:01:15 10:30:00"
FIXTURE_DATETIME_XMP = "2020-01-15T10:30:00+00:00"
FIXTURE_DOCUMENT_ID = "xmp.did:00000000-0000-4000-8000-000000000002"
FIXTURE_INSTANCE_ID_PRIMARY = "xmp.iid:00000000-0000-4000-8000-000000000001"
FIXTURE_INSTANCE_ID_SECONDARY = "xmp.iid:00000000-0000-4000-8000-000000000003"

_ADOBE_SOFTWARE_RE = re.compile(r"Adobe Photoshop CC 2018 \(Macintosh\)")
_XMP_ISO_DATETIME_RE = re.compile(r"2019-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}")
_XMP_IID_RE = re.compile(r"xmp\.iid:[0-9a-f-]+", re.IGNORECASE)
_XMP_DID_RE = re.compile(r"xmp\.did:[0-9a-f-]+", re.IGNORECASE)


def sanitize_xmp_packet(xmp: bytes | str) -> bytes:
	text = xmp.decode("utf-8") if isinstance(xmp, bytes) else xmp
	text = _ADOBE_SOFTWARE_RE.sub(FIXTURE_SOFTWARE, text)
	text = text.replace("2019:05:29 11:20:37", FIXTURE_DATETIME_EXIF)
	text = _XMP_ISO_DATETIME_RE.sub(FIXTURE_DATETIME_XMP, text)
	text = text.replace("image/png", "image/jpeg")
	text = _XMP_IID_RE.sub(FIXTURE_INSTANCE_ID_PRIMARY, text, count=1)
	text = _XMP_IID_RE.sub(FIXTURE_INSTANCE_ID_SECONDARY, text, count=1)
	text = _XMP_IID_RE.sub(FIXTURE_INSTANCE_ID_PRIMARY, text)
	text = _XMP_DID_RE.sub(FIXTURE_DOCUMENT_ID, text)

	text = _set_xml_tag(text, "dc", "title", FIXTURE_TITLE)
	text = _set_xml_tag(text, "dc", "description", FIXTURE_DESCRIPTION)
	text = _set_xml_tag(text, "dc", "creator", FIXTURE_AUTHOR)
	text = _set_xml_tag(text, "xmp", "CreatorTool", FIXTURE_SOFTWARE)
	return text.encode("utf-8")


def sanitize_exif(exif: Exif) -> Exif:
	from PIL import Image

	sanitized = Image.Exif()
	sanitized[305] = FIXTURE_SOFTWARE
	sanitized[306] = FIXTURE_DATETIME_EXIF
	sanitized[315] = FIXTURE_AUTHOR
	sanitized[270] = FIXTURE_TITLE
	if exif:
		for tag_id in (274, 282, 283, 296):
			if tag_id in exif:
				sanitized[tag_id] = exif[tag_id]
	return sanitized


def _set_xml_tag(xmp: str, prefix: str, local: str, value: str) -> str:
	tag_pattern = re.compile(rf"<{prefix}:{local}[^>]*>[^<]*</{prefix}:{local}>", re.IGNORECASE)
	replacement = f"<{prefix}:{local}>{value}</{prefix}:{local}>"
	if tag_pattern.search(xmp):
		return tag_pattern.sub(replacement, xmp, count=1)
	insert_point = xmp.find("</rdf:Description>")
	if insert_point < 0:
		return xmp
	indent = "         "
	block = f"{indent}{replacement}\n"
	return xmp[:insert_point] + block + xmp[insert_point:]
