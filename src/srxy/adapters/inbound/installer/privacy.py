"""Privacy / third-party disclaimer for the desktop installer."""

from __future__ import annotations

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
_FFMPEG = ("ffmpeg", "https://ffmpeg.org/", "https://ffmpeg.org/")
_FFMPEG_BUILD = (
	"ffmpeg_build",
	"https://github.com/BtbN/FFmpeg-Builds",
	"https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement",
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


def _title_key(*, for_app: bool) -> str:
	return "privacy.app_title" if for_app else "privacy.title"


def privacy_disclaimer_text(*, for_app: bool = False) -> str:
	"""Plain-text notice (docs / fallbacks)."""
	parts = [
		tr(_title_key(for_app=for_app)),
		"",
		tr("privacy.intro_mit"),
		"",
		tr("privacy.intro_downloads"),
		"",
		tr("privacy.what_heading"),
		"",
		f"• {_plain_link(*_UV)}",
		f"• {_plain_link(*_PYPI)} — {tr('privacy.includes_qt')}:",
		f"  {_plain_link(*_QT)}",
		f"• {_plain_link(*_TESSERACT)}",
		f"• {_plain_link(*_TESSDATA)}",
		f"• {_plain_link(*_FFMPEG)}",
		f"• {_plain_link(*_FFMPEG_BUILD)}",
		f"• {tr('privacy.optional_ai')}:",
		f"  {_plain_link(*_PYTORCH)}",
		f"  {_plain_link(*_NVIDIA)}",
		f"  {_plain_link(*_NVIDIA_EULA)}",
		f"• {tr('privacy.optional_models', party=_party_label('hf'))}:",
		f"  {_plain_link(*_MODEL_TEXT)}",
		f"  {_plain_link(*_MODEL_CLIP)}",
		f"  {_plain_link(*_MODEL_FW)}",
		f"  {_plain_link(*_MODEL_WHISPER)}",
		"",
		tr("privacy.section_privacy"),
		"",
		f"• {tr('privacy.bullet_local')}",
		f"• {tr('privacy.bullet_third_party')}",
		f"• {tr('privacy.bullet_cache')}",
		"",
		tr("privacy.ack_footer"),
	]
	return "\n".join(parts)


def privacy_disclaimer_html(*, for_app: bool = False) -> str:
	"""Rich-text notice with clickable links for the installer / About UI."""
	parts = [
		f"<p><b>{escape(tr(_title_key(for_app=for_app)))}</b></p>",
		f"<p>{escape(tr('privacy.intro_mit'))}</p>",
		f"<p>{escape(tr('privacy.intro_downloads'))}</p>",
		f"<p><b>{escape(tr('privacy.what_heading'))}</b></p>",
		"<ul>",
		f"<li>{_html_link(*_UV)}</li>",
		f"<li>{_html_link(*_PYPI)} — {escape(tr('privacy.includes_qt'))}:<br/>{_html_link(*_QT)}</li>",
		f"<li>{_html_link(*_TESSERACT)}</li>",
		f"<li>{_html_link(*_TESSDATA)}</li>",
		f"<li>{_html_link(*_FFMPEG)}</li>",
		f"<li>{_html_link(*_FFMPEG_BUILD)}</li>",
		f"<li>{escape(tr('privacy.optional_ai'))}:<br/>"
		f"{_html_link(*_PYTORCH)}<br/>"
		f"{_html_link(*_NVIDIA)}<br/>"
		f"{_html_link(*_NVIDIA_EULA)}</li>",
		f"<li>{escape(tr('privacy.optional_models', party=_party_label('hf')))}:<br/>"
		f"{_html_link(*_MODEL_TEXT)}<br/>"
		f"{_html_link(*_MODEL_CLIP)}<br/>"
		f"{_html_link(*_MODEL_FW)}<br/>"
		f"{_html_link(*_MODEL_WHISPER)}</li>",
		"</ul>",
		f"<p><b>{escape(tr('privacy.section_privacy'))}</b></p>",
		"<ul>",
		f"<li>{escape(tr('privacy.bullet_local'))}</li>",
		f"<li>{escape(tr('privacy.bullet_third_party'))}</li>",
		f"<li>{escape(tr('privacy.bullet_cache'))}</li>",
		"</ul>",
		f"<p>{escape(tr('privacy.ack_footer'))}</p>",
	]
	return "\n".join(parts)


__all__ = [
	"privacy_disclaimer_html",
	"privacy_disclaimer_text",
]
