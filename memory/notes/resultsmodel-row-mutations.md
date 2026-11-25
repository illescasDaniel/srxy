---
name: resultsmodel-row-mutations
description: Rewrote ResultsModel.clear() to use beginRemoveRows(_EMPTY_INDEX, 0, N-1)/endRemoveRows() (skipped when empty) and replace_results() to emit a remove-all…
type: decision
date: 2026-08-20
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Searches logged `DelegateModel::cancel: index out range 6 0` / `10 1`. `ResultsModel.clear()` and `replace_results()` did a full `beginResetModel()`/`endResetModel()`, invalidating rows while the `resultsView` ListView's async `currentIndex` binding and in-flight (async-incubated) delegates were stale. `QQmlDelegateModel::cancel(index)` was then asked to cancel a delegate at a row index beyond the delegate compositor's count. `_clear_selection()` (Python-side) cannot synchronously drive the QML `currentIndex` binding, so it did not silence the warning.
- **Decision:** Rewrote `ResultsModel.clear()` to use `beginRemoveRows(_EMPTY_INDEX, 0, N-1)`/`endRemoveRows()` (skipped when empty) and `replace_results()` to emit a remove-all + insert-all pair, never `modelReset`. `MatchesModel` full resets were left unchanged (no async `currentIndex` binding on that view).
- **Rationale:** Row-level mutations let the QML delegate model cancel in-flight incubations with valid indices, avoiding the stale-index warning. The change preserves the row contract (order, limit) exactly. Added `tests/unit/test_gui_models.py` (deterministic signal assertions: `rowsRemoved`/`rowsInserted`, never `modelReset`, incl. empty-model no-op cases) and a GUI regression test in `test_gui_qml_load.py` (two search cycles through loaded QML; asserts no `DelegateModel`/`index out range` message). Unit tests were verified to fail against the old full-reset code. Fallback options (QML `modelAboutToBeReset` → `currentIndex = -1`, deferred reset) were not needed.
