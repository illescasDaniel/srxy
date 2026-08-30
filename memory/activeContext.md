# Active Context

_Last updated: 2026-08-30_

## Branch

- `feature/fixes_1.6.6` — version target **1.7.0**.

## Current focus

Applied from worktree `cursor/5852d6f1`: **GUI Settings menu** — Download All Models / Reset Cache / Reset All Settings + **All Settings…**. Parent gate passed; hardening `follow_system_color_scheme` for bare `QCoreApplication` in GUI tests.

## Prior (same branch)

- Progress bar is file-scan only; parallel light + heavy search.
- Persist GUI search options/filters; live filter validation (other worktrees).

## Next steps

1. Manual GUI check: Settings menu shortcuts + All Settings dialog.
2. Manual QA leftovers (OCR progress bar, mixed light/heavy streaming, installers).
3. `/delete-worktree-srxy` for `cursor/5852d6f1` (`0svx`) when ready.
