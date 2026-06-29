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

`[semantic]` adds sentence-transformers (text + CLIP), faster-whisper, rawpy, and on Linux `nvidia-cublas-cu12` for GPU transcription. Models download on first use — see [Model prefetch](power-ups.md#model-prefetch) in the power-ups guide. To remove cached models or scan results, see [Managing cache](power-ups.md#managing-cache).

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

4. Install srxy with Windows Explorer tag support:

   ```powershell
   pipx install 'srxy[semantic,windows]'
   ```

   `[windows]` adds `pywin32` for `System.Keywords` tag search — see [CLI reference](cli.md).

## Core-only install

When you do not need semantic search, OCR, or transcription:

```bash
pipx install srxy
```

Filename fuzzy/phonetic search, document text extraction, and the TUI still work.

## Verify

```bash
srxy --version
which ffmpeg      # where ffmpeg on Windows
which tesseract   # where tesseract on Windows
```

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
