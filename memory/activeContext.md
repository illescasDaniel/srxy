# Active Context

_Last updated: 2026-09-12_

## Branch

- `cursor/gui-search-button-top-fixed-0e77` off `feature/1.8.0` — Trello `yO4X6JDM` (Search button top-fixed, multi-term).

## Current focus

Done: pin Search button to the top of the What-to-search row in multi-term mode so it does not re-centre as the term list grows.

## Just changed

- `src/srxy/adapters/inbound/gui/qml/Main.qml`:
  - `searchButton.pinTop: stretchToField || modeBox.currentIndex === 1` — pins Search (and the query-issue/search-warnings `ToolButton`s) to `Qt.AlignTop` in multi-term mode on every platform, not only the Windows `stretchToField` case.
  - Added `objectName: "multiTermColumn"` on the multi-term `ColumnLayout` for test hooks.
- `tests/gui/test_gui_query_layout.py`: new geometry test `test_given_multi_term_growth_when_terms_added_then_search_button_stays_top_pinned` — drives `applyDemoMultiTerms` from 1→6→1 terms, asserts `searchButton.mapToScene(QPointF(0,0)).y()` stays within 1px of the initial value while `multiTermColumn.height` actually grows. Confirmed it fails without the fix (`initial_y=186.0 grown_y=324.0`). Also switched pre-existing `applyDemoMultiTerms` invocations to `Q_ARG("QVariant", ...)` in the new test (the QML function's untyped param is `QVariant`, not `QString`; `Q_ARG(str, ...)` silently fails to invoke).

## Next steps

1. PR opened into `feature/1.8.0` (draft). Awaiting review/CI.
2. Note: gate's `pytest[gui]` bucket segfaults under the `checks.sh` process-wrapper (`setsid stdbuf`) in this sandboxed VM — reproduced identically on unmodified `feature/1.8.0` base, so it's a pre-existing environment issue, not a regression. Direct `uv run pytest tests/gui/` (no gate wrapper) passes cleanly (only 2 known-flaky installer timing tests fail, also pre-existing on base). `pip-audit` also pre-existing (pypdf CVEs, unrelated dependency).
3. Do not touch PRs #38–#41 (Unlimited OCR / media preview / folder-name search / NSIS) — untouched this session.
