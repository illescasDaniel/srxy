# Active Context

_Last updated: 2026-09-07_

## Branch

- `cursor/windows-pyside-offline-installer-fb07` off `develop` — Windows fat PySide offline installer (Inno removed). PR targets `develop` (PR #35).

## Current focus

Suppress `qt.qpa.mime: Retrying to obtain clipboard` spam (Qt clipboard lock bug).

## Just changed

- `silence_noisy_qt_logging()` in `qt_theme.py` — sets `QT_LOGGING_RULES` / `QLoggingCategory` for `qt.qpa.mime=false`
- Called from GUI + installer `run_*` before `QGuiApplication`
- Tests in `test_qt_theme.py`

## Next steps

1. Commit + push if desired (merge PR #35 once CI green).
2. **Check macOS installer**.
3. Optional: Authenticode signing.
