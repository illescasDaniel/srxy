# Active Context

_Last updated: 2026-10-03_

## Branch

- Topic **`feature/unlimited-ocr-dca2`** (draft PR #38 → `feature/1.8.0`). Just merged latest `origin/feature/1.8.0` (@ `1deb4ef`: media preview #39, recent searches #42, DnD path #41, Search top-fixed #51, folder-name search #40, develop sync #52).

## Current focus

1. **Unlimited OCR** (draft PR #38 → `feature/1.8.0`) — `[semantic]` → `baidu/Unlimited-OCR`, else Tesseract; benches + tests; **stay draft** until Daniel GPU QA. Implemented: `get_ocr_engine()` in `src/srxy/adapters/outbound/ocr/ocr_text.py` uses `UnlimitedOcrEngine` whenever `[semantic]` (torch + transformers) is importable — checked by `unlimited_ocr_deps_installed()` — else falls back to `TesseractEngine`. Model download/clear in `model_store.py` (`ensure_unlimited_ocr_model`, CLI target `unlimited-ocr`, not in `all`). Cache key variant tracks active backend. Benchmark: `uv run task bench-ocr`. Unit tests mock Unlimited; integration skips without `[semantic]` + cached model.
2. After merge: run quality gate and fix any conflicts/breakage from `feature/1.8.0` (media preview, folder search, gate unification, installer).

## Next steps

1. Quality gate clean after `feature/1.8.0` merge.
2. Daniel GPU QA (accuracy + throughput vs Tesseract); keep draft until then.
3. Visual smoke optional: chevron + media poster/icons on a real display (landed via #39).

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
