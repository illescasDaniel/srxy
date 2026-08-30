# Active Context

_Last updated: 2026-08-30_

## Branch

- Worktree branch `cursor/79bcea9a` (GUI selection/preview + Magika content routing). Related primary branch still targets **1.7.0**.

## Current focus

Just finished: **preview lifetime fix** (stuck Loading / deleted `QTextDocument`) + **Magika content-kind routing** for extensionless / wrong-extension / binary files.

## Touched files

- `src/srxy/adapters/inbound/gui/controller.py` — QQuickTextDocument hold, live re-resolve, `setPlainText`, fixed line-height
- `src/srxy/adapters/inbound/gui/qml/Main.qml` — remove `text: controller.previewText` binding
- `src/srxy/adapters/outbound/content/content_kind.py` — NUL + Magika route decisions
- `src/srxy/adapters/outbound/content/line_sources.py`, `documents/document_text.py`, `metadata/media_metadata.py` — Magika wiring
- `tests/unit/test_content_kind.py`, fixtures under `tests/fixtures/content_kind/`, GUI preview tests
- `pyproject.toml` / `uv.lock` — `magika>=1.0.3`; earlier `ty` replaces basedpyright

## Verified

- `./scripts/quality/checks.sh --quiet --fix` → **PASSED**
- Full re-run of affected suites: `tests/gui/test_gui_controller.py` + `test_content_kind` + related → **143 passed**

## Manual QA (user)

- Rapid GUI row selection: preview should not stick on Loading; no shiboken `QTextDocument already deleted` traceback.
- Optional: curseforge/Minecraft `assets/objects` hash files stay binary-skipped for body search; wrong-extension media/text/pdf behave per Magika route.

## Next steps

1. User smoke of live preview selection + binary objects tree if available.
2. Commit when ready; `/delete-worktree-srxy` for applied worktrees when done.
3. Installer / 1.7.0 release QA remains outstanding on primary track.
