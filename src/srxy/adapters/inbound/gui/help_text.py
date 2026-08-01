"""Help copy for GUI search options and filters."""

from __future__ import annotations


_HELP: dict[str, str] = {
	"search_names": """\
Match against file paths and filenames.

Fuzzy, phonetic, and substring matching apply to the basename and path
segments. Turn this off when you only want content matches.""",
	"search_contents": """\
Match text inside documents, tags, and file metadata.

Covers extracted document text, EXIF/media tags, and other content
sources. Power-ups (OCR, transcription, visual match) also require
content search.""",
	"semantic": """\
Find related meaning, not just exact spelling.

Uses a multilingual sentence embedding model. Requires optional deps and
a GPU (CUDA or Apple MPS):

  pip install 'srxy[semantic]'
  export SRXY_SEMANTIC=1

Semantic search needs a GPU to run. First use may download model weights
into ~/.cache/srxy/semantic-model.""",
	"ocr": """\
Read text in photos, scans, and embedded PDF/Office images via Tesseract.

Install the tesseract binary on PATH (pytesseract is included with srxy):

  Debian/Ubuntu:  sudo apt install tesseract-ocr
  Arch:           sudo pacman -S tesseract
  Fedora:         sudo dnf install tesseract
  macOS:          brew install tesseract
  Windows:        winget install UB-Mannheim.TesseractOCR
                  (or: choco install tesseract)

More info: https://github.com/tesseract-ocr/tesseract""",
	"transcribe": """\
Search spoken words in audio and video (Whisper).

Requires optional deps and ffmpeg on PATH:

  pip install 'srxy[semantic]'
  export SRXY_TRANSCRIBE=1

Install ffmpeg:

  Debian/Ubuntu:  sudo apt install ffmpeg
  Arch:           sudo pacman -S ffmpeg
  Fedora:         sudo dnf install ffmpeg
  macOS:          brew install ffmpeg
  Windows:        winget install Gyan.FFmpeg
                  (or: choco install ffmpeg)

Download builds: https://ffmpeg.org/download.html

First use may download model weights into ~/.cache/srxy/transcribe-model.""",
	"semantic_image": """\
Match what an image looks like using CLIP (visual description search).

Requires optional deps:

  pip install 'srxy[semantic]'
  export SRXY_SEMANTIC_IMAGE=1

A GPU (CUDA or Apple MPS) is strongly recommended. First use may download
CLIP weights into ~/.cache/srxy/semantic-image-model. Queries shorter than
4 characters are ignored for CLIP.""",
	"include_hidden": """\
Include hidden files and folders (dotfiles / hidden directories).

By default srxy skips hidden paths. Enable this to search them.""",
	"include_noise": """\
Include common cache and vendor directories.

By default srxy skips noise folders such as __pycache__, node_modules,
.git, and similar. Enable this to search inside them.""",
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
	return _HELP.get(key, "No help available.")


__all__ = [
	"help_text",
]
