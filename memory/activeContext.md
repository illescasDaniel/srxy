# Active Context

_Last updated: 2026-10-03_

## Branch

- Topic **`feature/unlimited-ocr-dca2`** (draft PR #38 → `feature/1.8.0`). Merged latest `origin/feature/1.8.0` @ `94b3d38` (includes PR #53 macOS offline SDK 26).

## Current focus

1. **Unlimited OCR — VRAM reality check (done this session):** On this RTX 4070 Laptop 8 GiB desktop session (~4.7–5 GiB free), Unlimited OCR **cannot load** (~4.3 GiB bf16 weights OOM). CPU path broken upstream. Gate: `is_unlimited_ocr_available()` now needs ≥6 GiB free CUDA VRAM; otherwise Tesseract. So `uv run task gui` here uses **Tesseract**, not Unlimited.
2. **Speed note:** Cold Tesseract OCR search `egypt` on `/home/daniel/Pictures/Screenshots/` (12 PNGs) ≈ **11.0s**, 3 hits. No Unlimited timing (won't load). Comment in `README.md` (HTML comment under Development).
3. **Infer call fixed** to model-card API (`prompt` + temp `image_file`). No `[semantic]` dep churn this pass.

## Next steps

1. High-VRAM GPU QA still needed before undrafting PR #38 (machine with ≥6 GiB free CUDA); also needs Unlimited runtime deps + transformers-5 compat if pursued later.
2. Do **not** kill user desktop apps to free VRAM for benches.
3. Keep draft PR #38 open (do not merge yet).

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
