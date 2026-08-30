# Active Context

_Last updated: 2026-08-30_

## Branch

<<<<<<< HEAD
- `feature/fixes_1.6.6` — version target **1.7.0**. Just applied worktree `cursor/ec4c7a6b` (GPU-only `[semantic]` + platform-aware `sync-dev`).

## Current focus

Applied: **`[semantic]` is GPU-only**; dropped `semantic-gpu` name and CPU semantic path. Platform-aware `sync` / `sync-dev` / `sync-uploader`; `pywin32` as core Windows dep. README/install no longer recommend semantic without a GPU.
=======
- `cursor/5ebdc811` (worktree) — parent `feature/fixes_1.6.6` / version target **1.7.0**.

## Current focus

Search progress UX: determinate file counts (`0/N` … `N/N`) as soon as the walk finishes, plus per-file OCR/CLIP/transcribe activity during concurrent (thread-pool) heavy searches. Sticky “Searching…” no longer blocks `Scanning current/total` in GUI/TUI status.
>>>>>>> cursor/5ebdc811

## Touched

<<<<<<< HEAD
- `scripts/dev/sync.py` (+ `sync.sh` / `sync.ps1` / `sync.cmd`), `pyproject.toml`, `uv.lock`
- `tests/unit/test_dev_sync.py`, installer package_spec / privacy / install flow
- README, AGENTS.md, docs/development.md, docs/installation.md, copy-venv / apply-worktree skills
- `memory/*`

## Next steps

1. `/delete-worktree-srxy` for `cursor/ec4c7a6b` (`6mnv`) when ready.
2. Manual Windows (and other) installer verification for 1.7.0.
3. Optional: Linux Search button visual check from prior apply (`cursor/08e18461`) if not done.
=======
- `src/srxy/domain/progress.py` — `concurrent_activity_fan_in`, `is_generic_searching_activity`
- `src/srxy/application/use_cases/search_files.py` — catch-up emits `0/N`; thread pool passes fan-in activity
- `src/srxy/adapters/inbound/gui/controller.py` — scanning status when activity is generic Searching
- `src/srxy/adapters/inbound/tui/app.py` — same status priority
- `tests/unit/test_progress.py`, `test_file_search_streaming.py`, `test_file_search.py`
- `tests/gui/test_gui_controller.py`

## Verified

- `copy-venv.sh` → worktree `.venv`; `srxy.__file__` under this tree; torch `2.13.0+cu130` `cuda=True`
- `./scripts/quality/checks.sh --quiet --fix` then `--quiet` **PASSED**

## Next steps

1. User visual check: OCR search on a small folder (e.g. Downloads with 2 images) — progressCount `0/2`→`1/2`→`2/2`, status `OCR · filename` / `Scanning N/M`.
2. User may commit when ready.
>>>>>>> cursor/5ebdc811
