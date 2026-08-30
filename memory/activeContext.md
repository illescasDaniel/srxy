# Active Context

_Last updated: 2026-08-30_

## Branch

- `feature/fixes_1.6.6` — version target **1.7.0**.

## Current focus

Applied from worktree `cursor/5852d6f1`: **GUI Settings menu** — Download All Models / Reset Cache / Reset All Settings + **All Settings…** dialog (models, cache, preferences/`settings.json` reset).

## Prior (same branch)

- Progress bar is file-scan only (activity/OCR page % no longer drives the bar).
- Parallel light + heavy search (text inline, OCR/CLIP/transcribe in pool).

## Touched (this apply)

- `src/srxy/application/settings.py` (`reset_settings`), `disk_usage.py`, `settings_maintenance.py`
- `src/srxy/adapters/inbound/gui/controller.py`, `qml/Main.qml`
- `src/srxy/i18n/en.json`, `es.json`
- `docs/power-ups.md`, tests, `memory/*`

## Next steps

1. Finish merge quality gate on parent.
2. Manual GUI check: Settings menu shortcuts + All Settings dialog.
3. Manual QA leftovers (OCR progress bar, mixed light/heavy streaming, installers).
4. `/delete-worktree-srxy` for `cursor/5852d6f1` (`0svx`) when ready.
