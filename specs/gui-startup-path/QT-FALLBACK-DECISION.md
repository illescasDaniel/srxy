# Qt fallback picker: accepted scope amendment

Status: **accepted for this patch on 2026-10-26**. After the KDE Browse fix and the remaining fallback limitation were reported, Daniel said “we're good to go” and requested commit/push after full checks. The narrow exception below is recorded in both related specs; replacement of the fallback backend remains a separate follow-up.

## Verified behavior

The startup-folder and picker-start-folder changes are implemented. Independent review's additional symlink-path and picker-handoff corrections are covered by passing regressions. Both final full gates passed after those corrections: autofix 134.952 seconds, verify 8.228 seconds, all four pytest buckets successful, zero errors or warnings. The GUI Taskipy startup smoke also exits successfully.

A standalone probe with installed Qt 6.11.1, without importing srxy, confirms a separate fallback-directory-model defect:

| Requested directory | Listed contents |
|---|---|
| `ordinary` | Its own sentinel |
| `ordinary#suffix` | The `ordinary` directory's sentinel |
| `ordinary%20suffix` | The process's working directory |

The public folder URL remains correctly encoded. Qt's fallback model converts it into a native path and then reparses that path as a URL, changing reserved-character meaning. This follows the [Qt 6.11 implementation](https://raw.githubusercontent.com/qt/qtdeclarative/6.11/src/labs/folderlistmodel/qquickfolderlistmodel.cpp). The actual installed-model behavior was reproduced independently; this is not a new srxy path-conversion error.

Ordinary paths, spaces and Unicode are not the same defect. Native OS pickers use a different backend; native Windows/macOS validation remains unavailable on this Linux host. Outside-root selection validation remains in place regardless of the browsing backend.

## Accepted narrow amendment

The startup spec's path-character scenario and related ignore-picker amendment include this exception:

> srxy preserves explicit native-path targets and encodes picker starting URLs without interpreting path characters as URL syntax. Correct displayed directory contents for reserved-character names such as `#` and literal `%20` in Qt 6.11.1's non-native fallback picker are a documented upstream limitation. Repairing or replacing that fallback backend is outside this change. The exception does not permit changing the main search root, changing selected paths, or relaxing outside-root rejection.

This keeps the approved launch policy, picker flow, startup dependencies, packaging and resource budget. It does not describe the reserved-character rendered-list behavior as verified or fixed.

## Alternative: expand the picker implementation

A supported replacement using QtWidgets' `QFileDialog` would need an architectural amendment before implementation:

- Construct `QApplication` before startup/splash instead of `QGuiApplication`; an existing application cannot be upgraded later.
- Introduce a picker adapter that uses native dialogs when available and a different widget fallback otherwise.
- Retain QtWidgets bindings/frameworks in Linux/macOS packages, where they are currently pruned, and update the associated packaging tests.
- Review changed fallback appearance, startup/resource costs, transient-window parenting and shared GUI fixtures.
- Test actual rendered sentinel rows, selection, cancellation and special-character paths on the replacement backend, then repeat the full gates and independent grade.

The candidate's basic feasibility is verified on this Linux host: a standalone QtWidgets probe passed all six combinations of ordinary, `#`, and literal `%20` paths in file and directory modes. It checked actual displayed model rows, clicked the target row, and verified exact selection/acceptance paths. This does not verify native Windows/macOS appearance or packaged startup. Reproducer: `.sandbox/widget_picker_repro.py`.

No replacement-backend production changes have been made. Double-encoding paths, mutating Qt's private model, and filesystem aliases are not proposed workarounds.
