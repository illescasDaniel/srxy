# Installation

Requires **Python 3.11+**.

## Recommended

```bash
uv tool install 'srxy[semantic]'
```

`uv tool install` puts srxy in an isolated environment and adds the `srxy` command to your `PATH`. If the tool bin directory is not on `PATH`, run `uv tool update-shell`.

### pipx (alternate)

```bash
pipx install 'srxy[semantic]'
```

### Library / project install

```bash
pip install 'srxy[semantic]'   # inside a venv or project
pip install srxy                 # core only (no PyTorch / semantic / transcription)
```

`[semantic]` adds sentence-transformers (text + CLIP), faster-whisper, rawpy, and on Linux and Windows `nvidia-cublas-cu12` for GPU transcription with faster-whisper. On **Windows**, default installs pull the **CPU-only** PyTorch wheel — install CUDA PyTorch first if you have an NVIDIA GPU ([Windows installation](#windows)). Models download on first use ([Model prefetch](power-ups.md#model-prefetch)). To clear cache, see [Managing cache](power-ups.md#managing-cache).

## Desktop installers (optional)

Linux AppImages and macOS `.app` wrappers are available now. Windows desktop installers are still in progress. Short reference: [installers.md](installers.md).

PyPI / `uv tool install` remain the primary install paths. On Linux you can also use a **desktop installer AppImage**:

### Offline wizard (full)

1. Download `srxy-*-installer-<installer_version>-x86_64.AppImage.xz` from [GitHub Releases](https://github.com/illescasDaniel/srxy/releases/latest) (or build with [`packaging/linux-appimage/build.sh`](../packaging/linux-appimage/build.sh)). Do **not** confuse this with the `*-installer-online-*` artifact.
2. Decompress (`xz -d srxy-*-installer-*-x86_64.AppImage.xz`), make it executable, and run it — no `libfuse2` host package required (type2 static runtime).
3. Choose **Install or update**, **Reinstall**, or **Uninstall**. Default install prefix: `~/Applications/srxy` (binaries, models, and cache under that folder via `SRXY_HOME`).
   - **Install or update** installs into the chosen folder, or updates an existing srxy install there in place (venv is recreated; models/cache may remain).
   - **Reinstall** removes that install completely (including models/cache in the prefix), then installs fresh — you enter the path only once.
   - **Uninstall** removes the app, desktop entry, icons, and PATH block.
4. Acknowledge the [privacy / third-party notice](privacy.md), then optionally download Tesseract, ffmpeg, semantic extras, and AI models.
5. Optionally enable **Also let me run srxy from the Terminal** (default on). This prepends `$prefix/bin` to your shell startup file (`~/.bashrc`, `~/.zshrc`, or fish `config.fish`) with `# >>> srxy PATH >>>` markers. Open a **new** terminal after install. Uninstall removes that block.

### Online one-click (slim)

1. Download `srxy-*-installer-online-<installer_version>-x86_64.AppImage.xz` (or build with [`packaging/linux-appimage/build-online.sh`](../packaging/linux-appimage/build-online.sh)).
2. Decompress (`xz -d …`), then run it — it opens your default browser. First launch may download `uv`, Python, and the srxy installer package from PyPI into `~/.cache/srxy/online-bootstrap/` (needs network), then shows the install page on localhost only. Acknowledge privacy, click **Install**. Installs **from PyPI** into your chosen prefix. Always vendors uv/tesseract/ffmpeg and adds PATH; enables smarter-search packages only when a GPU/MPS is detected. AI model weights are **not** prefetched (downloaded on first smarter search).
3. No reinstall/uninstall UI in this artifact — use the offline wizard or remove the prefix manually. Closing the browser tab stops the installer process.

Language defaults to the system locale (English or Spanish). Override with the installer language combo (offline wizard), GUI **Help → Language**, TUI help dialog, `--language es`, or `SRXY_LANGUAGE=es`. Settings persist in `$SRXY_HOME/settings.json` or `~/.config/srxy/settings.json`.

The GUI checks PyPI for updates on startup and under **Help → Check for updates…**. Updates use your install method (prefix `uv pip`, `uv tool upgrade`, `pipx upgrade`, or pip). After an update completes, restart srxy to load the new version.

### macOS wrappers

1. Download a DMG from Releases:
   - `srxy-*-installer-<installer_version>-<arch>.dmg` (offline wizard), or
   - `srxy-*-installer-online-<installer_version>-<arch>.dmg` (online bootstrap).
2. Open the DMG and double-click the installer `.app`.
3. Both wrappers target `~/Applications/srxy` by default and do not require admin rights for that path.
4. Optionally vendor Tesseract and ffmpeg (Apple Silicon downloads; no Homebrew required), plus semantic extras / models when offered.
5. Finish — launcher and shell PATH updates use the chosen prefix under `~/Applications/srxy` by default. The first Launch after install may take several seconds (cold Qt load).

CI builds macOS wrappers via [`.github/workflows/macos-installer.yml`](../.github/workflows/macos-installer.yml). Linux CI builds AppImages via [`.github/workflows/appimage.yml`](../.github/workflows/appimage.yml) (see [`packaging/linux-appimage/README.md`](../packaging/linux-appimage/README.md)).

```bash
uv run python -m srxy.adapters.inbound.installer          # offline wizard
uv run srxy-installer
uv run python -m srxy.adapters.inbound.installer_online   # online one-click
uv run srxy-installer-online
uv run task installer-online-local                        # build local wheel + online UI (no PyPI package fetch)
# or: SRXY_INSTALL_WHEEL=/path/to/srxy-….whl uv run srxy-installer-online
```

`SRXY_INSTALL_WHEEL` (checked before `SRXY_INSTALL_SPEC`) points the installer at a local `.whl` and skips the PyPI package lookup. Vendor downloads (uv / tesseract / ffmpeg) still need the network.

## System dependencies

**ffmpeg** (transcription) and **tesseract** (OCR) must be on `PATH` when you use `--transcribe`, `--ocr`, or `--semantic-all`. Verify with:

```bash
ffmpeg -version
tesseract --version
```

On Windows, use `where ffmpeg` and `where tesseract` instead of `which`.

### macOS

macOS `python3` often **3.9–3.10** or missing. srxy needs **3.11+**. Install newer Python (or let `uv` manage it) before installing the tool.

1. **Python 3.11+** (pick one):

   **uv** (recommended):

   ```bash
   # uv can fetch a suitable Python automatically when installing tools
   uv python install 3.12
   ```

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

2. Install **uv** ([docs](https://docs.astral.sh/uv/getting-started/installation/)), or **pipx** if you prefer that installer.

3. **ffmpeg** / **tesseract** (optional): the macOS installer wrappers can vendor Apple Silicon builds without Homebrew. For PyPI / `uv tool` installs, use Homebrew or another package manager:

   ```bash
   brew install ffmpeg tesseract
   ```

4. Install srxy:

   ```bash
   uv tool install --python 3.12 'srxy[semantic]'
   ```

   Or with pipx (pin interpreter to avoid old system `python3`):

   ```bash
   pipx install --python "$(which python3)" 'srxy[semantic]'
   ```

### Linux

Install ffmpeg and tesseract with your package manager, then install srxy:

| Distro | ffmpeg | tesseract |
|--------|--------|-----------|
| Debian / Ubuntu | `sudo apt install ffmpeg` | `sudo apt install tesseract-ocr` |
| Arch | `sudo pacman -S ffmpeg` | `sudo pacman -S tesseract` |
| Fedora | `sudo dnf install ffmpeg` | `sudo dnf install tesseract` |

```bash
uv tool install 'srxy[semantic]'
# or: pipx install 'srxy[semantic]'
```

### Windows

1. Install **Python 3.11+** from [python.org](https://www.python.org/downloads/) or `winget install Python.Python.3.12` (optional if uv manages Python).
2. Install **uv** ([docs](https://docs.astral.sh/uv/getting-started/installation/)), or **pipx**:

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
   uv tool install 'srxy[semantic,windows]'
   # or: pipx install 'srxy[semantic,windows]'
   ```

   **GPU** (semantic search and transcription): default Windows installs pull **CPU-only** PyTorch. Semantic search and transcription stay on CPU unless you install a CUDA build of PyTorch in the same environment first.

   See [pytorch.org/get-started](https://pytorch.org/get-started/locally/) (Windows → Pip → CUDA). Use **CUDA 13.0** (`cu130`) for most recent GPUs; use **CUDA 12.6** (`cu126`) if `cu130` fails or your GPU/driver is older.

   **uv / venv** (recommended for GPU):

   ```powershell
   uv venv .venv
   .\.venv\Scripts\Activate.ps1
   uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
   uv pip install 'srxy[semantic,windows]'
   ```

   For CUDA 12.6, replace `cu130` with `cu126`.

   **pipx** (global `srxy` with GPU):

   ```powershell
   pipx install 'srxy[semantic,windows]'
   pipx inject srxy torch torchvision torchaudio --pip-args="--index-url https://download.pytorch.org/whl/cu130"
   ```

   `pipx inject` replaces the CPU wheel from `pipx install`.

   **uv tool** with CUDA torch via `--with` (same idea as inject):

   ```powershell
   uv tool install 'srxy[semantic,windows]' --with torch --with torchvision --with torchaudio --index https://download.pytorch.org/whl/cu130
   ```

   If index mixing fails, prefer the venv path above.

## Core-only install

When you do not need semantic search or transcription:

```bash
uv tool install srxy
# or: pipx install srxy
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

To install a specific release candidate from TestPyPI (dependencies still come from production PyPI):

```bash
uv tool install \
  --index https://test.pypi.org/simple/ \
  --index https://pypi.org/simple/ \
  'srxy[semantic]==1.3.0'
```

Or with `pipx` (`--index-url` plus extra index via `--pip-args`):

```bash
pipx install \
  --index-url https://test.pypi.org/simple/ \
  --pip-args='--extra-index-url https://pypi.org/simple/' \
  'srxy[semantic]==1.3.0'
```

Or with `pip` in a venv:

```bash
pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  'srxy[semantic]==1.3.0'
```

Replace `1.3.0` with the version you want to test.
