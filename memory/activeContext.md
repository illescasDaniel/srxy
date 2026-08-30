# Active Context

_Last updated: 2026-08-30_

## Branch

- `develop` — continuous development trunk (post–feature-branch work lives here). Version target **1.7.0**.

## Current focus

QML click-driven GUI flow tests: `tests/gui/helpers.py` + `tests/gui/test_gui_flows.py` (path/query/options/filters → Search → results/progress). Scoped to the **gui** quality-gate bucket.

## Verified

- `checks.sh --quiet --fix` PASSED; `checks.sh --quiet --gui` PASSED.
- `QT_QPA_PLATFORM=offscreen uv run pytest tests/gui/test_gui_flows.py --durations=10` → **3 passed in ~1.6s**
  - happy path ~0.84s call
  - names-only ~0.50s call
  - filters validation ~0.14s call
- Wall clock including process start ~3s.

## Next steps

1. Manual QA items still open in `progress.md` (persist / settings / OCR progress).
2. Worktree cleanup (`cursor/5648e20a`, `cursor/5852d6f1`) when ready.
