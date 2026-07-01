# Installation

Requires **Python 3.11+**.

## Recommended

```bash
pipx install 'srxy[semantic]'
```

`pipx` installs srxy in an isolated environment and puts the `srxy` command on your `PATH`.

Alternatives:

```bash
pip install 'srxy[semantic]'   # inside a venv or project
pip install srxy                 # core only (no PyTorch / semantic / transcription)
```

`[semantic]` adds sentence-transformers (text + CLIP), faster-whisper, rawpy, and on Linux and Windows `nvidia-cublas-cu12` for GPU transcription with faster-whisper. On **Windows**, pip installs the **CPU-only** PyTorch wheel — install CUDA PyTorch first if you have an NVIDIA GPU ([Windows installation](#windows)). Models download on first use ([Model prefetch](power-ups.md#model-prefetch)). To clear cache, see [Managing cache](power-ups.md#managing-cache).

## System dependencies

**ffmpeg** (transcription) and **tesseract** (OCR) must be on `PATH` when you use `--transcribe`, `--ocr`, or `--semantic-all`. Verify with:

```bash
ffmpeg -version
tesseract --version
```

On Windows, use `where ffmpeg` and `where tesseract` instead of `which`.

### macOS

macOS `python3` often **3.9–3.10** or missing. srxy needs **3.11+**. Install newer Python before `pipx`.

1. **Python 3.11+** (pick one):

   **pyenv** (version management):

   ```bash
   brew install pyenv
   pyenv install 3.12
   pyenv global 3.12   # or pyenv local 3.12 in a project dir
   python3 --version   # expect 3.12.x
   ```

   Still old `python3`? [pyenv shell setup](https://github.com/pyenv/pyenv#set-up-your-shell-environment-for-pyenv) — `eval "$(pyenv init -)"` in `~/.zshrc`.

   **Homebrew** (one version):

   ```bash
   brew install python@3.12
   ```

   Put `python3.12` or linked `python3` on `PATH`.

2. **pipx** on `PATH`:

   ```bash
   python3 -m pip install pipx
   pipx ensurepath
   ```

   Restart terminal after `pipx ensurepath`.

3. System binaries ([Homebrew](https://brew.sh/)):

   ```bash
   brew install ffmpeg tesseract
   ```

4. Install srxy — pin interpreter (avoid old `python3`):

   ```bash
   pipx install --python "$(which python3)" 'srxy[semantic]'
   ```

   Homebrew versioned binary: `pipx install --python python3.12 'srxy[semantic]'`.

### Linux

Install ffmpeg and tesseract with your package manager, then install srxy:

| Distro | ffmpeg | tesseract |
|--------|--------|-----------|
| Debian / Ubuntu | `sudo apt install ffmpeg` | `sudo apt install tesseract-ocr` |
| Arch | `sudo pacman -S ffmpeg` | `sudo pacman -S tesseract` |
| Fedora | `sudo dnf install ffmpeg` | `sudo dnf install tesseract` |

```bash
pipx install 'srxy[semantic]'
```

### Windows

1. Install **Python 3.11+** from [python.org](https://www.python.org/downloads/) or `winget install Python.Python.3.12`.
2. Install **pipx** and ensure it is on `PATH`:

   ```powershell
   python -m pip install pipx
   pipx ensurepath
   ```

   Restart your terminal after `pipx ensurepath`.

3. Install system binaries (pick one package manager per tool):

   ```powershell
   winget install Gyan.FFmpeg
   winget install UB-Mannheim.TesseractOCR
   ```

   Or with [Chocolatey](https://chocolatey.org/):

   ```powershell
   choco install ffmpeg
   choco install tesseract
   ```

   Restart your terminal so `PATH` picks up the new binaries.

4. Install srxy:

   `[windows]` adds `pywin32` for `System.Keywords` tag search ([CLI reference](cli.md)).

   **CPU only** (no NVIDIA GPU, or GPU not needed):

   ```powershell
   pipx install 'srxy[semantic,windows]'
   ```

   **GPU** (semantic search and transcription): Windows `pip`/`pipx` install pulls **CPU-only** PyTorch. Semantic search and transcription stay on CPU unless you install a CUDA build of PyTorch in the same environment first.

   See [pytorch.org/get-started](https://pytorch.org/get-started/locally/) (Windows → Pip → CUDA). Use **CUDA 13.0** (`cu130`) for most recent GPUs; use **CUDA 12.6** (`cu126`) if `cu130` fails or your GPU/driver is older.

   **venv** (recommended for GPU):

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
   pip install 'srxy[semantic,windows]'
   ```

   For CUDA 12.6, replace `cu130` with `cu126`.

   **pipx** (global `srxy` with GPU):

   ```powershell
   pipx install 'srxy[semantic,windows]'
   pipx inject srxy torch torchvision torchaudio --pip-args="--index-url https://download.pytorch.org/whl/cu130"
   ```

   `pipx inject` replaces the CPU wheel from `pipx install`.

## Core-only install

When you do not need semantic search or transcription:

```bash
pipx install srxy
```

Filename fuzzy/phonetic search, document text extraction, OCR (with **tesseract** on `PATH`), and the TUI still work. OCR does not require `[semantic]` — only the Python wrapper (`pytesseract`) ships with core; install the **tesseract** binary separately.

## Verify

```bash
srxy --version
which ffmpeg      # where ffmpeg on Windows
which tesseract   # where tesseract on Windows
```

With `[semantic]` and an NVIDIA GPU, confirm PyTorch sees CUDA:

```powershell
python -c "import torch; print(torch.__version__); print('cuda:', torch.cuda.is_available())"
```

Expect `+cu130` or `+cu126` and `cuda: True`. `+cpu` means GPU support was not installed.

## TestPyPI (testers)

To install a specific release candidate from TestPyPI (dependencies still come from production PyPI).

`pipx` accepts `--index-url` but not `--extra-index-url`; pass the extra index through `--pip-args`:

```bash
pipx install \
  --index-url https://test.pypi.org/simple/ \
  --pip-args='--extra-index-url https://pypi.org/simple/' \
  'srxy[semantic]==1.3.0'
```

Or with `pip` in a venv (both index flags work directly):

```bash
pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  'srxy[semantic]==1.3.0'
```

Replace `1.3.0` with the version you want to test.
