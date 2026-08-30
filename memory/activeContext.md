# Active Context

_Last updated: 2026-08-30_

## Branch

- `feature/fixes_1.6.6` — version target **1.7.0**. Just applied worktree `cursor/5ebdc811` (search progress: file counts + OCR activity).

## Current focus

Applied: **Search progress UX** — determinate file counts (`0/N` … `N/N`) as soon as the walk finishes, plus per-file OCR/CLIP/transcribe activity during concurrent (thread-pool) heavy searches. Sticky “Searching…” no longer blocks `Scanning current/total` in GUI/TUI status.

## Touched (this apply)

- `src/srxy/domain/progress.py` — `concurrent_activity_fan_in`, `is_generic_searching_activity`
- `src/srxy/application/use_cases/search_files.py` — catch-up emits `0/N`; thread pool passes fan-in activity
- `src/srxy/adapters/inbound/gui/controller.py` — scanning status when activity is generic Searching
- `src/srxy/adapters/inbound/tui/app.py` — same status priority
- `tests/unit/test_progress.py`, `test_file_search_streaming.py`, `test_file_search.py`
- `tests/gui/test_gui_controller.py`
- `memory/*`

## Verified

- Parent `./scripts/quality/checks.sh --quiet --fix` then `--quiet` **PASSED** (first heavy run hit transient CUDA OOM; retry clean).
- Worktree commit `bfd9422`; merge `7a1e76f`.

## Next steps

1. User visual check: OCR search on a small folder — progressCount `0/2`→`1/2`→`2/2`, status `OCR · filename` / `Scanning N/M`.
2. `/delete-worktree-srxy` for `cursor/5ebdc811` (`hh32`) when ready.
3. `/delete-worktree-srxy` for `cursor/ec4c7a6b` (`6mnv`) if still present.
4. Manual Windows (and other) installer verification for 1.7.0.
