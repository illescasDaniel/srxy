from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from pathlib import Path

from srxy.image_formats import (
	DECODABLE_IMAGE_SUFFIXES,
	RAW_IMAGE_SUFFIXES,
	open_image,
	register_image_openers,
)


IMAGE_SUFFIXES = DECODABLE_IMAGE_SUFFIXES
ALL_IMAGE_SUFFIXES = IMAGE_SUFFIXES | RAW_IMAGE_SUFFIXES
AUDIO_SUFFIXES = frozenset({".mp3", ".flac", ".ogg", ".oga", ".opus", ".m4a", ".aac"})
VIDEO_SUFFIXES = frozenset({".mp4", ".m4v", ".mov"})
MEDIA_SUFFIXES = ALL_IMAGE_SUFFIXES | AUDIO_SUFFIXES | VIDEO_SUFFIXES

_EXIF_TAG_NAMES: dict[int, str] = {
	271: "Make",
	272: "Model",
	274: "Orientation",
	282: "XResolution",
	283: "YResolution",
	305: "Software",
	306: "DateTime",
	315: "Artist",
	33432: "Copyright",
	270: "ImageDescription",
	37510: "UserComment",
}

_MP4_ATOM_NAMES: dict[str, str] = {
	"\xa9nam": "Title",
	"\xa9ART": "Artist",
	"\xa9alb": "Album",
	"\xa9gen": "Genre",
	"\xa9day": "Date",
	"\xa9cmt": "Comment",
	"\xa9wrt": "Composer",
	"\xa9grp": "Grouping",
}

_SKIP_TAG_KEYS = frozenset({"\xa9too", "too", "encoder"})
_EXIFREAD_SKIP_PREFIXES = ("JPEGThumbnail", "Thumbnail", "MakerNote")
_XMP_INFO_KEYS = frozenset({"xmp", "xml:com.adobe.xmp"})
_XMP_XML_PREFIXES = ("<?x", "<x:xmpmeta", "<rdf:", "<xmp:")
_XMP_FIELD_LABELS: dict[str, str] = {
	"title": "Title",
	"description": "Description",
	"creator": "Creator",
	"subject": "Keywords",
	"headline": "Headline",
	"credit": "Credit",
	"source": "Source",
	"creatortool": "Software",
	"imagedescription": "ImageDescription",
}
_XMP_SKIP_LOCAL_NAMES = frozenset(
	{
		"format",
		"metadataDate",
		"modifyDate",
		"createDate",
		"instanceID",
		"documentID",
		"originalDocumentID",
		"history",
		"orientation",
		"colormode",
		"iccprofile",
		"action",
		"when",
		"changed",
		"softwareAgent",
		"seq",
		"li",
		"bag",
		"alt",
	}
)
_XMP_UUID_VALUE_RE = re.compile(r"^xmp\.(iid|did):", re.IGNORECASE)
_WINDOWS_XP_FIELD_NAMES: dict[str, str] = {
	"xpcomment": "Comment",
	"xptitle": "Title",
	"xpkeywords": "Keywords",
	"xpauthor": "Author",
}


def is_media_path(path: Path) -> bool:
	return path.suffix.lower() in MEDIA_SUFFIXES


def iter_media_metadata_lines(path: Path) -> Iterator[tuple[int, str]]:
	suffix = path.suffix.lower()
	extractors: dict[str, Callable[[Path], Iterator[tuple[int, str]]]] = {}
	for image_suffix in ALL_IMAGE_SUFFIXES:
		extractors[image_suffix] = _iter_image_metadata_lines
	for audio_suffix in AUDIO_SUFFIXES:
		extractors[audio_suffix] = _iter_audio_metadata_lines
	for video_suffix in VIDEO_SUFFIXES:
		extractors[video_suffix] = _iter_video_metadata_lines
	extractor = extractors.get(suffix)
	if extractor is None:
		return
	try:
		yield from extractor(path)
	except Exception:
		return


def _yield_tag_lines(tags: dict[str, str]) -> Iterator[tuple[int, str]]:
	line_number = 0
	for key in sorted(tags):
		if _should_skip_tag(key):
			continue
		value = tags[key].strip()
		if not value:
			continue
		line_number += 1
		yield line_number, f"[{_normalize_tag_key(key)}] {value}"


def _normalize_tag_key(key: str) -> str:
	if key in _MP4_ATOM_NAMES:
		return _MP4_ATOM_NAMES[key]
	normalized = key.strip()
	lowered = normalized.lower()
	if lowered in _WINDOWS_XP_FIELD_NAMES:
		return _WINDOWS_XP_FIELD_NAMES[lowered]
	if normalized.startswith("----:"):
		parts = normalized.split(":", 2)
		if len(parts) == 3:
			return parts[2]
	return normalized.replace("_", " ").title()


def _should_skip_tag(key: str) -> bool:
	if key in _SKIP_TAG_KEYS:
		return True
	return _normalize_tag_key(key).lower() in _SKIP_TAG_KEYS


def _decode_metadata_text(value: object) -> str | None:
	if value is None:
		return None
	if isinstance(value, bytes):
		for encoding in ("utf-16-le", "utf-16", "utf-8"):
			try:
				text = value.decode(encoding).strip("\x00").strip()
			except UnicodeDecodeError:
				continue
			else:
				if text:
					return text
		return None
	if isinstance(value, (tuple, list)):
		parts = [_decode_metadata_text(part) for part in value]
		joined = ", ".join(part for part in parts if part)
		return joined or None
	if isinstance(value, str):
		if "\x00" in value:
			try:
				text = value.encode("latin-1").decode("utf-16-le").strip("\x00").strip()
			except UnicodeDecodeError:
				text = value.replace("\x00", "").strip()
			return text or None
		text = value.strip()
		return text or None
	text = str(value).strip()
	return text or None


def _stringify_exif_value(value: object) -> str | None:
	return _decode_metadata_text(value)


def _format_gps_coordinates(gps_ifd: dict[int, object]) -> str | None:
	latitude = gps_ifd.get(2)
	latitude_ref = gps_ifd.get(1)
	longitude = gps_ifd.get(4)
	longitude_ref = gps_ifd.get(3)
	if not isinstance(latitude, tuple) or not isinstance(longitude, tuple):
		return None
	if not isinstance(latitude_ref, str) or not isinstance(longitude_ref, str):
		return None

	def _to_decimal(values: tuple[object, ...], reference: str) -> float | None:
		if len(values) != 3:
			return None
		degrees = _gps_component_to_float(values[0])
		minutes = _gps_component_to_float(values[1])
		seconds = _gps_component_to_float(values[2])
		if degrees is None or minutes is None or seconds is None:
			return None
		decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
		if reference in {"S", "W"}:
			decimal = -decimal
		return decimal

	lat = _to_decimal(latitude, latitude_ref)
	lon = _to_decimal(longitude, longitude_ref)
	if lat is None or lon is None:
		return None
	return f"{lat:.6f}, {lon:.6f}"


def _gps_component_to_float(value: object) -> float | None:
	if isinstance(value, bool):
		return None
	if isinstance(value, (int, float)):
		return float(value)
	numerator = getattr(value, "numerator", None)
	denominator = getattr(value, "denominator", None)
	if isinstance(numerator, int) and isinstance(denominator, int) and denominator != 0:
		return numerator / denominator
	try:
		return float(str(value))
	except ValueError:
		return None


def _collect_image_tags(path: Path) -> dict[str, str]:
	if path.suffix.lower() in RAW_IMAGE_SUFFIXES:
		try:
			return _collect_exifread_tags(path)
		except Exception:
			return {}

	try:
		return _collect_pillow_image_tags(path)
	except Exception:
		try:
			return _collect_exifread_tags(path)
		except Exception:
			return {}


def _collect_pillow_image_tags(path: Path) -> dict[str, str]:
	from PIL import ExifTags
	from PIL.ExifTags import IFD

	register_image_openers()
	tags: dict[str, str] = {}
	xmp_packets: list[str] = []
	with open_image(path) as image:
		for key, value in image.info.items():
			if not isinstance(key, str):
				continue
			if _is_xmp_info_key(key):
				packet = _coerce_xmp_packet(value)
				if packet:
					xmp_packets.append(packet)
				continue
			if isinstance(value, str) and value.strip():
				if _is_xmp_xml(value):
					xmp_packets.append(value.strip())
					continue
				decoded = _decode_metadata_text(value)
				if decoded:
					tags[_normalize_tag_key(key)] = decoded

		exif = image.getexif()
		if exif:
			for tag_id, raw_value in exif.items():
				name = _EXIF_TAG_NAMES.get(tag_id) or ExifTags.TAGS.get(tag_id)
				if not isinstance(name, str):
					continue
				value = _stringify_exif_value(raw_value)
				if value:
					tags[name] = value

			try:
				gps_ifd = exif.get_ifd(IFD.GPSInfo)
			except KeyError:
				gps_ifd = None
			if gps_ifd:
				gps = _format_gps_coordinates(gps_ifd)
				if gps:
					tags["GPS"] = gps

	for packet in xmp_packets:
		_merge_parsed_xmp_tags(tags, packet)

	return tags


def _is_xmp_info_key(key: str) -> bool:
	normalized = key.strip().lower()
	return normalized in _XMP_INFO_KEYS or normalized.endswith("xmp")


def _is_xmp_xml(text: str) -> bool:
	stripped = text.lstrip()
	return any(stripped.startswith(prefix) for prefix in _XMP_XML_PREFIXES)


def _coerce_xmp_packet(value: object) -> str | None:
	if isinstance(value, bytes):
		try:
			text = value.decode("utf-8").strip()
		except UnicodeDecodeError:
			return None
		return text or None
	if isinstance(value, str):
		text = value.strip()
		return text or None
	return None


def _should_skip_xmp_value(local_name: str, value: str) -> bool:
	if not value or not value.strip():
		return True
	if local_name.lower() in _XMP_SKIP_LOCAL_NAMES:
		return True
	if _XMP_UUID_VALUE_RE.match(value.strip()):
		return True
	if value.strip().isdigit():
		return True
	return False


def _parse_xmp_fields(xmp_xml: str) -> dict[str, str]:
	parsed: dict[str, list[str]] = {}
	pattern = re.compile(r"<([\w]+):([\w]+)[^>]*>([^<]+)</\1:\2>")
	for _prefix, local_name, raw_value in pattern.findall(xmp_xml):
		label = _XMP_FIELD_LABELS.get(local_name.lower())
		if label is None:
			continue
		value = raw_value.strip()
		if _should_skip_xmp_value(local_name, value):
			continue
		parsed.setdefault(label, []).append(value)

	result: dict[str, str] = {}
	for label, values in parsed.items():
		joined = ", ".join(dict.fromkeys(values))
		if joined:
			result[label] = joined
	return result


def _merge_parsed_xmp_tags(tags: dict[str, str], xmp_xml: str):
	for label, value in _parse_xmp_fields(xmp_xml).items():
		if _tag_value_present(tags, label, value):
			continue
		tags[label] = value


def _tag_value_present(tags: dict[str, str], label: str, value: str) -> bool:
	normalized = value.strip().lower()
	for existing_label, existing_value in tags.items():
		if existing_label == label and existing_value.strip().lower() == normalized:
			return True
		if existing_label == "Software" and label == "Software":
			if existing_value.strip().lower() == normalized:
				return True
		if existing_label == "ImageDescription" and label in {"Description", "ImageDescription"}:
			if existing_value.strip().lower() == normalized:
				return True
	return False


def _collect_exifread_tags(path: Path) -> dict[str, str]:
	import exifread

	tags: dict[str, str] = {}
	with path.open("rb") as handle:
		raw_tags = exifread.process_file(handle, details=False)
	for key, value in raw_tags.items():
		if _should_skip_exifread_key(key):
			continue
		name = _normalize_exifread_key(key)
		text = str(value).strip()
		if text:
			tags[name] = text
	return tags


def _should_skip_exifread_key(key: str) -> bool:
	return any(key.startswith(prefix) for prefix in _EXIFREAD_SKIP_PREFIXES)


def _normalize_exifread_key(key: str) -> str:
	for prefix in ("Image ", "EXIF ", "GPS ", "Interoperability "):
		if key.startswith(prefix):
			return key[len(prefix) :]
	return key


def _iter_image_metadata_lines(path: Path) -> Iterator[tuple[int, str]]:
	yield from _yield_tag_lines(_collect_image_tags(path))


def _collect_mutagen_tags(path: Path) -> dict[str, str]:
	suffix = path.suffix.lower()
	if suffix == ".mp3":
		return _collect_easyid3_tags(path)

	from mutagen import File as MutagenFile

	audio = MutagenFile(path, easy=True)
	if audio is None or not hasattr(audio, "tags") or audio.tags is None:
		return {}

	tags: dict[str, str] = {}
	for key, values in audio.tags.items():
		if values is None:
			continue
		if isinstance(values, list):
			text = ", ".join(str(value) for value in values if value is not None and str(value).strip())
		else:
			text = str(values)
		text = text.strip()
		if text:
			tags[_normalize_tag_key(str(key))] = text
	return tags


def _collect_easyid3_tags(path: Path) -> dict[str, str]:
	from mutagen.easyid3 import EasyID3
	from mutagen.id3 import ID3NoHeaderError

	try:
		audio = EasyID3(path)
	except ID3NoHeaderError:
		return {}

	tags: dict[str, str] = {}
	for key, values in audio.items():
		if values is None:
			continue
		text = ", ".join(str(value) for value in values if value is not None and str(value).strip())
		text = text.strip()
		if text:
			tags[_normalize_tag_key(str(key))] = text
	return tags


def _collect_mp4_tags(path: Path) -> dict[str, str]:
	from mutagen.mp4 import MP4

	tags: dict[str, str] = {}
	audio = MP4(path)
	if audio.tags is None:
		return tags

	for key, values in audio.tags.items():
		if values is None:
			continue
		if isinstance(values, list):
			text = ", ".join(str(value) for value in values if value is not None and str(value).strip())
		else:
			text = str(values)
		text = text.strip()
		if text:
			tags[_normalize_tag_key(str(key))] = text
	return tags


def _iter_audio_metadata_lines(path: Path) -> Iterator[tuple[int, str]]:
	yield from _yield_tag_lines(_collect_mutagen_tags(path))


def _iter_video_metadata_lines(path: Path) -> Iterator[tuple[int, str]]:
	yield from _yield_tag_lines(_collect_mp4_tags(path))
