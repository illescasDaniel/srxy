# Active Context

_Last updated: 2026-09-11_

## Branch

- `hotfix/windows-corrupt-jpeg-property-store-cdc4` (off `main`, not `develop`/`feature/1.8.0`) — CI #147 `test-windows` hotfix. **Merge waits on Daniel's fresh OK on that specific PR; do not merge.** No retag / no v1.7.0 rebuild.
- `main` — v1.7.0 released (`2c64f08`, tag `v1.7.0`); latest commit `2506b53` (memory-only #46, no product code change).
- `develop` — packaging trunk; sync from `main` after memory hygiene PR merges (pending Daniel OK).
- `feature/1.8.0` — active 1.8.0 release train (OCR, media preview, folder search, GUI Ideas, NSIS, etc.).

## Current focus

HOTFIX only: `main` @ `2506b53` CI #147 `test-windows` failed — native Windows fatal exception `0xc0000002` (STATUS_NOT_IMPLEMENTED) inside `windows_metadata.py::_open_property_store` <- `SHGetPropertyStoreFromParsingName`, hit by `tests/unit/test_file_search.py::test_given_corrupt_jpeg_when_searching_contents_then_skips_gracefully` (corrupt `broken.jpg` fixture). The native SEH fault bypasses Python `try/except`, kills the xdist worker (`--max-worker-restart=0`), and pytest falsely blames the next test. `quality` + `test-macos` were green; not touching 1.8.0 feature work under this brief.

## Just changed

- `src/srxy/adapters/outbound/metadata/windows_metadata.py`: `_read_searchable_property_entries` now dispatches to `_read_searchable_property_entries_isolated` on real Windows (`sys.platform == "win32"`); the previous direct implementation is renamed `_read_searchable_property_entries_direct` (unchanged behavior, still used by the existing mocked cross-platform unit tests so they're unaffected). The isolated path talks to a lazily-spawned, reused worker subprocess over a JSON-lines stdio protocol (write path, read one response line with a 5s timeout via a daemon reader thread); worker death (native SEH fault -> pipe EOF) or a hung read fails soft to `[]` — same contract as `except OSError: return []` — and drops the dead/hung worker so the next call respawns a clean one. Added `reset_isolated_worker_for_tests()`.
- New `src/srxy/adapters/outbound/metadata/windows_metadata_worker.py` — the subprocess entrypoint (`python -m srxy.adapters.outbound.metadata.windows_metadata_worker`); one JSON request/response line per file, calls `_read_searchable_property_entries_direct`, and only an actual native fault can kill it (any in-process Python exception is caught and returns empty entries) — the parent detects a dead worker via EOF.
- `tests/unit/test_windows_metadata.py` — added: Windows-platform dispatch test (asserts isolated path used, direct path not called); dead-worker (`readline()` -> `""`) fail-soft + respawn test; healthy-worker reuse test (one spawn serves two requests); hung-worker timeout test (patched `_ISOLATED_WORKER_TIMEOUT_SECONDS`); worker `_handle_request` tests (valid + malformed input). All via fake `Popen`-like mocks — no real Windows/pywin32 needed to exercise the harness logic.
- Verified against the real CI failure via `gh run view --job 103189783873 --log`: crash frame is exactly `windows_metadata.py:143 _open_property_store` <- `:89 _read_searchable_property_entries` <- `:71 iter_windows_metadata_lines` <- `line_sources.py:281 iter_searchable_lines`, matching the brief's root-cause description.
- Local verification (fresh VM, no prebuilt env — had to `curl -LsSf https://astral.sh/uv/install.sh | sh`, `uv run task sync-dev`, and `apt-get install -y libegl1 shellcheck shfmt` before the gate would run clean): `tests/unit/test_windows_metadata.py` 18/18 passed; `tests/unit/test_file_search.py -k corrupt_jpeg` passed; full `tests/unit tests/cli` (772 tests) passed; `./scripts/quality/checks.sh --quiet --all` → PASSED (ruff, shell, ty, pip-audit, build, pytest all green). Real Windows COM crash reproduction isn't possible on this Linux VM — the actual regression proof is CI's `test-windows` job on the PR.
- Pushed `hotfix/windows-corrupt-jpeg-property-store-cdc4`; opened PR -> `main` (see progress.md for URL). **Do not merge without Daniel's fresh OK on that specific PR.**

## Next steps

1. Watch the PR's `main` CI, especially `test-windows` (corrupt-JPEG regression test) — report PR URL + green CI, or blocked status, to the user. Do not merge.
2. After this hotfix, resume the v1.7.0 memory-hygiene / 1.8.0 items below (unaffected by this change).
3. Merge the memory-hygiene PR (#46-adjacent) when Daniel gives explicit OK on that PR; then sync `main` -> `develop`; then patch the v1.7.0 release body with changelog (no retag/rebuild).
