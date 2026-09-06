# Active Context

_Last updated: 2026-09-06_

## Branch

- `develop` is integration; feature work on topic branches. Windows PySide installer on PR #35 branch; Unlimited OCR on a new topic branch (Srxy Developer).

## Current focus

**Unlimited OCR** — if user has `[semantic]` dependency group, download/use `baidu/Unlimited-OCR`; else Tesseract. Benchmarks (quality + speed), unit + integration tests. **Stay draft** until Daniel GPU QA.

## Planned (Windows packaging)

Migrate away from Inno Setup commercial-license constraints before srxy revenue matters:

1. **PySide offline wrapper for Windows** — same model as macOS offline `.app` and Linux offline AppImage (full QML wizard; bootstrap Python + wheel in payload). Track: 1.7.0.
2. **NSIS instead of Inno** — replace `srxy-offline.iss` outer shell with NSIS (zlib/libpng; no commercial license). Track: 1.8.

Inno Setup remains fine **for now** — no sales/donations yet (non-commercial under Inno's ~$5k revenue threshold).

## Next steps

1. **Unlimited OCR** — implement + benchmarks + tests; draft PR; Daniel GPU QA before undraft.
2. **Windows installer migration** — finish PySide offline wrapper (PR #35 / CI green) then NSIS later.
3. **Check macOS installer** — verify build/signing/install path still works.

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory (avoids teammate merge conflicts).
- Removed stale `/delete-worktree-srxy` open items from `progress.md`.
