# Active Context

_Last updated: 2026-10-03_

## Branch

- Topic **`feature/unlimited-ocr-dca2`** (draft PR #38 → `feature/1.8.0`). Merged latest `origin/feature/1.8.0` @ `1deb4ef` (merge commit `24b66d0`).

## Current focus

1. **Unlimited OCR** — stay draft until Daniel GPU QA.
2. Post-merge fixes committed: `pypdf` ≥6.19.0, OCR unit-test mocks for `[semantic]` installs, CUDA VRAM release on model reset + integration autouse unload.

## Next steps

1. Daniel GPU QA for Unlimited OCR; keep draft until then.
2. Optional UX: GUI/TUI OCR help copy still describes Tesseract only — update when product wants Unlimited mentioned in the info panel.

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
