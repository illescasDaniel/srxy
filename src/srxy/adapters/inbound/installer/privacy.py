"""Privacy / third-party disclaimer for the desktop installer."""

from __future__ import annotations

import platform
from html import escape

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
PRIVACY_NOTICE_VERSION = "2"


def _copy_key(stem: str, *, for_app: bool) -> str:
	"""Pick installer vs in-app catalog key for shared privacy prose."""
	if stem == "title":
		return "privacy.app_title" if for_app else "privacy.title"
	return f"privacy.app_{stem}" if for_app else f"privacy.{stem}"


def _vendor_source_parties(*, for_app: bool, system: str | None = None) -> list[Party]:
	"""OS-specific vendor download sources for the installer; full set for in-app."""
	host = (system or platform.system()).lower()
	if for_app:
		return [_TESSERACT_LINUX, _TESSERACT_MACOS, _FFMPEG_BUILD, _FFMPEG_MACOS]
	if host == "darwin":
		return [_TESSERACT_MACOS, _FFMPEG_MACOS]
	if host == "linux":
		return [_TESSERACT_LINUX, _FFMPEG_BUILD]
	return []


def _download_party_lines(*, for_app: bool, html: bool) -> list[str]:
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
	for party in _vendor_source_parties(for_app=for_app):
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


def privacy_disclaimer_text(*, for_app: bool = False) -> str:
	"""Plain-text notice (docs / fallbacks)."""
	parts = [
		tr(_copy_key("title", for_app=for_app)),
		"",
		tr(_copy_key("intro_mit", for_app=for_app)),
		"",
		tr(_copy_key("intro_downloads", for_app=for_app)),
		"",
		tr(_copy_key("what_heading", for_app=for_app)),
		"",
		*_download_party_lines(for_app=for_app, html=False),
		"",
		tr("privacy.section_privacy"),
		"",
		f"• {tr('privacy.bullet_local')}",
		f"• {tr('privacy.bullet_third_party')}",
		f"• {tr('privacy.bullet_cache')}",
		"",
		tr(_copy_key("ack_footer", for_app=for_app)),
	]
	return "\n".join(parts)


def privacy_disclaimer_html(*, for_app: bool = False) -> str:
	"""Rich-text notice with clickable links for the installer / About UI."""
	parts = [
		f"<p><b>{escape(tr(_copy_key('title', for_app=for_app)))}</b></p>",
		f"<p>{escape(tr(_copy_key('intro_mit', for_app=for_app)))}</p>",
		f"<p>{escape(tr(_copy_key('intro_downloads', for_app=for_app)))}</p>",
		f"<p><b>{escape(tr(_copy_key('what_heading', for_app=for_app)))}</b></p>",
		"<ul>",
		*_download_party_lines(for_app=for_app, html=True),
		"</ul>",
		f"<p><b>{escape(tr('privacy.section_privacy'))}</b></p>",
		"<ul>",
		f"<li>{escape(tr('privacy.bullet_local'))}</li>",
		f"<li>{escape(tr('privacy.bullet_third_party'))}</li>",
		f"<li>{escape(tr('privacy.bullet_cache'))}</li>",
		"</ul>",
		f"<p>{escape(tr(_copy_key('ack_footer', for_app=for_app)))}</p>",
	]
	return "\n".join(parts)


__all__ = [
	"PRIVACY_NOTICE_VERSION",
	"privacy_disclaimer_html",
	"privacy_disclaimer_text",
]
