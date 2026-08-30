# Active Context

_Last updated: 2026-08-30_

## Branch

- `cursor/5ebdc811` (worktree) — parent `feature/fixes_1.6.6` / version target **1.7.0**.

## Current focus

Search progress UX: determinate file counts (`0/N` … `N/N`) as soon as the walk finishes, plus per-file OCR/CLIP/transcribe activity during concurrent (thread-pool) heavy searches. Sticky “Searching…” no longer blocks `Scanning current/total` in GUI/TUI status.

## Touched

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
