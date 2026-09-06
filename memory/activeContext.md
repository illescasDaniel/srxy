# Active Context

_Last updated: 2026-09-06_

## Branch

- Release train **`feature/1.8.0`** (forked from `develop`). Topic branches for 1.8.0 work fork from here (not from `develop`).

## Current focus

1. **Unlimited OCR** (draft PR #38 → `feature/1.8.0`) — `[semantic]` → `baidu/Unlimited-OCR`, else Tesseract; benches + tests; **stay draft** until Daniel GPU QA. **Not touched by this session** — Team Lead is rebasing it separately.
2. **Media preview panel** — done this session on `feature/media-preview-panel` (off `feature/1.8.0`, draft PR into `feature/1.8.0`). Images/audio/video now preview in-panel (Pillow-decoded `data:` URI for images, `QtMultimedia` player for audio/video); text/document preview untouched. See `memory/progress.md` for the file-by-file breakdown.

## Planned (also 1.8.0)

- **NSIS instead of Inno** — replace `srxy-offline.iss` outer shell with NSIS (zlib/libpng).

## Next steps

1. Unlimited OCR — Daniel GPU QA; keep draft until then (separate branch/PR, do not touch).
2. Media preview panel PR — awaiting review/merge into `feature/1.8.0`; possible follow-ups: animated GIF playback (currently first-frame only), transcript/OCR-matched-line context alongside the media viewer, RAW/HEIC preview correctness sanity check on real camera files.
3. NSIS Windows installer (later in 1.8.0).

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
