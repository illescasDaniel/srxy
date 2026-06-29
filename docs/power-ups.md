# Power-ups

Off by default. Enable per run (flags) or persist (`SRXY_*` env vars).

## OCR

Text in photos and embedded PDF images.

```bash
srxy "invoice" ./photos --ocr --content-only
export SRXY_OCR=1
```

Default: images via EXIF; PDFs via `pypdf` embedded text. `--ocr` adds Tesseract on top (needs `tesseract` on `PATH`). PDF body text still from `pypdf`; matches show page number.

Cache: `~/.cache/srxy/cache.db` (`SRXY_CACHE_DIR`). `SRXY_CACHE_DISABLE=1` to off. `SRXY_CACHE_DEBUG=1` for stderr logs. `--max-ocr-file-size` / `SRXY_OCR_MAX_FILE_SIZE` optional cap.

## Text semantic

Meaning-based text match (`srxy[semantic]` required):

```bash
srxy "revenue" ./docs --semantic --content-only
export SRXY_SEMANTIC=1
```

Model: `paraphrase-multilingual-MiniLM-L12-v2`. Cached under `~/.cache/srxy/semantic-model`. Embeddings in `cache.db`; model id in cache key.

## Image semantic (CLIP)

Visual description search (`srxy[semantic]`):

```bash
srxy "sunset over water" ~/Pictures --semantic-image --content-only
export SRXY_SEMANTIC_IMAGE=1
```

CLIP `clip-ViT-B-32`. Default threshold **0.18** (`--semantic-image-threshold`). RAW via `rawpy` preview.

## Transcription

Spoken words in audio/video (`srxy[semantic]` + **ffmpeg**):

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

**GPU:** CUDA → `faster-whisper` (+ `nvidia-cublas-cu12` on Linux). MPS → transformers Whisper. CPU → faster-whisper int8. Override: `SRXY_TRANSCRIBE_DEVICE` / `SRXY_SEMANTIC_DEVICE` (`cuda|mps|cpu`).

Model **base** by default. Cache: `~/.cache/srxy/transcribe-model/`. Transcript lines in `cache.db`. Threshold **0.25** (`--transcribe-threshold`).

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

Device order: CUDA → MPS → CPU (stderr warning on CPU fallback). Override per model family via `SRXY_*_DEVICE`.

Core deps (always): `rapidfuzz`, `jellyfish`.
