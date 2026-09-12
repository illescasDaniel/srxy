# Active Context

_Last updated: 2026-09-12_

## Branch

- `cursor/gui-search-button-top-fixed-0e77` off `feature/1.8.0` — Trello `yO4X6JDM` (Search button top-fixed, multi-term).
- `develop` — post-v1.7.0 (shipped `main` @ `2c64f08`, 2026-09-11).
- Release train **`feature/1.8.0`** (forked from `develop`). Topic branches for 1.8.0 work fork from here (not from `develop`).

## Current focus

Done: pin Search button to the top of the What-to-search row in multi-term mode so it does not re-centre as the term list grows.

## Just changed

- `src/srxy/adapters/inbound/gui/qml/Main.qml`:
  - `searchButton.pinTop: stretchToField || modeBox.currentIndex === 1` — pins Search (and the query-issue/search-warnings `ToolButton`s) to `Qt.AlignTop` in multi-term mode on every platform, not only the Windows `stretchToField` case.
  - Added `objectName: "multiTermColumn"` on the multi-term `ColumnLayout` for test hooks.
- `tests/gui/test_gui_query_layout.py`: new geometry test `test_given_multi_term_growth_when_terms_added_then_search_button_stays_top_pinned` — drives `applyDemoMultiTerms` from 1→6→1 terms, asserts `searchButton.mapToScene(QPointF(0,0)).y()` stays within 1px of the initial value while `multiTermColumn.height` actually grows. Confirmed it fails without the fix (`initial_y=186.0 grown_y=324.0`). Also switched pre-existing `applyDemoMultiTerms` invocations to `Q_ARG("QVariant", ...)` in the new test (the QML function's untyped param is `QVariant`, not `QString`; `Q_ARG(str, ...)` silently fails to invoke).
- Merged latest `origin/feature/1.8.0` (post `develop` sync, PR #52) onto this branch — pulls in the already-landed catalog-probe resilience (`ci.yml` `continue-on-error` + advisory warning, resilient `probe_catalog.py` lazy-resolver retries, `pypdf>=6.16.1`, fixed `fake_uninstall` stub kwargs in `test_installer.py`) that PR #51's first CI run hit before the sync (quality job hard-failed in ~17s on a Homebrew bottle-tag probe miss). No additional porting needed — the sync already carries all of it; only resolved a memory/`activeContext.md` merge conflict.

## Next steps

1. PR #51 opened into `feature/1.8.0` (draft). Re-push after merging the sync; awaiting green CI.
2. Do not touch PRs #38–#41 (Unlimited OCR / media preview / folder-name search / drag-and-drop) — untouched this session.

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.

## Sync note (2026-09-12)

- Synced `develop` (@ `0fcda8b`, includes signed/notarized v1.7.0 macOS installer work + `docs/images/gui-linux.png` regeneration) into `feature/1.8.0` via PR #52 (merged, merge commit `7d8e9d4`). v1.7.0 macOS installer distribution work is complete/shipped; no outstanding action here.
- Refreshed the 6 open PRs targeting `feature/1.8.0` onto the new tip:
  - #40 (search-by-folder-name) — merged base cleanly, pushed. Now `MERGEABLE`.
  - #38 (Unlimited OCR), #39 (media preview), #41 (DnD path field), #51 (search button top-fixed) — conflict only in `memory/*.md` (each branch's own scratch notes vs. the new `feature/1.8.0` tip). Left unresolved for the PR owner/agent to reconcile — not force-resolved on their branches.
  - #42 (recent searches) — conflict in `memory/activeContext.md` **and** `src/srxy/adapters/inbound/gui/qml/Main.qml` (real code conflict, not trivial). Left unresolved.
  - Did not find open PRs from `feature/macos-sdk26-offline-pyside` or `feature/gui-search-button-top-fixed` branches by those exact names; #51 (`cursor/gui-search-button-top-fixed-0e77`) appears to be the corresponding PR.
