# Active Context

_Last updated: 2026-09-01_

## Branch

- Worktree `gvl5` on `develop` — OCR hang + progress fix.

## Current focus

OCR performance + flaky `0/N` progress — **done** in this session.

## Diagnosis (Screenshot_20260807_113713.png)

- Not a true Tesseract hang (direct `tesseract` ~2s; full app path was ~15s / 10 `recognize()` calls before fix).
- Root cause: redundant full-frame + 9-region grid OCR at 2560×1600 even when upright OSD + lexical text already good.
- With OCR + semantic-image, folder search completes ~40s (12 PNGs).

## Implemented

- [`ocr_text.py`](src/srxy/adapters/outbound/ocr/ocr_text.py): full-frame fast path before region grid; `DEFAULT_MAX_IMAGE_DIMENSION` 4000→2000; per-call Tesseract timeout (default 60s, `SRXY_OCR_TESSERACT_TIMEOUT`); `OcrRecognizeTimeout` → skip with `ocr_timeout`.
- [`search_control.py`](src/srxy/application/search_control.py): always emit listing catch-up `(0, N)` through throttle.
- [`Main.qml`](src/srxy/adapters/inbound/gui/qml/Main.qml): `objectName: "optOcr"` for flow tests.
- Tests: `test_search_control.py`, `test_ocr_text.py`, `test_cli.py`, `test_gui_flows.py` (OCR progress count).

## Verified

- Stuck file OCR: **~5.6s**, **1** `recognize()` call (was ~15s / 10 calls).
- `checks.sh --quiet --scope=core,gui --no-cache` PASSED.
- Explicit pytest on changed tests: **37 passed** (~77s, includes GUI OCR flow).

## Next steps

1. Manual QA: search `/home/daniel/Pictures/Screenshots/` with Contents + OCR + Image — confirm `0/12` shows promptly and Aug 7 file no longer feels stuck.
2. Open manual QA items in `progress.md` when ready.
