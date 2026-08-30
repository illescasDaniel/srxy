# Active Context

_Last updated: 2026-08-30_

## Branch

- `feature/fixes_1.6.6` — version target **1.7.0**. Just applied worktree `cursor/79bcea9a` (Magika/preview + GUI search responsiveness + spinner/progress + preview scrollbar).

## Current focus

Just finished: **merge of GUI search freeze fixes** into the parent branch — subprocess isolation, no process pool for light worker searches, stream-append + sort-on-finish, coalesced status/list updates, `activitySpinner` property, indeterminate progress until file total known, preview ScrollBar placement. Prior parent work (copy-venv shebang rewrite) remains on this branch.

## Touched (this apply)

- `src/srxy/adapters/inbound/gui/controller.py`, `models.py`, `qml/Main.qml`
- `src/srxy/adapters/outbound/worker/search_worker.py`
- `src/srxy/domain/progress.py`
- `docs/gui.md`, `memory/*`, Magika/preview/content-kind path from the same worktree branch
- `scripts/dev/profile-gui-freeze.sh`

## Verified (worktree before apply)

- Freeze/perf commit: `c20d4dc`; spinner/progress: `439995a`; preview scrollbar: `04197c6`
- User confirmed buttery-smooth scrolling/UI after freeze fixes
- Parent quality gate still to run after this merge

## Next steps

1. Parent quality gate after apply (`checks.sh --quiet --fix` then `--quiet`).
2. User smoke: activity spinner animates; progress bar pulses until `current/total`, then shows %.
3. `/delete-worktree-srxy` for `cursor/79bcea9a` when ready.
4. Manual Windows (and other) installer verification for 1.7.0.
