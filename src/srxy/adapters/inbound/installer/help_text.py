"""Easy-to-read help copy for installer options (same tone as the main GUI)."""

from __future__ import annotations


_HELP: dict[str, str] = {
	"tesseract": """\
Text in images

Downloads Tesseract so srxy can read text inside photos, scans, and
images embedded in PDFs or Office files.

This does not need a GPU. Files are kept in your install folder — no
system-wide Tesseract install is required.""",
	"ffmpeg": """\
Spoken words helper

Downloads ffmpeg so srxy can listen to audio and video when you use
Spoken words search.

This helper works on its own; the AI speech models (under AI search
extras) still need a GPU in the GUI. Files stay in your install folder.""",
	"semantic": """\
AI search extras

Installs the optional pieces for:

  • Similar meaning (find related text, not just exact spelling)
  • Visual description (match what a picture looks like)
  • Spoken words (search what was said in audio/video)

Needs a GPU that PyTorch can use (NVIDIA CUDA on Linux/Windows; Apple
Silicon MPS on macOS). Downloads PyTorch and related packages from
PyPI — including NVIDIA pieces when CUDA is used (see the privacy
notice).""",
	"models": """\
Download AI models now

Fetches the AI model files from Hugging Face during install (similar
meaning, visual description, and speech).

You can skip this; srxy can later install the models when needed.
Prefetching needs AI search extras.""",
	"no_gpu": """\
No usable GPU detected

AI search extras (similar meaning, visual description, and spoken words
in the GUI) need a GPU that PyTorch can use.

On this Linux installer we look for an NVIDIA GPU (CUDA). None was found,
so those options stay off. You can still install srxy and use:

  • File names and folder search
  • Document text, tags, and metadata
  • Text in images (if you download Tesseract)

If you add a compatible GPU later, you can install AI extras with:

  uv pip install 'srxy[semantic]'
""",
}


def help_text(key: str) -> str:
	return _HELP.get(key, "No help available.")


__all__ = ["help_text"]
