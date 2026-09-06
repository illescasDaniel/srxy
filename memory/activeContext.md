# Active Context

_Last updated: 2026-09-07_

## Branch

- `cursor/windows-pyside-offline-installer-fb07` off `develop` — Windows fat PySide offline installer (Inno removed). PR targets `develop` (PR #35). Pushed through `95ec559`.
- `develop` is integration for 1.7.0. Release train **1.8.0** lives on `feature/1.8.0` (Unlimited OCR, media preview, optional NSIS, …).

## Current focus

Merge conflict with `develop` resolved — branch ready to merge once CI is green.

## Shipped on this branch (recent)

1. Fat self-extracting `SrxyInstaller.exe` (embed python/venv/share).
2. Removed Inno Setup packaging; CI/docs/tasks/release attach point at the fat PySide zip only.

## Next steps

1. Merge PR #35 into `develop`.
2. **Check macOS installer** — verify build/signing/install path still works.
3. Optional: Authenticode signing for Windows fat exe.
4. **1.8.0 work** — see `feature/1.8.0` (Unlimited OCR draft PR #38, media preview; NSIS only if still wanted as an outer shell).

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory (avoids teammate merge conflicts).
- Removed stale `/delete-worktree-srxy` open items from `progress.md`.
