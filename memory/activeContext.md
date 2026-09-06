# Active Context

_Last updated: 2026-09-06_

## Branch

- `cursor/windows-pyside-offline-installer-fb07` off `develop` — Windows installer migration step (1): PySide offline wrapper. PR targets `develop`.

## Current focus

Fat self-extracting Windows PySide offline installer — **done** on this branch (pending commit).

## Just completed (2026-09-06)

- Fat `SrxyInstaller.exe`: stub + appended `payload-embed.zip` + `SRXYISFX` trailer (sha256 + length + magic).
- Extracts once to `%LOCALAPPDATA%\srxy\is\<sha16>\p\` (short path for MAX_PATH); distribution zip contains only the fat exe.
- Verified: `--help` / headless install+uninstall exit 0; zip ≈ 138 MiB with sole member `SrxyInstaller.exe`.
- Contract tests: `test_windows_pyside_packaging.py` 13 passed.

## Next steps

1. Commit when asked.
2. Optional: full `uv run task build-windows-installer-offline-pyside` from a clean stage (logic already smoke-tested via stub rebuild).
3. NSIS / release-artifact decision remains a separate follow-up.
