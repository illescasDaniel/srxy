# Active Context

_Last updated: 2026-09-01_

## Branch

- Worktree on `develop`.

## Current focus

Windows fixes batch — **complete**. Install/sync docs, async settings, matches h-scroll, file-total probe, preview alignment.

## Implemented (this batch)

- **Sync:** `scripts/dev/sync.py` mirrors uv flags; pruning guard for `--no-default-groups` inside `.venv`; deleted `sync`/`sync-win` tasks and wrappers; docs/README/AGENTS restructured around three install paths.
- **Settings:** async snapshot via stdlib `threading.Thread` + loading spinner; per-kind size cache in `build_settings_snapshot`; torch removed from snapshot hot path.
- **Matches:** horizontal scroll via `maxTextLength` + `TextMetrics`; header tracks scroll.
- **Search progress:** parallel file-count probe thread; `0/N` as soon as probe finishes.
- **Preview:** `verticalAlignment: TextEdit.AlignTop` on `previewTextArea` (FluentWinUI3 fix).

## Verified

- `checks-win.ps1 -Fix -Quiet -Scope core,gui` PASSED
- `checks-win.ps1 -Quiet -Scope core,gui` PASSED

## Next steps

1. Manual QA: All Settings opens instantly with spinner; file total appears within seconds on OCR search; matches panel scrolls horizontally; preview text top-aligned on Windows.
2. Manual QA: `uv run --no-project python scripts/dev/sync.py --no-default-groups` from outside activated venv for runtime-only sync.
