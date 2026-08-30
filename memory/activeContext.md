# Active Context

_Last updated: 2026-08-30_

## Branch

- `feature/fixes_1.6.6` — version target **1.7.0**.

## Current focus

Fixed: **Progress bar 100%→95% during OCR** — GUI was driving the search progress bar from determinate activity (OCR page / transcribe segment %). Last page of a PDF set the bar to 100%, then the next file-scan event dropped it. Activity now updates status only; the bar follows file `current/total` only.

## Touched

- `src/srxy/adapters/inbound/gui/controller.py` — stop activity from setting progress bar
- `tests/gui/test_gui_controller.py` — regression: OCR 10/10 must not overwrite 95/100 file progress
- `memory/*`

## Prior (same branch)

- Parallel light + heavy search (text inline, OCR/CLIP/transcribe in pool)

## Verified

- `./scripts/quality/checks.sh --quiet --fix` then `--quiet` — **PASSED** (gui 66 incl. new regression).

## Next steps

1. User visual check: OCR search on a folder with a multi-page PDF + other files — bar should only follow files; status may show `100% OCR · doc.pdf` without yanking the bar.
2. Manual QA leftovers (mixed light/heavy streaming, installers).
