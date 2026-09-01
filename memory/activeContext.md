# Active Context

_Last updated: 2026-09-01_

## Branch

- Worktree `38v7` on `develop` — GUI cache clear off main thread.

## Current focus

Settings maintenance (cache / model clear) no longer blocks the GUI thread.

## Implemented

- `_SettingsMaintenanceWorker` — `clear_results_cache` / `clear_model_kind` + `build_settings_snapshot` on a `QThread`; controller updates settings JSON and status on finish.
- Status strings while clearing: `settings.status.clearing_cache` / `clearing_model` (EN/ES).
- Tests: async wait in `test_gui_controller` cache/model clear tests.

## Verified

- `checks.sh --quiet --fix --scope=core,gui --no-cache` PASSED (959 tests).
- `copy-venv-to-worktree-srxy` — venv copied; `srxy.__file__` under worktree; torch `2.13.0+cu130 cuda=True`.

## Next steps

1. Manual QA: Settings → Reset Cache… — UI should stay responsive; status shows clearing then cleared.
2. Optional follow-up: defer `openSettings()` snapshot build (still walks model dirs on main thread when opening All Settings).
