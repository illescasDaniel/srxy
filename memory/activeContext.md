# Active Context

_Last updated: 2026-09-01_

## Branch

- Worktree on `feature/improve_buttons` (develop-oriented work).

## Current focus

Manual QA items from `progress.md` — **confirmed done by user (2026-09-01)**.

## Planned (Windows packaging)

Migrate away from Inno Setup commercial-license constraints before srxy revenue matters:

1. **PySide offline wrapper for Windows** — same model as macOS offline `.app` and Linux offline AppImage (full QML wizard; bootstrap Python + wheel in payload).
2. **NSIS instead of Inno** — replace `srxy-offline.iss` outer shell with NSIS (zlib/libpng; no commercial license). Likely after or alongside step 1 depending on whether NSIS wraps the PySide launcher or the headless engine.

Inno Setup remains fine **for now** — no sales/donations yet (non-commercial under Inno's ~$5k revenue threshold).

## Implemented (2026-09-01 session)

- Inno: `ExtraDiskSpaceRequired`, tessdata byte sizes, `RefreshDiskSpaceLabel`, `n/m - title` steps, uninstall extras page, `--cancel-file`, `CancelButtonClick` procedure (ISCC compile fix).
- Engine: `InstallOptions.ui_language`, prefix `settings.json` on first install, pip/CUDA heartbeats + cooperative cancel (`cancel.py`), `cleanup_user_data()` on uninstall.
- PySide installer: uninstall checkboxes (cache/settings/models, default on).
- Tests: `test_installer_cancel_cleanup.py`, ISS contract tests, install-flow language tests.

## Next steps

1. **Windows installer migration** — PySide offline wrapper + NSIS (see Planned).
2. **Check macOS installer** — verify build/signing/install path still works.

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory (avoids teammate merge conflicts).
- Removed stale `/delete-worktree-srxy` open items from `progress.md`.
