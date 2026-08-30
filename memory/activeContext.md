# Active Context

_Last updated: 2026-08-30_

## Branch

- `feature/fixes_1.6.6` — version target **1.7.0**.

## Current focus

**GUI persist fix** — restore no longer wiped by pre-probe clamp; prefs write on OK; save failures surfaced.

## Touched (this fix)

- `src/srxy/adapters/inbound/gui/controller.py` — probe-aware clamp; write on OK + shutdown; error on save fail
- `src/srxy/application/settings.py` — `save_*` return bool
- `src/srxy/i18n/en.json`, `es.json` — `gui.settings.save_failed`
- `tests/gui/test_gui_controller.py` — semantic restore / immediate write / save-fail tests; QGuiApplication qapp
- `memory/decisions.md`

## Verified

- GUI suite 199 passed; persist-related tests 13 passed.
- Host note: `~/.config/srxy` may be root-owned from sandbox runs — user must `sudo chown -R "$USER:$USER" ~/.config/srxy` for writes as daniel.

## Next steps

1. User: fix ownership of `~/.config/srxy`, then Persist + Similar meaning + OK + relaunch.
2. Prior open: OCR progress visual check; installer QA.
