# Active Context

_Last updated: 2026-09-06_

## Branch

- Release train **`feature/1.8.0`** (forked from `develop`). Topic branches for 1.8.0 work fork from here (not from `develop`).

## Current focus

1. **Unlimited OCR** (draft PR #38 → `feature/1.8.0`) — `[semantic]` → `baidu/Unlimited-OCR`, else Tesseract; benches + tests; **stay draft** until Daniel GPU QA.
2. **Media preview panel** — preview images, video, and audio in the content preview panel (new topic branch off `feature/1.8.0`).

## Planned (also 1.8.0)

- **NSIS instead of Inno** — replace `srxy-offline.iss` outer shell with NSIS (zlib/libpng).

## Next steps

1. Unlimited OCR — Daniel GPU QA; keep draft until then.
2. Media preview (images / video / audio) — Srxy Developer implements on a branch off `feature/1.8.0`.
3. NSIS Windows installer (later in 1.8.0).

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
