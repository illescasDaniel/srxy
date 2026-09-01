# Active Context

_Last updated: 2026-09-01_

## Branch

- `cursor/windows-pyside-offline-installer-fb07` off `develop` — Windows installer migration step (1): PySide offline wrapper. PR targets `develop`.

## Current focus

Windows installer migration step (1) — **PySide offline wrapper shipped in this branch** (see `progress.md` → "Windows PySide offline wrapper"). Step (2) (NSIS) is a separate follow-up PR; do not implement NSIS on this branch.

## Planned (Windows packaging)

Migrate away from Inno Setup commercial-license constraints before srxy revenue matters:

1. **PySide offline wrapper for Windows** — same model as macOS offline `.app` and Linux offline AppImage (full QML wizard; bootstrap Python + wheel in payload). **Done** on `cursor/windows-pyside-offline-installer-fb07`: `packaging/windows/build-offline-pyside.ps1` / `prune-pyside.ps1` / `smoke-offline-pyside.ps1`, new `SrxyInstaller.exe` launcher (`src/srxy/resources/windows/SrxyInstallerLauncher.cs`), CI job `build-offline-pyside` in `.github/workflows/windows-installer.yml`, contract tests in `tests/unit/test_windows_pyside_packaging.py`. Reused the existing `SRXY_INSTALLER_PAYLOAD` contract and shared install engine as-is — no engine changes needed (already Windows-aware from prior Inno work).
2. **NSIS instead of Inno** — replace `srxy-offline.iss` outer shell with NSIS (zlib/libpng; no commercial license). Separate follow-up PR; will decide whether NSIS wraps the new PySide launcher (from step 1) or the headless engine directly, and whether the PySide zip becomes the shipped/released Windows offline artifact.

Inno Setup remains fine **for now** — no sales/donations yet (non-commercial under Inno's ~$5k revenue threshold). The Inno installer is untouched by step (1) and keeps shipping to GitHub Releases; the PySide zip is currently a CI build artifact only (not yet attached to Releases).

## Implemented (2026-09-01 session)

- Inno: `ExtraDiskSpaceRequired`, tessdata byte sizes, `RefreshDiskSpaceLabel`, `n/m - title` steps, uninstall extras page, `--cancel-file`, `CancelButtonClick` procedure (ISCC compile fix).
- Engine: `InstallOptions.ui_language`, prefix `settings.json` on first install, pip/CUDA heartbeats + cooperative cancel (`cancel.py`), `cleanup_user_data()` on uninstall.
- PySide installer: uninstall checkboxes (cache/settings/models, default on).
- Tests: `test_installer_cancel_cleanup.py`, ISS contract tests, install-flow language tests.

## Next steps

1. **NSIS Windows installer** — replace Inno's outer shell using the PySide wrapper from step 1 (separate PR).
2. **Check macOS installer** — verify build/signing/install path still works.

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory (avoids teammate merge conflicts).
- Removed stale `/delete-worktree-srxy` open items from `progress.md`.
