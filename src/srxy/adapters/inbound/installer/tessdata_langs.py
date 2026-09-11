"""Tessdata language registry for installer OCR packs (tessdata 4.1.0)."""

from __future__ import annotations

import json
import locale
import os
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path

from srxy.adapters.inbound.installer.catalog import DownloadArtifact


TESSDATA_VERSION = "4.1.0"
REQUIRED_TESSDATA_LANGS: tuple[str, ...] = ("eng", "osd")

# ISO-ish UI / BCP-47 primary tags → tessdata codes.
_LOCALE_TO_TESSDATA: dict[str, str] = {
	"af": "afr",
	"am": "amh",
	"ar": "ara",
	"as": "asm",
	"az": "aze",
	"be": "bel",
	"bn": "ben",
	"bo": "bod",
	"bs": "bos",
	"br": "bre",
	"bg": "bul",
	"ca": "cat",
	"cs": "ces",
	"cy": "cym",
	"da": "dan",
	"de": "deu",
	"dv": "div",
	"dz": "dzo",
	"el": "ell",
	"en": "eng",
	"eo": "epo",
	"es": "spa",
	"et": "est",
	"eu": "eus",
	"fa": "fas",
	"fi": "fin",
	"fil": "fil",
	"fr": "fra",
	"ga": "gle",
	"gd": "gla",
	"gl": "glg",
	"gu": "guj",
	"he": "heb",
	"hi": "hin",
	"hr": "hrv",
	"hu": "hun",
	"hy": "hye",
	"id": "ind",
	"is": "isl",
	"it": "ita",
	"ja": "jpn",
	"jv": "jav",
	"ka": "kat",
	"kk": "kaz",
	"km": "khm",
	"kn": "kan",
	"ko": "kor",
	"ku": "kmr",
	"ky": "kir",
	"la": "lat",
	"lb": "ltz",
	"lo": "lao",
	"lt": "lit",
	"lv": "lav",
	"mi": "mri",
	"mk": "mkd",
	"ml": "mal",
	"mn": "mon",
	"mr": "mar",
	"ms": "msa",
	"mt": "mlt",
	"my": "mya",
	"ne": "nep",
	"nl": "nld",
	"no": "nor",
	"nb": "nor",
	"nn": "nor",
	"oc": "oci",
	"or": "ori",
	"pa": "pan",
	"pl": "pol",
	"ps": "pus",
	"pt": "por",
	"qu": "que",
	"ro": "ron",
	"ru": "rus",
	"sa": "san",
	"sd": "snd",
	"si": "sin",
	"sk": "slk",
	"sl": "slv",
	"sq": "sqi",
	"sr": "srp",
	"sv": "swe",
	"sw": "swa",
	"ta": "tam",
	"te": "tel",
	"tg": "tgk",
	"th": "tha",
	"ti": "tir",
	"tl": "tgl",
	"tr": "tur",
	"tt": "tat",
	"ug": "uig",
	"uk": "ukr",
	"ur": "urd",
	"uz": "uzb",
	"vi": "vie",
	"yi": "yid",
	"yo": "yor",
	"zh": "chi_sim",
}

# Human labels for installer checkboxes (English). Unknown codes fall back to the code.
_DISPLAY_NAMES: dict[str, str] = {
	"afr": "Afrikaans",
	"amh": "Amharic",
	"ara": "Arabic",
	"asm": "Assamese",
	"aze": "Azerbaijani",
	"aze_cyrl": "Azerbaijani (Cyrillic)",
	"bel": "Belarusian",
	"ben": "Bengali",
	"bod": "Tibetan",
	"bos": "Bosnian",
	"bre": "Breton",
	"bul": "Bulgarian",
	"cat": "Catalan",
	"ceb": "Cebuano",
	"ces": "Czech",
	"chi_sim": "Chinese (Simplified)",
	"chi_sim_vert": "Chinese (Simplified, vertical)",
	"chi_tra": "Chinese (Traditional)",
	"chi_tra_vert": "Chinese (Traditional, vertical)",
	"chr": "Cherokee",
	"cos": "Corsican",
	"cym": "Welsh",
	"dan": "Danish",
	"dan_frak": "Danish (Fraktur)",
	"deu": "German",
	"deu_frak": "German (Fraktur)",
	"div": "Dhivehi",
	"dzo": "Dzongkha",
	"ell": "Greek",
	"eng": "English",
	"enm": "English (Middle)",
	"epo": "Esperanto",
	"est": "Estonian",
	"eus": "Basque",
	"fao": "Faroese",
	"fas": "Persian",
	"fil": "Filipino",
	"fin": "Finnish",
	"fra": "French",
	"frk": "Frankish",
	"frm": "French (Middle)",
	"fry": "Frisian",
	"gla": "Scottish Gaelic",
	"gle": "Irish",
	"glg": "Galician",
	"grc": "Greek (Ancient)",
	"guj": "Gujarati",
	"hat": "Haitian",
	"heb": "Hebrew",
	"hin": "Hindi",
	"hrv": "Croatian",
	"hun": "Hungarian",
	"hye": "Armenian",
	"iku": "Inuktitut",
	"ind": "Indonesian",
	"isl": "Icelandic",
	"ita": "Italian",
	"ita_old": "Italian (Old)",
	"jav": "Javanese",
	"jpn": "Japanese",
	"jpn_vert": "Japanese (vertical)",
	"kan": "Kannada",
	"kat": "Georgian",
	"kat_old": "Georgian (Old)",
	"kaz": "Kazakh",
	"khm": "Khmer",
	"kir": "Kyrgyz",
	"kmr": "Kurmanji (Kurdish)",
	"kor": "Korean",
	"kor_vert": "Korean (vertical)",
	"lao": "Lao",
	"lat": "Latin",
	"lav": "Latvian",
	"lit": "Lithuanian",
	"ltz": "Luxembourgish",
	"mal": "Malayalam",
	"mar": "Marathi",
	"mkd": "Macedonian",
	"mlt": "Maltese",
	"mon": "Mongolian",
	"mri": "Maori",
	"msa": "Malay",
	"mya": "Burmese",
	"nep": "Nepali",
	"nld": "Dutch",
	"nor": "Norwegian",
	"oci": "Occitan",
	"ori": "Odia",
	"osd": "Orientation detection",
	"pan": "Punjabi",
	"pol": "Polish",
	"por": "Portuguese",
	"pus": "Pashto",
	"que": "Quechua",
	"ron": "Romanian",
	"rus": "Russian",
	"san": "Sanskrit",
	"sin": "Sinhala",
	"slk": "Slovak",
	"slk_frak": "Slovak (Fraktur)",
	"slv": "Slovenian",
	"snd": "Sindhi",
	"spa": "Spanish",
	"spa_old": "Spanish (Old)",
	"sqi": "Albanian",
	"srp": "Serbian",
	"srp_latn": "Serbian (Latin)",
	"sun": "Sundanese",
	"swa": "Swahili",
	"swe": "Swedish",
	"syr": "Syriac",
	"tam": "Tamil",
	"tat": "Tatar",
	"tel": "Telugu",
	"tgk": "Tajik",
	"tgl": "Tagalog",
	"tha": "Thai",
	"tir": "Tigrinya",
	"ton": "Tonga",
	"tur": "Turkish",
	"uig": "Uyghur",
	"ukr": "Ukrainian",
	"urd": "Urdu",
	"uzb": "Uzbek",
	"uzb_cyrl": "Uzbek (Cyrillic)",
	"vie": "Vietnamese",
	"yid": "Yiddish",
	"yor": "Yoruba",
}


@dataclass(frozen=True, slots=True)
class TessdataLanguage:
	code: str
	display_name: str
	bytes_size: int
	required: bool


@lru_cache(maxsize=1)
def _checksums_payload() -> dict[str, object]:
	raw = (
		resources.files("srxy.adapters.inbound.installer")
		.joinpath("tessdata_checksums.json")
		.read_text(encoding="utf-8")
	)
	payload = json.loads(raw)
	if not isinstance(payload, dict):
		raise RuntimeError("invalid tessdata_checksums.json")
	return payload


def tessdata_commit() -> str:
	commit = _checksums_payload().get("commit")
	if not isinstance(commit, str) or not commit:
		raise RuntimeError("tessdata commit missing from checksums")
	return commit


def tessdata_sha256(code: str) -> str:
	sha_map = _checksums_payload().get("sha256")
	if not isinstance(sha_map, dict):
		raise KeyError(code)
	digest = sha_map.get(code)
	if not isinstance(digest, str) or not digest:
		raise KeyError(code)
	return digest


def tessdata_bytes(code: str) -> int:
	size_map = _checksums_payload().get("bytes")
	if not isinstance(size_map, dict):
		return 0
	raw = size_map.get(code, 0)
	return int(raw) if isinstance(raw, int | float | str) else 0


def is_selectable_tessdata_code(code: str) -> bool:
	"""Spoken / OCR language packs shown in installers (excludes script/* and equ)."""
	if not code or "/" in code or code == "equ":
		return False
	sha_map = _checksums_payload().get("sha256", {})
	return isinstance(sha_map, dict) and code in sha_map


def tessdata_display_name(code: str) -> str:
	if code == "osd":
		return _DISPLAY_NAMES["osd"]
	return _DISPLAY_NAMES.get(code, code)


def selectable_tessdata_languages() -> tuple[TessdataLanguage, ...]:
	sha_map = _checksums_payload().get("sha256")
	if not isinstance(sha_map, dict):
		return ()
	langs: list[TessdataLanguage] = []
	for code in sorted(sha_map):
		if not isinstance(code, str) or not is_selectable_tessdata_code(code):
			continue
		langs.append(
			TessdataLanguage(
				code=code,
				display_name=tessdata_display_name(code),
				bytes_size=tessdata_bytes(code),
				required=code in REQUIRED_TESSDATA_LANGS,
			)
		)
	return tuple(langs)


def locale_to_tessdata(tag: str) -> str | None:
	primary = tag.strip().lower().replace("_", "-").split("-", 1)[0]
	if not primary:
		return None
	code = _LOCALE_TO_TESSDATA.get(primary)
	if code is None:
		return None
	if not is_selectable_tessdata_code(code) and code != "osd":
		return None
	return code


def system_preferred_locale_tags() -> tuple[str, ...]:
	"""OS preferred locale tags from LANGUAGE, getlocale, LANG/LC_ALL (Qt-free)."""
	ordered: list[str] = []
	seen: set[str] = set()

	def _add(raw: str):
		tag = raw.strip()
		if not tag:
			return
		# Drop charset/modifier suffixes: es_ES.UTF-8@euro → es_ES
		tag = tag.split(".", 1)[0].split("@", 1)[0]
		if not tag or tag in {"C", "POSIX"}:
			return
		if tag in seen:
			return
		ordered.append(tag)
		seen.add(tag)

	for part in os.environ.get("LANGUAGE", "").split(":"):
		_add(part)
	try:
		loc = locale.getlocale()[0]
		if loc:
			_add(loc)
	except (TypeError, ValueError):
		pass
	for key in ("LANG", "LC_ALL"):
		_add(os.environ.get(key, ""))
	return tuple(ordered)


def default_tessdata_langs(*locale_tags: str) -> tuple[str, ...]:
	"""eng + osd + every mapped locale tag (deduped, stable order)."""
	ordered: list[str] = []
	seen: set[str] = set()
	for code in REQUIRED_TESSDATA_LANGS:
		ordered.append(code)
		seen.add(code)
	for tag in locale_tags:
		mapped = locale_to_tessdata(tag)
		if mapped is None or mapped in seen:
			continue
		ordered.append(mapped)
		seen.add(mapped)
	return tuple(ordered)


def normalize_tessdata_langs(codes: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
	ordered: list[str] = []
	seen: set[str] = set()
	for code in REQUIRED_TESSDATA_LANGS:
		ordered.append(code)
		seen.add(code)
	if codes:
		for raw in codes:
			code = raw.strip().lower()
			if not code or code in seen:
				continue
			if code == "osd":
				continue
			if not is_selectable_tessdata_code(code):
				raise ValueError(f"unknown tessdata language: {raw}")
			ordered.append(code)
			seen.add(code)
	return tuple(ordered)


def tessdata_url(code: str) -> str:
	commit = tessdata_commit()
	# script/* packs live under a subdirectory in the tessdata repo.
	return f"https://raw.githubusercontent.com/tesseract-ocr/tessdata/{commit}/{code}.traineddata"


def tessdata_artifact(code: str) -> DownloadArtifact:
	return DownloadArtifact(
		name=f"tessdata_{code.replace('/', '_')}",
		version=TESSDATA_VERSION,
		url=tessdata_url(code),
		sha256=tessdata_sha256(code),
		kind="file",
		notes=f"Tesseract tessdata {TESSDATA_VERSION} pack '{code}' (Apache-2.0).",
	)


def tessdata_dest_path(tessdata_dir: Path, code: str) -> Path:
	return tessdata_dir / f"{code}.traineddata"


__all__ = [
	"REQUIRED_TESSDATA_LANGS",
	"TESSDATA_VERSION",
	"TessdataLanguage",
	"default_tessdata_langs",
	"is_selectable_tessdata_code",
	"locale_to_tessdata",
	"normalize_tessdata_langs",
	"selectable_tessdata_languages",
	"system_preferred_locale_tags",
	"tessdata_artifact",
	"tessdata_bytes",
	"tessdata_commit",
	"tessdata_dest_path",
	"tessdata_display_name",
	"tessdata_sha256",
	"tessdata_url",
]
