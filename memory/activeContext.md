# Active Context

_Last updated: 2026-09-11_

## Branch

- `main` @ `fff4427` — v1.7.0 + #49 hotfix + README Linux screenshot update.
- `develop` @ `38c2466` — `main` merged in (ahead of `origin/develop` by 6).
- `feature/1.8.0` — active 1.8.0 release train (OCR, media preview, folder search, GUI Ideas, NSIS, etc.).

## Current focus

Fixed ShellCheck SC2034 in `scripts/quality/pytest.sh` (offsets nameref).

## Just changed

- `pytest.sh`: pass `offsets` array + index into `lib_pytest_emit_log_gate_lines` (was unquoted `offsets[i]`, which expanded to the value and broke the nameref); SC2034 disable for nameref mutation.
- Prior: quality gate dispatcher (`checks.py`), interrupt cleanup, lock metadata, docs/tests (still uncommitted).

## Next steps

1. Commit when Daniel asks (uncommitted: checks dispatcher + pytest.sh SC2034 fix + docs + memory).
2. Push `develop` when ready.
3. Continue 1.8.0 work off `feature/1.8.0`.
