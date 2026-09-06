# Active Context

_Last updated: 2026-09-07_

## Branch

- `cursor/windows-pyside-offline-installer-fb07` off `develop` — Windows fat PySide offline installer (Inno removed). PR targets `develop`.

## Current focus

Commit Inno removal + push after quality gate.

## Just completed

1. Fat SFX `SrxyInstaller.exe` (commit `8d914f9`).
2. Removed all Inno Setup packaging/docs/CI/tasks; promoted PySide scripts to `build-offline.ps1` / `smoke-offline.ps1`; release attaches the fat zip.

## Next steps

1. Finish quality gate if still running; push branch.
2. Open/update PR targeting `develop`.
3. Optional later: Authenticode signing; NSIS outer shell only if needed.
