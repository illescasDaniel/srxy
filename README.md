# Srxy

[![CI](https://github.com/illescasDaniel/srxy/actions/workflows/ci.yml/badge.svg)](https://github.com/illescasDaniel/srxy/actions/workflows/ci.yml)
[![version](https://img.shields.io/pypi/v/srxy)](https://pypi.org/project/srxy/)
[![PyPI](https://img.shields.io/badge/PyPI-srxy-3775A9?logo=pypi&logoColor=white)](https://pypi.org/project/srxy/)

**Find files by what you mean — from the terminal or Python.**

Fuzzy, phonetic, and semantic matching across filenames, documents, photos, audio, video, and OS file tags. One command: `srxy`.

## Installation

**Recommended** — fuzzy/phonetic search plus semantic search, OCR, and audio/video transcription. Model weights are downloaded on first use, not at install time:

```bash
pipx install 'srxy[semantic]'   # global srxy command (recommended)
pip install 'srxy[semantic]'      # library + CLI in current env
pip install srxy                  # core only (no PyTorch / semantic / transcription)
```

The `[semantic]` extra adds:

- **`sentence-transformers`** (pulls in **PyTorch** and `huggingface_hub`) — text semantic (`paraphrase-multilingual-MiniLM-L12-v2`) and image semantic (**CLIP** `clip-ViT-B-32`)
- **`faster-whisper`** — local Whisper speech-to-text for audio and video (`--transcribe`)
- **`rawpy`** — embedded previews from camera RAW for CLIP search
- **`nvidia-cublas-cu12`** (Linux only) — CUDA libraries for GPU-accelerated transcription

You also need **ffmpeg** on `PATH` for transcription and the **tesseract** binary for OCR (see [Power-ups](#power-ups)).

If you don't have pipx yet, see the [pipx installation guide](https://pipx.pypa.io/stable/installation/).

---

## Quick start

Search file names and contents (default) with fuzzy matching:

```bash
srxy registry ./src
```

Grouped output highlights scores, match locations, and query hits:

```
1 file matched for "registry"
── ./src/srxy/file_search.py ──
   score 0.82  ·  matched: name, content
   line 128  ·  score 0.76
   │ def magic_file_search(
```

**Targeted modes:**

```bash
srxy revenue ./docs --content-only          # skip filename search
srxy budget . --format flat                 # pipe-friendly lines
srxy token . --json                         # machine-readable output
srxy invoice ./photos --ocr --content-only  # OCR text in photos and PDF images
srxy "call me maybe" ~/Music --transcribe --content-only  # speech in audio/video
srxy "dog at the beach" ~/Pictures --semantic-image --content-only
srxy revenue ./docs --semantic-all --content-only
```

**Scope controls:**

```bash
srxy token . --names-only                   # filenames only
srxy token . --include-hidden               # search .git and other dot entries
srxy token . --include-noise                # search __pycache__, node_modules, etc.
srxy token . --include-hidden --include-noise
```

Directories are walked recursively. By default, dot-prefixed hidden entries and noise folders (`__pycache__`, `node_modules`) are skipped.

---

## What srxy can search

| Category | Formats | What's searched | Notes |
|----------|---------|-----------------|-------|
| Plain text | any file | line-by-line body text | `--max-file-size` applies |
| Documents | `.pdf`, `.docx`, `.xlsx`, `.pptx` | extracted text | locations: page / paragraph / row / slide |
| Images | `.jpg`, `.jpeg`, `.png`, `.webp`, `.tif`, `.tiff`, `.heic`, `.heif` | EXIF + embedded metadata | |
| Camera RAW | `.arw`, `.cr2`, `.cr3`, `.dng`, `.nef`, `.nrw`, `.orf`, `.pef`, `.raf`, `.raw`, `.rw2`, `.srw` | EXIF from embedded preview | CLIP uses preview via `rawpy` |
| Audio | `.mp3`, `.flac`, `.ogg`, `.oga`, `.opus`, `.m4a`, `.aac` | ID3 / Vorbis tags; **spoken words** with `--transcribe` | title, artist, album, lyrics tags, etc. |
| Video | `.mp4`, `.m4v`, `.mov` | container metadata; **spoken words** with `--transcribe` | |
| Video (limited) | `.mkv`, `.avi`, `.webm` | filename only | no tag/transcription support yet |
| Linux tags | any file | `user.xdg.tags`, `user.dolphin.tags`, `user.xdg.comment` xattrs | |
| macOS tags | any file | Finder tags + comments xattrs | |
| Windows tags | any file | `System.Keywords` | requires `srxy[windows]` |

Media metadata and OS tags are searchable regardless of `--max-file-size`. There is **no default file-size cap** for plain text or office documents; use `--max-file-size` only when you want to limit content reads. Files that look binary (null bytes in the first 8 KiB) are skipped for body text search.

Platform-specific tag tests: `pytest -m linux_xattr`, `pytest -m macos_finder`, `pytest -m windows_tags` (requires `srxy[windows]`).

### Optional layers

These add capabilities on top of the table above — see [Power-ups](#power-ups):

- **OCR** — raster images + embedded images in PDF pages (`--ocr`)
- **Text semantic** — meaning-based text match (`--semantic`)
- **Image semantic (CLIP)** — search photos by visual description (`--semantic-image`)
- **Transcription** — search spoken words in audio and video via local Whisper (`--transcribe`)

---

## CLI reference

| | |
|---|---|
| **Search scope** | `--names-only`, `--content-only`, `--names` / `--no-names`, `--content` / `--no-content` |
| **Matching** | `--threshold`, `--semantic-image-threshold`, `--transcribe-threshold`, `--semantic`, `--semantic-image`, `--semantic-all`, `--ocr`, `--transcribe` |
| **Limits** | `--max-file-size`, `--max-ocr-file-size`, `--max-transcribe-file-size`, `--max-line-matches`, `-l` / `--limit` |
| **Output** | `--format grouped\|flat`, `--json`, `-o` / `--output` |
| **Walk** | `--include-hidden`, `--include-noise` |
| **UX** | `--progress` / `--no-progress` |

When stderr is a terminal (default), a file-scan progress bar is shown; during slow work (OCR, transcription, CLIP encoding, model load) an activity spinner appears on stderr. A brief **match found** flash appears on the progress bar when a file matches. Results are printed **after** the scan completes, sorted by score (best first). Skipped-file warnings are printed after the match summary.

**Exit codes:** `0` matches found, `1` no matches, `2` usage/path error.

---

## Power-ups

All optional features are off by default. Enable per run with CLI flags or persist with environment variables.

### OCR

Search text inside photos and embedded images in PDF pages (code screenshots, charts, scans).

```bash
srxy invoice ./photos --ocr --content-only
export SRXY_OCR=1
```

By default, images are searched via EXIF/metadata only; PDFs use embedded text from `pypdf`. With `--ocr`, srxy **adds** local OCR on top. PDF body text still comes from `pypdf`; OCR does not replace it. Matches report the PDF **page** number.

OCR uses **Tesseract** via `pytesseract` (installed with srxy). You still need the `tesseract` binary on `PATH` (e.g. `tesseract-ocr` on Debian/Ubuntu, `tesseract` on Arch). There is **no default OCR file-size cap**; use `--max-ocr-file-size` or `SRXY_OCR_MAX_FILE_SIZE` only when you want to limit OCR on very large files.

OCR results are cached by file content hash in `~/.cache/srxy/cache.db` (override with `SRXY_CACHE_DIR`). Disable with `SRXY_CACHE_DISABLE=1`.

### Text semantic

Meaning-based similarity for text content (requires `srxy[semantic]`):

```bash
srxy revenue ./docs --semantic --content-only
export SRXY_SEMANTIC=1
```

With `SRXY_SEMANTIC=1`, composite matching includes semantic similarity. Explicit `Q.semantic(...)` or `MatchType.SEMANTIC` in the Python API raises a clear error if semantic is not enabled.

Default model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. On first use, srxy offers to download and cache it under `~/.cache/srxy/semantic-model`.

### Image semantic (CLIP)

Search photos by **visual meaning**, not just filenames or EXIF tags (requires `srxy[semantic]`):

```bash
srxy "sunset over water" ~/Pictures --semantic-image --content-only
export SRXY_SEMANTIC_IMAGE=1
```

Uses **CLIP** (`sentence-transformers/clip-ViT-B-32`) via [`sentence-transformers`](https://www.sbert.net/) `SentenceTransformer`. On first use, srxy offers to download and cache weights under `~/.cache/srxy/semantic-image-model`.

Image embeddings are cached by content hash alongside OCR. CLIP scores are typically lower than text fuzzy matches; when the best score comes from image semantic, the default cutoff is **0.18** (`--semantic-image-threshold`; the global `--threshold` default remains 0.35 for names and text). **Camera RAW** is supported via embedded previews decoded with [`rawpy`](https://pypi.org/project/rawpy/) (included in `srxy[semantic]`).

### Transcription

Search **spoken words** inside audio and video files (requires `srxy[semantic]` and **ffmpeg** on `PATH`):

```bash
srxy "quarterly earnings" ~/Recordings --transcribe --content-only
srxy "call me maybe" ~/Music --semantic-all --content-only
export SRXY_TRANSCRIBE=1
```

By default, audio and video are searchable via container tags only (title, artist, embedded lyrics, etc.). With `--transcribe`, srxy **adds** local speech-to-text on top using **Whisper**. Supported formats: the same audio extensions as above plus `.mp4`, `.m4v`, and `.mov`.

Matches show the timestamp in the location header, not in the searchable text:

```
transcript at 02:40  ·  score 0.34
   │ And all the «other boys»
```

Only the spoken words are matched — searching `02` will **not** hit a segment at `02:40`. Embedded lyrics/tags and transcript lines are both searched when transcription is enabled; the best-scoring signal wins.

Transcription requires the **ffmpeg** binary on `PATH` (e.g. `ffmpeg` on Debian/Ubuntu/Arch, `brew install ffmpeg` on macOS). If `--transcribe` is set and ffmpeg is missing, srxy prints install hints and exits with code `2`.

**GPU backends:** NVIDIA **CUDA** uses `faster-whisper` (fastest; on Linux, `nvidia-cublas-cu12` from `[semantic]` supplies CUDA 12 libraries). Apple Silicon **MPS** uses Hugging Face **transformers** Whisper via PyTorch (faster-whisper has no MPS support). CPU uses optimized `faster-whisper` int8. If CUDA transcription fails, srxy falls back to transformers on GPU with a stderr warning. Override device with `SRXY_TRANSCRIBE_DEVICE` or `SRXY_SEMANTIC_DEVICE` (`cuda|mps|cpu`).

Default model size: **base** (`--transcribe-model` / `SRXY_TRANSCRIBE_MODEL`). On first use, srxy offers to download and cache weights under `~/.cache/srxy/transcribe-model/`. Transcripts are cached by file content hash in `~/.cache/srxy/cache.db` (override with `SRXY_CACHE_DIR`; disable with `SRXY_CACHE_DISABLE=1`). Use `--max-transcribe-file-size` or `SRXY_TRANSCRIBE_MAX_FILE_SIZE` to skip very large files. When transcription is the best match signal, the default cutoff is **0.25** (`--transcribe-threshold` / `SRXY_TRANSCRIBE_THRESHOLD`).

### Enable everything at once

```bash
srxy "quarterly revenue" ~/Documents --semantic-all --content-only
```

`--semantic-all` turns on text semantic, image semantic, OCR, and transcription.

### Model prefetch and devices

Prefetch models without waiting for first search:

```bash
python -m srxy.model_store semantic-text
python -m srxy.model_store semantic-image
python -m srxy.model_store transcribe
python -m srxy.model_store all
```

Set `SRXY_AUTO_DOWNLOAD=1` to download without prompting (useful for scripts and CI).

Semantic matching and transcription use PyTorch, preferring **CUDA**, then **MPS** (Apple Silicon), then CPU — with a one-time stderr warning on CPU fallback. Override with `SRXY_SEMANTIC_DEVICE`, `SRXY_SEMANTIC_IMAGE_DEVICE`, or `SRXY_TRANSCRIBE_DEVICE` (`cuda|mps|cpu`).

Core dependencies (always installed): `rapidfuzz` and `jellyfish` (phonetic matching).

---

## Use in scripts

The same matchers and content types power the CLI. Import from `srxy`:

`magic_file_search`, `magic_search`, `search`, `Q`, `FieldConfig`, `MatchType`, `SearchResult`

### File search

```python
from pathlib import Path
from srxy import magic_file_search

results = magic_file_search(Path("./src"), "registry", threshold=0.3)
for result in results:
    print(result.path, result.score, result.breakdown)
    for line in result.lines:
        print(f"  line {line.line_number}: {line.text}")

# Include hidden directories and files (e.g. .git)
results = magic_file_search(Path("."), "token", skip_hidden_folders=False)

# Include noise directories (e.g. __pycache__, node_modules)
results = magic_file_search(Path("."), "token", skip_noise_folders=False)

# Search everywhere — disable both skip flags
results = magic_file_search(
    Path("."),
    "token",
    skip_hidden_folders=False,
    skip_noise_folders=False,
)
```

### In-memory search

`magic_search` auto-discovers fields from your items, runs composite matching on each, and keeps the best score. Works with dicts, dataclasses, and Pydantic models. Default threshold is `0.35`.

```python
from srxy import magic_search

items = [{"name": "salt"}, {"name": "salty"}, {"name": "salad"}]
results = magic_search(items, "salat", fields=["name"])
print(results[0].item["name"])  # salad
```

When you need precision, use `search` with the `Q` expression DSL:

```python
from srxy import search, Q, FieldConfig, MatchType

# OR — match if any field scores well
search(items, "salat", where=Q.composite("name") | Q.contains("tags"))

# AND — every branch must clear the threshold
search(items, "spatial", where=Q.all(Q.composite("name"), Q.exact("status")))

# Explicit field config
search(
    people,
    "engineer",
    fields=[
        FieldConfig("role", MatchType.EXACT, weight=2.0),
        FieldConfig("name", MatchType.CONTAINS, weight=1.0),
    ],
    threshold=0.5,
)
```

Boolean scoring: `OR` uses `max(child scores)`, `AND` uses `min(child scores)`. See [Match types](#match-types) for strategies and composite weights.

---

## Match types

All CLI and API search uses these strategies under the hood.

| Type | Behavior |
|------|----------|
| `EXACT` | Case-insensitive full string equality |
| `CONTAINS` | Substring match |
| `PARTIAL` | Prefix or suffix match |
| `FUZZY` | Character-level similarity (rapidfuzz) |
| `PHONETIC` | Sounds-alike (metaphone, soundex, NYSIIS with graduated scoring) |
| `SEMANTIC` | Meaning similarity (optional; see [Power-ups](#power-ups)) |
| `COMPOSITE` | Weighted blend of available atomic matchers (default smart mode) |

Default composite weights: fuzzy 35%, semantic 20%, partial 15%, phonetic 12%, contains 10%, exact 8%. When semantic is disabled, composite skips it and renormalizes the remaining weights. Override per field via `composite_weights` on `Q.composite(...)` or `FieldConfig`.

---

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,semantic]"
./scripts/quality/checks.sh --fix
./scripts/quality/checks.sh
```

Quality gate: Ruff → ShellCheck/shfmt → basedpyright → pip-audit → build → pytest.

- **Local** (`./scripts/quality/checks.sh`): runs all tests (unit + integration).
- **CI**: runs only `pytest -m unit` (fast tests; no semantic model required).

Integration tests (requires `pip install -e ".[semantic]"` and `SRXY_SEMANTIC=1`, set automatically in `tests/integration/conftest.py`):

```bash
pytest -m integration
```

Integration tests load a curated news-style corpus from `tests/fixtures/search_corpus.json` and measure top-k hit rates.
