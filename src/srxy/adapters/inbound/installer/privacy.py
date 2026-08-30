"""Privacy / third-party disclaimer for the desktop installer."""

from __future__ import annotations

import platform
from html import escape
from pathlib import Path

from srxy.i18n import tr


# Official sites and privacy policies for third-party downloads.
# (stable name key, url, privacy_url)
_UV = ("uv", "https://docs.astral.sh/uv/", "https://astral.sh/privacy-policy")
_PYPI = ("pypi", "https://pypi.org/", "https://policies.python.org/pypi.org/Privacy-Notice/")
_QT = ("qt", "https://www.qt.io/", "https://www.qt.io/terms-conditions/privacy-policy")
_TESSERACT = (
	"tesseract",
	"https://github.com/tesseract-ocr/tesseract",
	"https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement",
)
_TESSDATA = (
	"tessdata",
	"https://github.com/tesseract-ocr/tessdata",
	"https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement",
)
_TESSERACT_LINUX = (
	"tesseract_linux",
	"https://github.com/DanielMYT/tesseract-static",
	"https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement",
)
_TESSERACT_MACOS = (
	"tesseract_macos",
	"https://formulae.brew.sh/formula/tesseract",
	"https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement",
)
_TESSERACT_WINDOWS = (
	"tesseract_windows",
	"https://github.com/UB-Mannheim/tesseract",
	"https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement",
)
_SEVENZIP = (
	"sevenzip",
	"https://www.7-zip.org/",
	"https://www.7-zip.org/",
)
_FFMPEG = ("ffmpeg", "https://ffmpeg.org/", "https://ffmpeg.org/")
_FFMPEG_BUILD = (
	"ffmpeg_build",
	"https://github.com/BtbN/FFmpeg-Builds",
	"https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement",
)
_FFMPEG_MACOS = (
	"ffmpeg_macos",
	"https://ffmpeg.martin-riedl.de/",
	"https://ffmpeg.org/",
)
_PYTORCH = ("pytorch", "https://pytorch.org/", "https://www.linuxfoundation.org/legal/privacy")
_NVIDIA = (
	"nvidia",
	"https://developer.nvidia.com/cuda-zone",
	"https://www.nvidia.com/en-us/about-nvidia/privacy-policy/",
)
_NVIDIA_EULA = (
	"nvidia_eula",
	"https://docs.nvidia.com/cuda/eula/index.html",
	"https://www.nvidia.com/en-us/about-nvidia/privacy-policy/",
)
_HF = ("hf", "https://huggingface.co/", "https://huggingface.co/privacy")
_MODEL_TEXT = (
	"model_text",
	"https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
	"https://huggingface.co/privacy",
)
_MODEL_CLIP = (
	"model_clip",
	"https://huggingface.co/sentence-transformers/clip-ViT-B-32",
	"https://huggingface.co/privacy",
)
_MODEL_FW = (
	"model_fw",
	"https://huggingface.co/Systran/faster-whisper-base",
	"https://huggingface.co/privacy",
)
_MODEL_WHISPER = (
	"model_whisper",
	"https://huggingface.co/openai/whisper-base",
	"https://huggingface.co/privacy",
)

Party = tuple[str, str, str]
# (stable i18n key, display name, project url)
Dep = tuple[str, str, str]

_CORE_DEPS: tuple[Dep, ...] = (
	("cryptography", "cryptography", "https://cryptography.io/"),
	("exifread", "exifread", "https://github.com/ianare/exif-py"),
	("jellyfish", "jellyfish", "https://github.com/jamesturk/jellyfish"),
	("mutagen", "mutagen", "https://mutagen.readthedocs.io/"),
	("openpyxl", "openpyxl", "https://openpyxl.readthedocs.io/"),
	("pillow", "Pillow", "https://python-pillow.org/"),
	("pillow_heif", "pillow-heif", "https://github.com/bigcat88/pillow_heif"),
	("pypdf", "pypdf", "https://pypdf.readthedocs.io/"),
	("pytesseract", "pytesseract", "https://github.com/madmaze/pytesseract"),
	("pyside6", "PySide6", "https://doc.qt.io/qtforpython/"),
	("python_docx", "python-docx", "https://python-docx.readthedocs.io/"),
	("python_pptx", "python-pptx", "https://python-pptx.readthedocs.io/"),
	("pywin32", "pywin32", "https://github.com/mhammond/pywin32"),
	("rapidfuzz", "rapidfuzz", "https://github.com/rapidfuzz/RapidFuzz"),
	("textual", "textual", "https://textual.textualize.io/"),
	("wordfreq", "wordfreq", "https://github.com/rspeer/wordfreq"),
)

_SEMANTIC_DEPS: tuple[Dep, ...] = (
	("faster_whisper", "faster-whisper", "https://github.com/SYSTRAN/faster-whisper"),
	("nvidia_cublas", "nvidia-cublas-cu12", "https://developer.nvidia.com/cublas"),
	("rawpy", "rawpy", "https://github.com/letmaik/rawpy"),
	("sentence_transformers", "sentence-transformers", "https://www.sbert.net/"),
)


def _party_label(key: str) -> str:
	return tr(f"privacy.party.{key}")


def _plain_link(key: str, url: str, privacy: str) -> str:
	label = _party_label(key)
	site = tr("privacy.label.site")
	priv = tr("privacy.label.privacy")
	return f"{label}\n    {site}: {url}\n    {priv}: {privacy}"


def _html_link(key: str, url: str, privacy: str) -> str:
	label = escape(_party_label(key))
	site = escape(tr("privacy.label.site"))
	priv = escape(tr("privacy.label.privacy"))
	return (
		f"{label}<br/>"
		f'&nbsp;&nbsp;{site}: <a href="{escape(url, quote=True)}">{escape(url)}</a><br/>'
		f'&nbsp;&nbsp;{priv}: <a href="{escape(privacy, quote=True)}">{escape(privacy)}</a>'
	)


# Bump when ack'd notice content changes so users re-acknowledge.
PRIVACY_NOTICE_VERSION = "7"


def _vendor_source_parties(*, system: str | None = None) -> list[Party]:
	"""OS-specific vendor download sources for the current platform."""
	host = (system or platform.system()).lower()
	if host == "darwin":
		return [_TESSERACT_MACOS, _FFMPEG_MACOS]
	if host == "linux":
		return [_TESSERACT_LINUX, _FFMPEG_BUILD]
	if host == "windows":
		return [_TESSERACT_WINDOWS, _SEVENZIP, _FFMPEG_BUILD]
	return []


def _download_party_lines(*, html: bool) -> list[str]:
	link = _html_link if html else _plain_link
	bullet = "<li>" if html else "• "
	end = "</li>" if html else ""
	indent = "" if html else "  "
	sep = "<br/>" if html else "\n"

	lines = [
		f"{bullet}{link(*_UV)}{end}",
		(
			f"{bullet}{link(*_PYPI)} — {escape(tr('privacy.includes_qt')) if html else tr('privacy.includes_qt')}:"
			f"{sep}{indent}{link(*_QT)}{end}"
		),
		f"{bullet}{link(*_TESSERACT)}{end}",
		f"{bullet}{link(*_TESSDATA)}{end}",
		f"{bullet}{link(*_FFMPEG)}{end}",
	]
	for party in _vendor_source_parties():
		lines.append(f"{bullet}{link(*party)}{end}")
	ai_label = escape(tr("privacy.optional_ai")) if html else tr("privacy.optional_ai")
	models_label = (
		escape(tr("privacy.optional_models", party=_party_label("hf")))
		if html
		else tr("privacy.optional_models", party=_party_label("hf"))
	)
	if html:
		lines.append(f"<li>{ai_label}:<br/>{link(*_PYTORCH)}<br/>{link(*_NVIDIA)}<br/>{link(*_NVIDIA_EULA)}</li>")
		lines.append(
			f"<li>{models_label}:<br/>"
			f"{link(*_MODEL_TEXT)}<br/>"
			f"{link(*_MODEL_CLIP)}<br/>"
			f"{link(*_MODEL_FW)}<br/>"
			f"{link(*_MODEL_WHISPER)}</li>"
		)
	else:
		lines.extend(
			[
				f"• {ai_label}:",
				f"  {link(*_PYTORCH)}",
				f"  {link(*_NVIDIA)}",
				f"  {link(*_NVIDIA_EULA)}",
				f"• {models_label}:",
				f"  {link(*_MODEL_TEXT)}",
				f"  {link(*_MODEL_CLIP)}",
				f"  {link(*_MODEL_FW)}",
				f"  {link(*_MODEL_WHISPER)}",
			]
		)
	return lines


def _plain_dep(key: str, name: str, url: str) -> str:
	use = tr(f"privacy.dep.use.{key}")
	project = tr("privacy.label.project")
	return f"{name} — {use}\n    {project}: {url}"


def _html_dep(key: str, name: str, url: str) -> str:
	use = escape(tr(f"privacy.dep.use.{key}"))
	project = escape(tr("privacy.label.project"))
	return f'{escape(name)} — {use}<br/>&nbsp;&nbsp;{project}: <a href="{escape(url, quote=True)}">{escape(url)}</a>'


def _dep_group_lines(*, html: bool, heading_key: str, deps: tuple[Dep, ...]) -> list[str]:
	fmt = _html_dep if html else _plain_dep
	heading = escape(tr(heading_key)) if html else tr(heading_key)
	if html:
		lines = [f"<li><b>{heading}</b><ul>"]
		for dep in deps:
			lines.append(f"<li>{fmt(*dep)}</li>")
		lines.append("</ul></li>")
		return lines
	lines = [f"• {heading}"]
	for dep in deps:
		for part in fmt(*dep).split("\n"):
			lines.append(f"  {part}")
	return lines


def _library_section_lines(*, html: bool) -> list[str]:
	"""Direct runtime libraries (via PyPI) with project links and brief uses."""
	if html:
		parts = [
			f"<p><b>{escape(tr('privacy.deps_heading'))}</b></p>",
			f"<p>{escape(tr('privacy.deps_intro'))}</p>",
			"<ul>",
			*_dep_group_lines(html=True, heading_key="privacy.deps_core_heading", deps=_CORE_DEPS),
			*_dep_group_lines(html=True, heading_key="privacy.deps_semantic_heading", deps=_SEMANTIC_DEPS),
			"</ul>",
		]
		return parts
	parts = [
		tr("privacy.deps_heading"),
		"",
		tr("privacy.deps_intro"),
		"",
		*_dep_group_lines(html=False, heading_key="privacy.deps_core_heading", deps=_CORE_DEPS),
		"",
		*_dep_group_lines(html=False, heading_key="privacy.deps_semantic_heading", deps=_SEMANTIC_DEPS),
	]
	return parts


def privacy_disclaimer_text(*, language: str | None = None) -> str:
	"""Plain-text notice (docs / fallbacks).

	When ``language`` is set, temporarily switch the active catalog for this call.
	"""
	from srxy.i18n import get_language, set_language

	previous: str | None = None
	if language is not None:
		previous = get_language()
		set_language(language)
	try:
		parts = [
			tr("privacy.title"),
			"",
			tr("privacy.intro_mit"),
			"",
			tr("privacy.intro_downloads"),
			"",
			tr("privacy.what_heading"),
			"",
			*_download_party_lines(html=False),
			"",
			*_library_section_lines(html=False),
			"",
			tr("privacy.section_privacy"),
			"",
			f"• {tr('privacy.bullet_local')}",
			f"• {tr('privacy.bullet_third_party')}",
			f"• {tr('privacy.bullet_cache')}",
			"",
			tr("privacy.section_disclaimer"),
			"",
			f"• {tr('privacy.bullet_warranty')}",
			"",
			tr("privacy.ack_footer"),
		]
		return "\n".join(parts)
	finally:
		if previous is not None:
			set_language(previous)


def write_privacy_notice_utf8(path: Path, *, language: str):
	"""Write a UTF-8 privacy notice with BOM (Inno Setup LoadStringsFromFile-friendly)."""
	text = privacy_disclaimer_text(language=language)
	path.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))


def privacy_disclaimer_html() -> str:
	"""Rich-text notice with clickable links for the installer / About UI."""
	parts = [
		f"<p><b>{escape(tr('privacy.title'))}</b></p>",
		f"<p>{escape(tr('privacy.intro_mit'))}</p>",
		f"<p>{escape(tr('privacy.intro_downloads'))}</p>",
		f"<p><b>{escape(tr('privacy.what_heading'))}</b></p>",
		"<ul>",
		*_download_party_lines(html=True),
		"</ul>",
		*_library_section_lines(html=True),
		f"<p><b>{escape(tr('privacy.section_privacy'))}</b></p>",
		"<ul>",
		f"<li>{escape(tr('privacy.bullet_local'))}</li>",
		f"<li>{escape(tr('privacy.bullet_third_party'))}</li>",
		f"<li>{escape(tr('privacy.bullet_cache'))}</li>",
		"</ul>",
		f"<p><b>{escape(tr('privacy.section_disclaimer'))}</b></p>",
		"<ul>",
		f"<li>{escape(tr('privacy.bullet_warranty'))}</li>",
		"</ul>",
		f"<p>{escape(tr('privacy.ack_footer'))}</p>",
	]
	return "\n".join(parts)


__all__ = [
	"PRIVACY_NOTICE_VERSION",
	"privacy_disclaimer_html",
	"privacy_disclaimer_text",
	"write_privacy_notice_utf8",
]
