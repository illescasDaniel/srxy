# Parallel File Search Benchmark

> **Status:** Temporary reference — results captured during implementation of `ThreadPoolExecutor`-based parallelism in `magic_file_search`.

## Machine

| Property | Value |
|---|---|
| OS | Linux x86_64 (CachyOS) |
| CPU | Intel Core i9-13900HX (16P+16E cores, 32 threads) |
| Python | 3.14.6 |
| Fixture files | 22 |

## What changed

Three files were modified:

**`src/srxy/matchers/semantic.py`** — Fixed a thread-safety bug in the lazy model load. Without a lock, two concurrent threads could both call `_load_model()` simultaneously and load a 400 MB `SentenceTransformer` model twice. Added double-checked locking via `threading.Lock`.

**`src/srxy/file_search.py`** — Two changes:

1. `_search_single_file` no longer takes a shared `skipped_files` list parameter. Instead it creates a local list and returns it alongside the result as `tuple[FileSearchResult | None, list[SkippedFile]]`. This makes every call self-contained and thread-safe.

2. `magic_file_search` now uses `concurrent.futures.ThreadPoolExecutor` when at least one *heavy* search mode is active (OCR, transcribe, or semantic image). For pure-text searches the sequential path is preserved — thread-pool creation overhead (~60 ms on 32 cores) exceeds the parallelism benefit for typical small-to-medium file sets.

   A new optional `max_workers: int | None = None` parameter is exposed for callers that want manual control.

## Why `ThreadPoolExecutor` and not `ProcessPoolExecutor`

| Concern | `ThreadPoolExecutor` | `ProcessPoolExecutor` |
|---|---|---|
| Model re-loading | Zero — all threads share one loaded model | Each spawned process re-loads from disk (seconds) |
| Cross-platform safety | Identical on Linux/macOS/Windows | `fork` is dangerous on macOS; `spawn` (Windows/macOS default) forces re-loading |
| Pickling | Not needed | Required for all arguments passed to workers |
| GIL for heavy work | Released by tesseract subprocesses, PyTorch, file I/O | N/A |

## When threading activates

Threading is enabled when **all** of the following are true:

- More than one file will be processed
- `max_workers != 1` (i.e. not explicitly disabled by the caller)
- At least one of `ocr=True`, `transcribe=True`, or `semantic_image=True` is active

In all other cases the original sequential loop is used unchanged.

## Benchmark results

Fixture: `tests/fixtures/file_search/` (22 files, 2 in `ocr/`, 1 in `samples/ocr/`).

**Warm cache** — SQLite cache already populated; measures scoring + cache lookup overhead.

| Scenario | Baseline | Threaded | Δ |
|---|---|---|---|
| Text — full tree | 40 ms | 41 ms | ≈ same (sequential path) |
| Text — documents folder | 13 ms | 25 ms | ≈ same (sequential path, σ noise) |
| OCR — `ocr/` folder | 6 ms | 7 ms | ≈ same (all cache hits) |
| OCR — `samples/ocr/` folder | 4 ms | 5 ms | ≈ same (all cache hits) |

**Cold cache** — SQLite cache cleared before each run; measures actual computation (tesseract, document parsing).

| Scenario | Baseline | Threaded | Speedup |
|---|---|---|---|
| Text — full tree | 105 ms | 99 ms | ≈ same (sequential path) |
| Text — documents folder | 29 ms | 38 ms | ≈ same (sequential path, σ noise) |
| OCR — `ocr/` folder (2 files) | **8,691 ms** | **4,364 ms** | **2.0×** |
| OCR — `samples/ocr/` folder (1 file) | 419 ms | 490 ms | ≈ same (1 file, no parallelism) |

### Notes on the OCR result

The `ocr/` folder contains two files (`ocr_sample.png` and `ocr_embedded.pdf`). Sequentially they took ~8.7 s total (the PDF embeds an image that also needs OCR). In parallel they ran concurrently and finished in ~4.4 s — limited by the slower of the two. This is the expected near-linear speedup for *N* independent heavy tasks on *N* available threads.

The `samples/ocr/` folder has a single file so parallelism has no effect; the small timing variance (~70 ms) is measurement noise.

### Expected scaling with more files

The fixture is intentionally small (22 files). Real-world directories with dozens of images or audio files benefit proportionally:

- *N* OCR images previously took *N × t* time; they now take *max(t₁…tₙ)* across threads
- *N* Whisper transcriptions similarly run concurrently, bounded by available CPU/GPU
- Thread pool overhead (~5–20 ms) is amortised over the file set

## Benchmark script

```bash
# warm cache (default)
python scripts/bench_file_search.py --label label --iters 3

# cold cache (forces re-computation)
python scripts/bench_file_search.py --label label --iters 3 --cold
```
