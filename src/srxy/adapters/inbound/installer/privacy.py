"""Privacy / third-party disclaimer for the desktop installer."""

from __future__ import annotations

from html import escape


# Official sites and privacy policies for third-party downloads.
_UV = ("Astral uv", "https://docs.astral.sh/uv/", "https://astral.sh/privacy-policy")
_PYPI = (
	"Python Package Index (PyPI)",
	"https://pypi.org/",
	"https://policies.python.org/pypi.org/Privacy-Notice/",
)
_QT = ("Qt / PySide6", "https://www.qt.io/", "https://www.qt.io/terms-conditions/privacy-policy")
_TESSERACT = (
	"Tesseract OCR",
	"https://github.com/tesseract-ocr/tesseract",
	"https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement",
)
_TESSDATA = (
	"Tesseract language data (tessdata)",
	"https://github.com/tesseract-ocr/tessdata",
	"https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement",
)
_FFMPEG = ("ffmpeg", "https://ffmpeg.org/", "https://ffmpeg.org/")
_FFMPEG_BUILD = (
	"ffmpeg Linux builds (BtbN)",
	"https://github.com/BtbN/FFmpeg-Builds",
	"https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement",
)
_PYTORCH = (
	"PyTorch",
	"https://pytorch.org/",
	"https://www.linuxfoundation.org/legal/privacy",
)
_NVIDIA = (
	"NVIDIA CUDA",
	"https://developer.nvidia.com/cuda-zone",
	"https://www.nvidia.com/en-us/about-nvidia/privacy-policy/",
)
_NVIDIA_EULA = (
	"NVIDIA CUDA EULA",
	"https://docs.nvidia.com/cuda/eula/index.html",
	"https://www.nvidia.com/en-us/about-nvidia/privacy-policy/",
)
_HF = (
	"Hugging Face",
	"https://huggingface.co/",
	"https://huggingface.co/privacy",
)
_MODEL_TEXT = (
	"paraphrase-multilingual-MiniLM-L12-v2 (similar meaning)",
	"https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
	"https://huggingface.co/privacy",
)
_MODEL_CLIP = (
	"clip-ViT-B-32 (visual description)",
	"https://huggingface.co/sentence-transformers/clip-ViT-B-32",
	"https://huggingface.co/privacy",
)
_MODEL_FW = (
	"faster-whisper-base (spoken words)",
	"https://huggingface.co/Systran/faster-whisper-base",
	"https://huggingface.co/privacy",
)
_MODEL_WHISPER = (
	"openai/whisper-base (spoken words, Apple MPS path)",
	"https://huggingface.co/openai/whisper-base",
	"https://huggingface.co/privacy",
)


def _plain_link(label: str, url: str, privacy: str) -> str:
	return f"{label}\n    Site: {url}\n    Privacy: {privacy}"


def _html_link(label: str, url: str, privacy: str) -> str:
	safe_label = escape(label)
	return (
		f"{safe_label}<br/>"
		f'&nbsp;&nbsp;Site: <a href="{escape(url, quote=True)}">{escape(url)}</a><br/>'
		f'&nbsp;&nbsp;Privacy: <a href="{escape(privacy, quote=True)}">{escape(privacy)}</a>'
	)


def privacy_disclaimer_text() -> str:
	"""Plain-text notice (docs / fallbacks)."""
	parts = [
		"srxy desktop installer — privacy & third-party notice",
		"",
		"srxy itself is MIT-licensed. This installer is an optional desktop distribution "
		"channel; you can still install srxy from PyPI and use the GUI, TUI, CLI, or "
		"library without this installer.",
		"",
		"This AppImage does not embed NVIDIA/CUDA binaries, Hugging Face model weights, "
		"Tesseract, or ffmpeg. When you opt in, the installer downloads components from "
		"third parties. Please review their sites and privacy policies before continuing.",
		"",
		"What this installer may download (only after you choose the related options):",
		"",
		f"• {_plain_link(*_UV)}",
		f"• {_plain_link(*_PYPI)} — includes PySide6 / Qt (LGPL):",
		f"  {_plain_link(*_QT)}",
		f"• {_plain_link(*_TESSERACT)}",
		f"• {_plain_link(*_TESSDATA)}",
		f"• {_plain_link(*_FFMPEG)}",
		f"• {_plain_link(*_FFMPEG_BUILD)}",
		"• Optional AI search extras from PyPI:",
		f"  {_plain_link(*_PYTORCH)}",
		f"  {_plain_link(*_NVIDIA)}",
		f"  {_plain_link(*_NVIDIA_EULA)}",
		f"• Optional AI models via {_plain_link(*_HF)} — default model cards:",
		f"  {_plain_link(*_MODEL_TEXT)}",
		f"  {_plain_link(*_MODEL_CLIP)}",
		f"  {_plain_link(*_MODEL_FW)}",
		f"  {_plain_link(*_MODEL_WHISPER)}",
		"",
		"Privacy:",
		"",
		"• srxy searches files on your machine. It does not upload your files to a remote srxy search service.",
		"• Choosing downloads contacts third-party servers listed above. Those parties "
		"have their own privacy policies (linked above).",
		"• Cached models, OCR results, and embeddings stay under your install prefix "
		"(SRXY_HOME) or ~/.cache/srxy for non-prefix installs.",
		"",
		"By checking the acknowledgment box you confirm you understand these third-party "
		"downloads and accept responsibility for complying with their licenses and "
		"privacy policies.",
	]
	return "\n".join(parts)


def privacy_disclaimer_html() -> str:
	"""Rich-text notice with clickable links for the installer UI."""
	parts = [
		"<p><b>srxy desktop installer — privacy &amp; third-party notice</b></p>",
		"<p>srxy itself is MIT-licensed. This installer is an optional desktop "
		"distribution channel; you can still install srxy from PyPI and use the GUI, "
		"TUI, CLI, or library without this installer.</p>",
		"<p>This AppImage does not embed NVIDIA/CUDA binaries, Hugging Face model "
		"weights, Tesseract, or ffmpeg. When you opt in, the installer downloads "
		"components from third parties. Please review their sites and privacy policies "
		"before continuing.</p>",
		"<p><b>What this installer may download</b> (only after you choose the related options):</p>",
		"<ul>",
		f"<li>{_html_link(*_UV)}</li>",
		f"<li>{_html_link(*_PYPI)} — includes PySide6 / Qt (LGPL):<br/>{_html_link(*_QT)}</li>",
		f"<li>{_html_link(*_TESSERACT)}</li>",
		f"<li>{_html_link(*_TESSDATA)}</li>",
		f"<li>{_html_link(*_FFMPEG)}</li>",
		f"<li>{_html_link(*_FFMPEG_BUILD)}</li>",
		"<li>Optional AI search extras from PyPI:<br/>"
		f"{_html_link(*_PYTORCH)}<br/>"
		f"{_html_link(*_NVIDIA)}<br/>"
		f"{_html_link(*_NVIDIA_EULA)}</li>",
		f"<li>Optional AI models via {_html_link(*_HF)} — default model cards:<br/>"
		f"{_html_link(*_MODEL_TEXT)}<br/>"
		f"{_html_link(*_MODEL_CLIP)}<br/>"
		f"{_html_link(*_MODEL_FW)}<br/>"
		f"{_html_link(*_MODEL_WHISPER)}</li>",
		"</ul>",
		"<p><b>Privacy</b></p>",
		"<ul>",
		"<li>srxy searches files on your machine. It does not upload your files to a remote srxy search service.</li>",
		"<li>Choosing downloads contacts third-party servers listed above. Those parties "
		"have their own privacy policies (linked above).</li>",
		"<li>Cached models, OCR results, and embeddings stay under your install prefix "
		"(SRXY_HOME) or ~/.cache/srxy for non-prefix installs.</li>",
		"</ul>",
		"<p>By checking the acknowledgment box you confirm you understand these "
		"third-party downloads and accept responsibility for complying with their "
		"licenses and privacy policies.</p>",
	]
	return "\n".join(parts)


__all__ = [
	"privacy_disclaimer_html",
	"privacy_disclaimer_text",
]
