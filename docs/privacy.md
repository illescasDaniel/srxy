# Privacy & third-party notice

srxy itself is **MIT**-licensed. You can install it from PyPI and use the GUI, TUI, CLI, or library without any desktop installer.

The optional **desktop installer** (Linux AppImages, macOS `.app` / DMG wrappers, and the Windows offline Inno Setup `.exe`) does **not** ship NVIDIA/CUDA binaries, Hugging Face model weights, Tesseract, or ffmpeg inside the installer artifact. When you opt in, it downloads components from third parties. Review their sites and privacy policies before continuing. See [installers.md](installers.md).

## What the installer may download

Only after you choose the related options (and after acknowledging this notice). Sources vary by OS:

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

## Privacy

- srxy searches files **on your machine**. It does not upload your files to a remote srxy search service.
- Choosing downloads contacts the third-party servers linked above. Those parties have their own privacy policies.
- For prefix installs, cache and models live under the install folder (`SRXY_HOME`). For PyPI / `uv tool` installs, defaults are `~/.cache/srxy` on Linux/macOS and `%LOCALAPPDATA%\srxy` on Windows (override with `SRXY_CACHE_DIR`).
- When srxy is launched from the desktop menu (non-interactive stdout), the prefix launcher appends output to `{SRXY_HOME}/logs/srxy.log`. Search command-line arguments are **not** logged by default; set `SRXY_DEBUG=1` before launch to include them in that log file.
- The install manifest records which privacy-notice version you acknowledged (`privacy_ack_version`).

By acknowledging the installer notice you confirm you understand these third-party downloads and accept responsibility for complying with their licenses and privacy policies.
