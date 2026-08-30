# Active Context

_Last updated: 2026-08-30_

## Branch

- `feature/fixes_1.6.6` — version target **1.7.0**. Just applied worktree `cursor/ec4c7a6b` (GPU-only `[semantic]` + platform-aware `sync-dev`).

## Current focus

Applied: **`[semantic]` is GPU-only**; dropped `semantic-gpu` name and CPU semantic path. Platform-aware `sync` / `sync-dev` / `sync-uploader`; `pywin32` as core Windows dep. README/install no longer recommend semantic without a GPU.

## Touched (this apply)

- `scripts/dev/sync.py` (+ `sync.sh` / `sync.ps1` / `sync.cmd`), `pyproject.toml`, `uv.lock`
- `tests/unit/test_dev_sync.py`, installer package_spec / privacy / install flow
- README, AGENTS.md, docs/development.md, docs/installation.md, copy-venv / apply-worktree skills
- `memory/*`

## Next steps

1. `/delete-worktree-srxy` for `cursor/ec4c7a6b` (`6mnv`) when ready.
2. Manual Windows (and other) installer verification for 1.7.0.
3. Optional: Linux Search button visual check from prior apply (`cursor/08e18461`) if not done.
