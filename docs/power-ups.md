# Power-ups

Off by default. Enable per run (flags) or persist (`SRXY_*` env vars).

## OCR

Text in photos and embedded PDF images.

```bash
srxy "invoice" ./photos --ocr --content-only
export SRXY_OCR=1
```

Default: images via EXIF; PDFs via `pypdf` embedded text. `--ocr` adds Tesseract on top — see [Installation](installation.md). PDF body text still from `pypdf`; matches show page number.

Cache: encrypted `~/.cache/srxy/cache.db` (`SRXY_CACHE_DIR`). Key file: `~/.cache/srxy/.cache_key` (mode `600`). Override key with `SRXY_CACHE_KEY` (Fernet). `SRXY_CACHE_DISABLE=1` to off. `SRXY_CACHE_DEBUG=1` for stderr logs.

Default OCR file cap: **50 MiB** (`--max-ocr-file-size` / `SRXY_OCR_MAX_FILE_SIZE`).

## Text semantic

Meaning-based text match (`srxy[semantic]` required):

```bash
srxy "revenue" ./docs --semantic --content-only
export SRXY_SEMANTIC=1
```

Model: `paraphrase-multilingual-MiniLM-L12-v2` (override: `SRXY_SEMANTIC_MODEL`, local path: `SRXY_SEMANTIC_MODEL_PATH`). Cached under `~/.cache/srxy/semantic-model`. Embeddings in encrypted `cache.db`; model id in cache key.

## Image semantic (CLIP)

Visual description search (`srxy[semantic]`):

```bash
srxy "sunset over water" ~/Pictures --semantic-image --content-only
export SRXY_SEMANTIC_IMAGE=1
```

CLIP `clip-ViT-B-32` (override: `SRXY_SEMANTIC_IMAGE_MODEL`, local path: `SRXY_SEMANTIC_IMAGE_MODEL_PATH`). Default threshold **0.18** (`--semantic-image-threshold`). Queries shorter than **4** characters are ignored for CLIP. Device override: `SRXY_SEMANTIC_IMAGE_DEVICE`. RAW via `rawpy` preview.

## Transcription

Spoken words in audio/video (`srxy[semantic]` + ffmpeg — see [Installation](installation.md)):

```bash
srxy "quarterly earnings" ~/Recordings --transcribe --content-only
export SRXY_TRANSCRIBE=1
```

Default: container tags only. `--transcribe` adds Whisper. Audio extensions + `.mp4`, `.m4v`, `.mov`.

```
transcript at 02:40  ·  score 0.34
   │ And all the «other boys»
```

Timestamp in location header, not searchable text. Missing ffmpeg → exit `2` with hints.

**GPU:** CUDA → `faster-whisper` (+ `nvidia-cublas-cu12` on Linux and Windows). MPS → transformers Whisper. CPU → faster-whisper int8. Status shows device/backend (e.g. `cuda/faster-whisper`). Override: `SRXY_TRANSCRIBE_DEVICE` / `SRXY_SEMANTIC_DEVICE` (`cuda|mps|cpu`).

Model **base** by default (`--transcribe-model` / `SRXY_TRANSCRIBE_MODEL`). Cache: `~/.cache/srxy/transcribe-model/`. Local paths: `SRXY_TRANSCRIBE_FASTER_WHISPER_MODEL_PATH`, `SRXY_TRANSCRIBE_TRANSFORMERS_MODEL_PATH`. Transcript lines in encrypted `cache.db`. Threshold **0.25** (`--transcribe-threshold`). Default transcribe file cap: **500 MiB** (`--max-transcribe-file-size` / `SRXY_TRANSCRIBE_MAX_FILE_SIZE`).

## All at once

```bash
srxy "quarterly revenue" ~/Documents --semantic-all --content-only
```

`--semantic-all` = semantic + image semantic + OCR + transcribe.

## Model prefetch

```bash
python -m srxy.model_store semantic-text
python -m srxy.model_store semantic-image
python -m srxy.model_store transcribe
python -m srxy.model_store all
```

`SRXY_AUTO_DOWNLOAD=1` for non-interactive download.

## Managing cache

Downloaded model weights and scan results are stored separately under `~/.cache/srxy/`:

| Path | Contents |
|------|----------|
| `semantic-model/` | Text semantic model weights |
| `semantic-image-model/` | CLIP model weights |
| `transcribe-model/` | Whisper / faster-whisper weights |
| `cache.db` | Encrypted OCR, transcripts, embeddings, document-text cache |
| `.cache_key` | Fernet key for `cache.db` payloads (created on first use) |

Custom model paths via `SRXY_SEMANTIC_MODEL_PATH`, `SRXY_SEMANTIC_IMAGE_MODEL_PATH`, `SRXY_TRANSCRIBE_FASTER_WHISPER_MODEL_PATH`, `SRXY_TRANSCRIBE_TRANSFORMERS_MODEL_PATH`, and `SRXY_CACHE_DIR`. LRU cap: `SRXY_CACHE_MAX_BYTES`.

Upgrading from older srxy versions clears unencrypted cache entries on first open (schema v2).

### Clear downloaded models

Removes model weights only. Models re-download on next use (or run [Model prefetch](#model-prefetch) again).

```bash
./scripts/clear_models.sh                    # all models
./scripts/clear_models.sh semantic-text
./scripts/clear_models.sh semantic-image
./scripts/clear_models.sh transcribe
```

Or without the script:

```bash
python -m srxy.model_store clear all
python -m srxy.model_store clear semantic-text
```

### Clear results cache

Removes `cache.db` and `.cache_key`. Scan results rebuild on the next run.

```bash
./scripts/clear_results_cache.sh
```

Or:

```bash
python -c "from srxy.cache import clear_results_cache; clear_results_cache()"
```

Device order: CUDA → MPS → CPU (stderr warning on CPU fallback). Override per model family via `SRXY_*_DEVICE` (including `SRXY_SEMANTIC_IMAGE_DEVICE`).

Core deps include fuzzy matching (`rapidfuzz`, `jellyfish`), document parsers, Pillow, Textual, `cryptography` (cache encryption), and more — see `pyproject.toml`.
