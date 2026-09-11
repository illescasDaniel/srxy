# Privacy & third-party notice

srxy itself is **MIT**-licensed. You can install it from PyPI, a desktop installer, or another channel and use the GUI, TUI, CLI, or library.

srxy and its optional features may download NVIDIA/CUDA-related packages, Hugging Face model weights, Tesseract, or ffmpeg from third parties. Review their sites and privacy policies before using those features. See [installers.md](installers.md).

## What srxy may download

Only when you enable the related options (and after acknowledging this notice). Sources vary by OS:

| Component | Site | Privacy |
|-----------|------|---------|
| Astral **uv** | [docs.astral.sh/uv](https://docs.astral.sh/uv/) | [Astral privacy](https://astral.sh/privacy-policy) |
| **PyPI** packages | [pypi.org](https://pypi.org/) | [PyPI privacy](https://policies.python.org/pypi.org/Privacy-Notice/) |
| **Qt / PySide6** (LGPL) | [qt.io](https://www.qt.io/) | [Qt privacy](https://www.qt.io/terms-conditions/privacy-policy) |
| **Tesseract** OCR (upstream) | [tesseract-ocr/tesseract](https://github.com/tesseract-ocr/tesseract) | [GitHub privacy](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement) |
| **tessdata** | [tesseract-ocr/tessdata](https://github.com/tesseract-ocr/tessdata) | [GitHub privacy](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement) |
| Tesseract Linux binary | [DanielMYT/tesseract-static](https://github.com/DanielMYT/tesseract-static) | [GitHub privacy](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement) |
| Tesseract macOS bottles (Homebrew core via ghcr.io) | [formulae.brew.sh/tesseract](https://formulae.brew.sh/formula/tesseract) | [Homebrew](https://brew.sh/) · [GitHub Container Registry](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement) |
| Tesseract Windows setup (UB-Mannheim; extracted without elevation) | [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract) | [GitHub privacy](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement) |
| **7-Zip** (Windows install-time extract helper for Tesseract) | [7-zip.org](https://www.7-zip.org/) | [7-zip.org](https://www.7-zip.org/) |
| **ffmpeg** | [ffmpeg.org](https://ffmpeg.org/) | [ffmpeg.org](https://ffmpeg.org/) |
| ffmpeg Linux/Windows builds (BtbN) | [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds) | [GitHub privacy](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement) |
| ffmpeg macOS builds (martin-riedl) | [ffmpeg.martin-riedl.de](https://ffmpeg.martin-riedl.de/) | [ffmpeg.org](https://ffmpeg.org/) |
| **PyTorch** (`[semantic]`) | [pytorch.org](https://pytorch.org/) | [Linux Foundation privacy](https://www.linuxfoundation.org/legal/privacy) |
| **NVIDIA CUDA** | [CUDA Zone](https://developer.nvidia.com/cuda-zone) · [CUDA EULA](https://docs.nvidia.com/cuda/eula/index.html) | [NVIDIA privacy](https://www.nvidia.com/en-us/about-nvidia/privacy-policy/) |
| **Hugging Face** hub | [huggingface.co](https://huggingface.co/) | [HF privacy](https://huggingface.co/privacy) |

### Default AI model cards

| Use | Model card |
|-----|------------|
| Similar meaning | [paraphrase-multilingual-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) |
| Visual description | [clip-ViT-B-32](https://huggingface.co/sentence-transformers/clip-ViT-B-32) |
| Spoken words (default) | [Systran/faster-whisper-base](https://huggingface.co/Systran/faster-whisper-base) |
| Spoken words (Apple MPS path) | [openai/whisper-base](https://huggingface.co/openai/whisper-base) |

Each model card has its own license and usage terms.

## Python libraries (via PyPI)

These direct runtime libraries ship with srxy (or with optional extras) via PyPI. They process files **on your machine**; install/download privacy for the index itself is under PyPI above.

### Core

| Library | Project | Used for |
|---------|---------|----------|
| **cryptography** | [cryptography.io](https://cryptography.io/) | Encrypts the local search cache on disk |
| **exifread** | [ianare/exif-py](https://github.com/ianare/exif-py) | Reads image EXIF/GPS/camera metadata |
| **jellyfish** | [jamesturk/jellyfish](https://github.com/jamesturk/jellyfish) | Phonetic matching (“sounds like” search) |
| **mutagen** | [mutagen](https://mutagen.readthedocs.io/) | Reads audio/video tags |
| **openpyxl** | [openpyxl](https://openpyxl.readthedocs.io/) | Extracts text from Excel `.xlsx` |
| **Pillow** | [python-pillow.org](https://python-pillow.org/) | Opens/rotates images for OCR, EXIF, and vision |
| **pillow-heif** | [bigcat88/pillow_heif](https://github.com/bigcat88/pillow_heif) | Opens HEIC/HEIF images |
| **pypdf** | [pypdf](https://pypdf.readthedocs.io/) | Extracts PDF text (and pages for OCR) |
| **pytesseract** | [madmaze/pytesseract](https://github.com/madmaze/pytesseract) | Python bridge to local Tesseract OCR |
| **PySide6** | [Qt for Python](https://doc.qt.io/qtforpython/) | Desktop GUI and installer UI |
| **python-docx** | [python-docx](https://python-docx.readthedocs.io/) | Extracts text from Word `.docx` |
| **python-pptx** | [python-pptx](https://python-pptx.readthedocs.io/) | Extracts text from PowerPoint `.pptx` |
| **pywin32** | [mhammond/pywin32](https://github.com/mhammond/pywin32) | Windows Explorer file tags (Windows only) |
| **rapidfuzz** | [rapidfuzz/RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) | Fuzzy string scoring for search |
| **textual** | [textual.textualize.io](https://textual.textualize.io/) | Terminal UI (TUI) |
| **wordfreq** | [rspeer/wordfreq](https://github.com/rspeer/wordfreq) | Scores OCR text against word-frequency lists |

### Optional `[semantic]`

| Library | Project | Used for |
|---------|---------|----------|
| **faster-whisper** | [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Local speech-to-text |
| **nvidia-cublas-cu12** | [cuBLAS](https://developer.nvidia.com/cublas) | cuBLAS libs for GPU transcription (Linux/Windows) |
| **rawpy** | [letmaik/rawpy](https://github.com/letmaik/rawpy) | Decodes camera RAW for metadata/vision |
| **sentence-transformers** | [sbert.net](https://www.sbert.net/) | Local text/image embeddings |

## Privacy

- srxy searches files **on your machine**. It does not upload your files to a remote srxy search service.
- Choosing downloads contacts the third-party servers linked above. Those parties have their own privacy policies.
- For prefix installs, cache and models live under the install folder (`SRXY_HOME`). For non-prefix installs the default is `~/.cache/srxy` on Linux/macOS or `%LOCALAPPDATA%\srxy` on Windows (override with `SRXY_CACHE_DIR`).
- When srxy is launched from the desktop menu (non-interactive stdout), the prefix launcher appends output to `{SRXY_HOME}/logs/srxy.log`. Search command-line arguments are **not** logged by default; set `SRXY_DEBUG=1` before launch to include them in that log file.
- The install manifest records which privacy-notice version you acknowledged (`privacy_ack_version`).

## Disclaimer of Warranties and Limitation of Liability

This software is provided "as is", without any warranty of any kind, express or implied. The author and contributors shall not be held liable for any damage, data loss, malfunction, or any other harm arising from the use of this software. By accepting these terms, you acknowledge and accept all such limitations.

By acknowledging this notice you confirm you understand these third-party downloads and accept responsibility for complying with their licenses and privacy policies.
