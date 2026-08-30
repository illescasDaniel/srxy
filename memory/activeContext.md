# Active Context

_Last updated: 2026-08-30_

## Branch

- `feature/fixes_1.6.6` — version target **1.7.0**. Worktree `0svx`.

## Current focus

**GUI Settings menu shortcuts** — done. Settings menu: Download All Models / Reset Cache / Reset All Settings + **All Settings…** (models, cache, preferences/`settings.json` reset).

## Touched

- `src/srxy/application/settings.py` (`reset_settings`), `settings_maintenance.py`
- `src/srxy/adapters/inbound/gui/controller.py`, `qml/Main.qml`
- `src/srxy/i18n/en.json`, `es.json`
- `docs/power-ups.md`, tests, `memory/*`

## Verified

- `checks.sh --quiet --fix` + scoped verify **PASSED**; full GUI + settings unit suite 200+ passed.

## Next steps

1. Manual GUI check of menu shortcuts + All Settings dialog.
2. Continue open 1.7.0 QA (OCR progress, installers).
