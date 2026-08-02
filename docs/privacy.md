# Privacy & third-party notice

srxy itself is **MIT**-licensed. You can install it from PyPI and use the GUI, TUI, CLI, or library without any desktop installer.

The optional **desktop installer** (Linux AppImage first; macOS/Windows later) does **not** ship NVIDIA/CUDA binaries, Hugging Face model weights, Tesseract, or ffmpeg inside the AppImage. When you opt in, it downloads components from third parties. Review their sites and privacy policies before continuing.

## What the installer may download

Only after you choose the related options (and after acknowledging this notice):

| Component | Site | Privacy |
|-----------|------|---------|
| Astral **uv** | [docs.astral.sh/uv](https://docs.astral.sh/uv/) | [Astral privacy](https://astral.sh/privacy-policy) |
| **PyPI** packages | [pypi.org](https://pypi.org/) | [PyPI privacy](https://policies.python.org/pypi.org/Privacy-Notice/) |
| **Qt / PySide6** (LGPL) | [qt.io](https://www.qt.io/) | [Qt privacy](https://www.qt.io/terms-conditions/privacy-policy) |
| **Tesseract** OCR | [tesseract-ocr/tesseract](https://github.com/tesseract-ocr/tesseract) | [GitHub privacy](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement) |
| **tessdata** | [tesseract-ocr/tessdata](https://github.com/tesseract-ocr/tessdata) | [GitHub privacy](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement) |
| **ffmpeg** | [ffmpeg.org](https://ffmpeg.org/) | [ffmpeg.org](https://ffmpeg.org/) |
| ffmpeg Linux builds (BtbN) | [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds) | [GitHub privacy](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement) |
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
- For prefix installs, cache and models live under the install folder (`SRXY_HOME`). For PyPI / `uv tool` installs, defaults remain under `~/.cache/srxy` unless overridden.
- When srxy is launched from the desktop menu (non-interactive stdout), the prefix launcher appends output to `{SRXY_HOME}/logs/srxy.log`. Search command-line arguments are **not** logged by default; set `SRXY_DEBUG=1` before launch to include them in that log file.
- The install manifest records which privacy-notice version you acknowledged (`privacy_ack_version`).

By acknowledging the installer notice you confirm you understand these third-party downloads and accept responsibility for complying with their licenses and privacy policies.
