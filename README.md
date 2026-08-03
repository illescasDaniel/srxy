# Srxy

[![CI](https://github.com/illescasDaniel/srxy/actions/workflows/ci.yml/badge.svg)](https://github.com/illescasDaniel/srxy/actions/workflows/ci.yml)
[![version](https://img.shields.io/pypi/v/srxy)](https://pypi.org/project/srxy/)
[![PyPI](https://img.shields.io/badge/PyPI-srxy-3775A9?logo=pypi&logoColor=white)](https://pypi.org/project/srxy/)

**Find files by what you mean — terminal or Python.**

Fuzzy, phonetic, and semantic matching across filenames, documents, photos, audio, video, and OS tags. On a desktop session, **srxy opens a GUI by default**; use `--tui` for the terminal UI or `--cli` for scripts and pipes.

## Installation

Needs **Python 3.11+**. `uv tool install 'srxy[semantic]'` recommended; `pipx install 'srxy[semantic]'` also works; `pipx install srxy` for core-only in a venv. Windows: add `[windows]` for Explorer tags. macOS: system `python3` may be too old — [Installation](docs/installation.md#macos).

**Platform setup (ffmpeg, tesseract):** [docs/installation.md](docs/installation.md). Privacy / third-party notice: [docs/privacy.md](docs/privacy.md).

## Quick start

**GUI (default on a graphical session):**

```bash
srxy                          # empty query/path
srxy "registry" ./src         # pre-filled; auto-starts
```

![srxy GUI](docs/images/gui.png)

Walkthrough: [docs/gui.md](docs/gui.md). Architecture: [docs/architecture.md](docs/architecture.md).

**Desktop installers (Linux):**

Two Linux AppImages from [GitHub Releases](https://github.com/illescasDaniel/srxy/releases) (make executable and run; no host `libfuse2`):

| Artifact | What you get |
|----------|----------------|
| `srxy-*-installer-*.AppImage` | **Offline wizard** — full PySide UI; install / update / reinstall / uninstall |
| `srxy-*-installer-online-*.AppImage` | **Online one-click** — slim Go bootstrap; opens your browser to a localhost page and installs from PyPI |

Default prefix: `~/Applications/srxy`. The online AppImage needs a network connection on first launch (downloads `uv`, managed Python, and srxy into `~/.cache/srxy/online-bootstrap/`); later runs reuse the cache. It vendors PATH / tesseract / ffmpeg automatically and enables smarter-search packages only when a GPU is detected — model weights download later when you use those features. No reinstall/uninstall UI on the online path (use the offline wizard or remove the prefix).

Windows and macOS installers are in progress. PyPI / `uv tool install` remain the primary paths on every platform. Guide: [docs/installers.md](docs/installers.md). Privacy / third-party notice: [docs/privacy.md](docs/privacy.md).

![srxy offline desktop installer](docs/images/installer.png)

![srxy online web installer](docs/images/installer-online.png)

**TUI:**

```bash
srxy --tui
srxy --tui "registry" ./src
srxy --tui "transform" ./docs --ocr
```

![srxy TUI](docs/images/tui.svg)

Live scan progress, sortable results, preview pane, option chips, clipboard copy. Full walkthrough: [docs/tui.md](docs/tui.md).

**Plain CLI:**

```bash
srxy "registry" ./src --cli
srxy "revenue" ./docs --json
srxy "dog at the beach" ~/Pictures --semantic-image --content-only
srxy "revenue" ./docs --semantic-all --content-only
```

Boolean queries (`|`, `&`), scope flags, format table: [docs/cli.md](docs/cli.md).

**Python:**

```python
from pathlib import Path
from srxy import magic_file_search, magic_search

magic_file_search(Path("./src"), "registry", threshold=0.3)
magic_search([{"name": "salad"}], "salat", fields=["name"])
```

API reference: [docs/python-api.md](docs/python-api.md) · [docs/api-reference.md](docs/api-reference.md).

## Documentation

| Guide | Contents |
|-------|----------|
| [Installation](docs/installation.md) | uv tool / pipx, macOS/Linux/Windows, ffmpeg, tesseract |
| [Desktop installers](docs/installers.md) | Linux AppImages (offline + online); Windows/macOS coming soon |
| [TUI](docs/tui.md) | Layout, keybindings, clipboard, release checklist |
| [CLI reference](docs/cli.md) | Flags, formats, boolean queries, exit codes |
| [Power-ups](docs/power-ups.md) | OCR, semantic, CLIP, transcription, models |
| [Python API](docs/python-api.md) | `magic_file_search`, `search`, `Q`, match types |
| [API reference](docs/api-reference.md) | Generated signatures from `srxy.__all__` |
| [Development](docs/development.md) | Quality gate, `--full`, fixtures, pytest |

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra semantic
uv run task checks-fix
uv run task checks              # day-to-day
uv run task checks-full         # before release
uv run task checks-full-cpu     # + forced-CPU transcribe matrix
```

CI runs unit tests only (`unit` marker, excluding `semantic` and `transcribe`). Details: [docs/development.md](docs/development.md).

Try fixtures: `srxy "axolotl" ./tests/fixtures/file_search`

## License

MIT — see [LICENSE](LICENSE).
