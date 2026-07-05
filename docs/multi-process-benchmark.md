# Parallel File Search Benchmark

> **Status:** Temporary reference — results captured during implementation of
> `ThreadPoolExecutor` / `ProcessPoolExecutor`-based parallelism and hot-path
> optimisations in `magic_file_search`.

## Machine

| Property | Value |
|---|---|
| OS | Linux x86_64 (CachyOS) |
| CPU | Intel Core i9-13900HX (16P+16E cores, 32 threads) |
| Python | 3.14.6 |
| Fixture files | 22 |

---

## Round 1 — ThreadPoolExecutor for heavy modes (OCR / Whisper / CLIP)

### What changed

**`src/srxy/matchers/semantic.py`** — Fixed a thread-safety bug in the lazy model load.
Two concurrent threads could both call `_load_model()` and load a 400 MB
`SentenceTransformer` model twice.  Added double-checked locking via
`threading.Lock`.

**`src/srxy/file_search.py`** — `magic_file_search` now uses
`concurrent.futures.ThreadPoolExecutor` when at least one *heavy* search mode
is active (OCR, transcribe, or semantic image).  Pure-text searches stay
sequential because thread-pool creation overhead exceeds the benefit for small
file sets.

### Why `ThreadPoolExecutor` for heavy modes

| Concern | `ThreadPoolExecutor` | `ProcessPoolExecutor` |
|---|---|---|
| Model re-loading | Zero — threads share one loaded model | Each spawned process re-loads from disk (seconds) |
| Cross-platform safety | Identical on Linux/macOS/Windows | `fork` unsafe on macOS; `spawn` forces model re-load |
| GIL for heavy work | Released by tesseract subprocesses, PyTorch, file I/O | N/A |

### Results — fixture set (22 files, warm cache)

| Scenario | Baseline | Threaded | Δ |
|---|---|---|---|
| Text — full tree | 40 ms | 41 ms | ≈ same (sequential) |
| Text — documents folder | 13 ms | 25 ms | ≈ same (σ noise) |
| OCR — `ocr/` folder | 6 ms | 7 ms | ≈ same (cache hits) |
| OCR — `samples/ocr/` folder | 4 ms | 5 ms | ≈ same (cache hits) |

### Results — cold cache

| Scenario | Baseline | Threaded | Speedup |
|---|---|---|---|
| Text — full tree | 105 ms | 99 ms | ≈ same |
| Text — documents folder | 29 ms | 38 ms | ≈ same |
| OCR — `ocr/` folder (2 files) | **8,691 ms** | **4,364 ms** | **2.0×** |
| OCR — `samples/ocr/` folder (1 file) | 419 ms | 490 ms | ≈ same (1 file) |

The `ocr/` folder holds two OCR files.  In parallel they run concurrently and
complete in ~max(t₁, t₂) instead of t₁+t₂ — the expected near-linear speedup.

### Threading thrashes for large text-only

Extending threading to text-only searches (pure Python + short C-extension calls)
made them **2–5× slower** across all thread counts tested (2, 4, 8, 32).  Root
causes:

- **GIL thrashing** — rapidfuzz, jellyfish, and PyTorch cosine calls release
  the GIL for only microseconds; thread switching overhead dominates.
- **`lru_cache` lock contention** — `get_atomic_matcher()` is called per word
  per file; its internal lock serialised threads further.

Conclusion: threading is **disabled** for pure-text searches.

---

## Round 2 — Hot-path optimisations + ProcessPoolExecutor for large text-only

### What changed

**`src/srxy/matchers/composite.py`** — `CompositeMatcher` pre-fetches all
atomic matchers once in `__init__` instead of calling `get_atomic_matcher()`
(and acquiring its `lru_cache` lock) on every `score_with_breakdown` call.  For
a 500-file search this eliminates ~200 000 lock acquisitions.

**`src/srxy/matchers/phonetic.py`** — Added `@lru_cache` on a
`_phonetic_codes(text)` helper that computes `metaphone`, `soundex`, and `nysiis`
together.  The same query string is compared against every line in every file;
before this change those three jellyfish calls were repeated ~120 000 times
for a 500-file search.

**`src/srxy/file_search.py`** — Added a `ProcessPoolExecutor` path for large
pure-text searches (≥ 50 files, no OCR/transcribe/CLIP, no semantic-text
matching).  Each worker process is warmed up by an `initializer` that creates a
`CompositeMatcher` once; subsequent tasks reuse it.  This bypasses the GIL
entirely — text matching is CPU-bound by Python bytecode and cannot benefit
from threads.

### Execution strategy matrix

| Condition | Executor |
|---|---|
| OCR / transcribe / CLIP active | `ThreadPoolExecutor` (GIL released by heavy C/subprocess work) |
| ≥ 50 files, text-only, no semantic-text | `ProcessPoolExecutor` (bypasses GIL; workers pre-warm matchers) |
| Everything else | Sequential loop |

### Results — 500 synthetic text files, warm cache, no `SRXY_SEMANTIC`

| Variant | Mean | Min | Speedup vs sequential |
|---|---|---|---|
| Sequential (`max_workers=1`) | 565 ms | 531 ms | 1× (baseline) |
| Process pool (32 workers) | 117 ms | 110 ms | **4.8×** |
| Process pool (8 workers) | 140 ms | 125 ms | **4.0×** |
| Process pool (4 workers) | 268 ms | 235 ms | **2.1×** |
| Process pool (2 workers) | 488 ms | 345 ms | 1.2× |

32 workers on 500 files delivers **4.8× speedup** (565 ms → 117 ms).  The
sub-linear scaling vs 32 cores is expected: uneven file sizes cause some workers
to finish earlier, and IPC for result objects adds a small constant.

### Results — 500 synthetic text files, warm cache, with `SRXY_SEMANTIC=1`

When semantic text matching is enabled the process pool is disabled (loading a
~400 MB model per worker would be prohibitively slow and memory-heavy).  The
`CompositeMatcher` pre-fetch and phonetic cache still apply:

| Variant | Mean |
|---|---|
| Before Round-2 changes | ~3 600 ms |
| After Round-2 changes (sequential) | ~2 825 ms |
| Improvement | **~21%** |

### Small-directory regression check (no regression)

| Scenario | Before | After |
|---|---|---|
| Synthetic text — 25 files | 84 ms | 81 ms |
| Text — full tree (22 fixtures) | 40 ms | 14 ms |
| Text — documents folder | 16 ms | 14 ms |

No regression on small directories.  The process pool is only activated at
≥ 50 files, so small searches keep the original sequential path.

---

## Benchmark script

Source: [`scripts/bench_file_search.py`](../scripts/bench_file_search.py)

```bash
# warm cache (default)
python scripts/bench_file_search.py --label label --iters 3

# cold cache (forces re-computation)
python scripts/bench_file_search.py --label label --iters 3 --cold
```
