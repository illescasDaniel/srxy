"""Help copy for GUI search options and filters."""

from __future__ import annotations

from srxy.application.install_method import (
	ffmpeg_enable_hint,
	ocr_enable_hint,
	semantic_enable_hint,
)


def _help() -> dict[str, str]:
	semantic_hint = semantic_enable_hint()
	ocr_hint = ocr_enable_hint()
	ffmpeg_hint = ffmpeg_enable_hint()
	return {
		"search_names": """\
Match against file paths and filenames.

Fuzzy, phonetic, and substring matching apply to the basename and path
segments. Turn this off when you only want content matches.""",
		"search_contents": """\
Search inside files (not just names).

Master switch for document text, tags/metadata, OCR, transcription, and
visual matching. Turn this off for filename-only search. When on, choose
sources under How to match.""",
		"search_docs_tags": """\
Match text inside documents, tags, and file metadata.

Recommended ON for most searches. Turn this off when you only want Text
in images, Spoken words, and/or Visual description (File contents must
still be on).""",
		"semantic": f"""\
Find related meaning, not just exact spelling.

Uses a multilingual sentence embedding model. Requires optional AI extras
and a GPU (CUDA or Apple MPS):

  {semantic_hint}
  export SRXY_SEMANTIC=1

Semantic search needs a GPU to run. First use may download model weights
into the srxy cache (under SRXY_HOME/cache when installed via the desktop
installer).""",
		"ocr": f"""\
Read text in photos, scans, and embedded PDF/Office images via Tesseract.

{ocr_hint}

If you install Tesseract yourself:

  Debian/Ubuntu:  sudo apt install tesseract-ocr
  Arch:           sudo pacman -S tesseract
  Fedora:         sudo dnf install tesseract
  macOS:          brew install tesseract
  Windows:        winget install UB-Mannheim.TesseractOCR
                  (or: choco install tesseract)

More info: https://github.com/tesseract-ocr/tesseract""",
		"transcribe": f"""\
Search spoken words in audio and video (Whisper).

Requires optional AI extras and ffmpeg:

  {semantic_hint}
  export SRXY_TRANSCRIBE=1

{ffmpeg_hint}

Install ffmpeg yourself if needed:

  Debian/Ubuntu:  sudo apt install ffmpeg
  Arch:           sudo pacman -S ffmpeg
  Fedora:         sudo dnf install ffmpeg
  macOS:          brew install ffmpeg
  Windows:        winget install Gyan.FFmpeg
                  (or: choco install ffmpeg)

Download builds: https://ffmpeg.org/download.html

First use may download model weights into the srxy cache.""",
		"semantic_image": f"""\
Match what an image looks like using CLIP (visual description search).

Requires optional AI extras:

  {semantic_hint}
  export SRXY_SEMANTIC_IMAGE=1

A GPU (CUDA or Apple MPS) is strongly recommended. First use may download
CLIP weights into the srxy cache. Queries shorter than 4 characters are
ignored for CLIP.""",
		"include_hidden": """\
Include hidden files and folders (dotfiles / hidden directories).

By default srxy skips hidden paths. Enable this to search them.""",
		"include_noise": """\
Include common cache and vendor directories.

By default srxy skips noise folders such as __pycache__ and node_modules.
Enable this to search inside them.""",
		"include_noise_files": """\
Include common junk, lock, and temp files.

By default srxy skips files such as uv.lock, package-lock.json, yarn.lock,
*.min.js, source maps, Office lock temps (~$), Thumbs.db, and similar.
Enable this to search their contents.""",
		"match_skipped_names": """\
Match filenames of otherwise-skipped noisy paths.

Requires File names to be on. When Hidden, Cache & vendor, or Junk & lock
files are off, enable this to still find those paths by name. Content
inside them stays skipped. May walk large trees such as node_modules just
to score names.""",
		"include_archives": """\
Search inside compressed archives (.zip, .tar, .tar.gz, .gz).

By default archives are skipped. Enabling this can be slower on large
archive trees.""",
		"include_subdirectories": """\
Search nested folders under the selected path.

On by default. Turn off to only search files directly inside the
chosen folder (not its subfolders).""",
		"top_files": """\
Maximum number of result files to keep (empty = no limit).

After ranking matches, only the top N files are returned. Leave blank
for unlimited results.""",
		"max_matches": """\
Maximum hit lines shown per file (default 50).

Caps how many match locations are kept for each file in the results.""",
		"threshold": """\
Minimum classic match score as a percentage (default 35%).

Applies to fuzzy / phonetic / substring scoring. Lower values return more
(and noisier) hits; higher values are stricter.""",
		"semantic_image_threshold": """\
Minimum CLIP visual similarity as a percentage (default 18%).

Only image-semantic matches at or above this score are kept.""",
		"transcribe_threshold": """\
Minimum speech-match score as a percentage (default 25%).

Only transcript matches at or above this score are kept.""",
		"text_mib": """\
Document / text extraction size limit in MiB (0 = unlimited).

Files larger than this are skipped for content text extraction.
Default is typically 100 MiB.""",
		"ocr_mib": """\
Image / OCR size limit in MiB (default 50).

Images and embedded media larger than this are skipped for OCR.""",
		"transcribe_mib": """\
Audio / video size limit in MiB for transcription (default 500).

Media files larger than this are skipped for speech search.""",
	}


def help_text(key: str) -> str:
	return _help().get(key, "No help available.")


__all__ = [
	"help_text",
]
