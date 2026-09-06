# Active Context

_Last updated: 2026-09-06_

## Branch

- `develop` is integration for 1.7.0. Release train **1.8.0** lives on `feature/1.8.0` (Unlimited OCR, media preview, NSIS, …). Topic branches fork from the matching train.

## Current focus

**1.7.0 packaging** — Windows PySide offline wrapper (PR #35) + Check macOS installer.

## Planned (Windows packaging)

1. **PySide offline wrapper for Windows** — track: **1.7.0** (PR #35).
2. **NSIS instead of Inno** — track: **1.8.0** (`feature/1.8.0`).

Inno Setup remains fine **for now** — no sales/donations yet.

## Next steps

1. **Windows installer migration** — finish PySide offline wrapper (PR #35 / CI green).
2. **Check macOS installer** — verify build/signing/install path still works.
3. **1.8.0 work** — see `feature/1.8.0` (Unlimited OCR draft PR #38, media preview, NSIS).

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory (avoids teammate merge conflicts).
- Removed stale `/delete-worktree-srxy` open items from `progress.md`.
