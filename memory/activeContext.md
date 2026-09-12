# Active Context

_Last updated: 2026-09-12_

## Branch

- Release train **`feature/1.8.0`** (forked from `develop`). Topic branches for 1.8.0 work fork from here (not from `develop`).
- Working branch for this session: `feature/macos-sdk26-offline-pyside` (Trello `geIhdHch`) → PR into `feature/1.8.0`, draft, do not merge.

## Current focus

1. **macOS offline installer SDK 26 restamp** — done, PR opened (draft) → `feature/1.8.0`. Ported `develop`'s Mach-O `Srxy.app` launcher + `vtool` SDK-26 restamp (`install.py`) so it applies to the offline PySide bundle too (shared `install_srxy()` path with online); pinned offline wrapper's `PySide6==6.11.1`; kept the offline installer's bundled wheel authoritative (`_packaged_payload_wheel`); `smoke-offline.sh` now asserts Quick style `macOS`. Touched files: `src/srxy/adapters/inbound/installer/install.py`, `package_spec.py`, `app.py`; `src/srxy/adapters/inbound/gui/{app.py,qt_theme.py}`; `src/srxy/resources/{macos/,icons/icns.py}` (new); `packaging/macos/{build-offline.sh,smoke-offline.sh}`; `scripts/macos/repair-prefix-gui.sh` (new, dev tool); `tests/unit/test_macos_app_launcher.py` (new), `tests/gui/test_installer.py`; `pyproject.toml`/`uv.lock` (`pypdf` CVE bump, unrelated pre-existing gate blocker). Local gate: ruff/shell/ty/pip-audit/build/core/gui/tui all green except 2 GUI thread-timing tests that are pre-existing flakes in this sandbox (reproduced failing identically on unmodified `feature/1.8.0`, unrelated to this change — real macOS CI runners should not have this issue). macOS-only code paths (`vtool` restamp, Mach-O bundle) skip on this Linux sandbox; will only be exercised by the `test-macos` CI job and `macos-installer.yml`'s `build-offline`/smoke job.
2. **Unlimited OCR** — draft PR #38 → `feature/1.8.0`; Daniel GPU QA before undraft.
3. **Media preview panel** — draft PR #39 → `feature/1.8.0`; Team Lead LGTM; Daniel visual/playback smoke before undraft.
4. **Search by folder name** — GUI + TUI + CLI; topic branch off `feature/1.8.0`; tests required; Team Lead marks ready-for-review when OK.

## Planned (also 1.8.0)

- **NSIS instead of Inno** — replace `srxy-offline.iss` outer shell with NSIS (zlib/libpng).

## Next steps

1. Folder-name search — Srxy Developer implements (GUI/TUI/CLI + tests); PR into `feature/1.8.0`.
2. Unlimited OCR — Daniel GPU QA; keep draft until then.
3. Media preview — Daniel smoke; then undraft/merge into `feature/1.8.0`.
4. NSIS Windows installer (later in 1.8.0).

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
