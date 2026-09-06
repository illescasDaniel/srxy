# Active Context

_Last updated: 2026-09-06_

## Branch

- Release train **`feature/1.8.0`** (forked from `develop`). Topic branches for 1.8.0 work fork from here (not from `develop`). Unlimited OCR lives on `feature/unlimited-ocr-dca2` (draft PR #38 → `feature/1.8.0`).

## Current focus

1. **Unlimited OCR** (draft PR #38 → `feature/1.8.0`) — `[semantic]` → `baidu/Unlimited-OCR`, else Tesseract; benches + tests; **stay draft** until Daniel GPU QA. Implemented: `get_ocr_engine()` in `src/srxy/adapters/outbound/ocr/ocr_text.py` uses `UnlimitedOcrEngine` (`baidu/Unlimited-OCR` via transformers, `trust_remote_code=True`) whenever `[semantic]` (torch + transformers) is importable — checked by `unlimited_ocr_deps_installed()` — else falls back to `TesseractEngine` unchanged. Model download/clear mirrors the CLIP/semantic-text/transcribe pattern in `model_store.py` (`ensure_unlimited_ocr_model`, `unlimited_ocr_model_dir`, own CLI target `unlimited-ocr`, not part of the `all` bundle so bulk "download all" stays lightweight). Cache key variant tracks the active backend. Benchmarks: `scripts/bench_ocr_unlimited_vs_tesseract.py` (`uv run task bench-ocr`). Unit tests mock the Unlimited path; a new `tests/integration/test_ocr_unlimited_backend.py` is real-model but skips without `[semantic]` + cached model (no GPU/download forced in CI). **Stay draft** until Daniel runs GPU QA (accuracy + throughput vs Tesseract) — see `memory/progress.md` → Open.
2. **Media preview panel** — preview images, video, and audio in the content preview panel (new topic branch off `feature/1.8.0`).

## Planned (also 1.8.0)

- **NSIS instead of Inno** — replace `srxy-offline.iss` outer shell with NSIS (zlib/libpng).

## Next steps

1. Unlimited OCR — Daniel GPU QA (accuracy + throughput vs Tesseract); keep draft until then.
2. Media preview (images / video / audio) — Srxy Developer implements on a branch off `feature/1.8.0`.
3. NSIS Windows installer (later in 1.8.0).
4. Windows installer migration — finish PySide offline wrapper (PR #35 / CI green), parity with macOS `.app` / Linux AppImage offline wizard.
5. Check macOS installer — verify build/signing/install path still works.

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
