# Independent final review — 2026-10-24

Diff base: `05a0d276034a4a88e6dfcd592023e1cbddac294a`.
Reviewer: independent read-only `code-grader` (`startup_regrade`).
Historical review against the original spec: the Qt exception was unapproved at review time. On 2026-10-26 Daniel accepted proceeding with the documented limitation and requested commit/push; see `QT-FALLBACK-DECISION.md`. The original scorecard below is retained unchanged as review evidence. The subsequent KDE Browse conversion fix has a separate PASS review in `KDE-BROWSE-REVIEW.md`.

## Verification

Both exact full gates passed outside the sandbox after the final source changes:

- `uv run task checks -- --quiet --fix --all` — 134.952 seconds.
- `uv run task checks -- --quiet --all` — 8.228 seconds.

Core, GUI, TUI and heavy buckets exited 0; zero formal errors/warnings. The build printed its existing uv-build version-range notice. GUI task smoke passed: `SRXY_STARTUP_EXIT=1 QT_QPA_PLATFORM=offscreen SRXY_SKIP_UPDATE_CHECK=1 uv run task gui`.

## Verdict: NEEDS WORK

| # | Criterion | Score | Key evidence |
|---|-----------|-------|--------------|
| 1 | Spec conformance | FAIL | Qt fallback displays incorrect contents for reserved-character paths. |
| 2 | Design decisions honoured | FAIL | Upstream picker gap remains; first-party path fixes are complete. |
| 3 | Architecture & layering | PASS | Pure startup policy; adapter-owned filesystem and Qt handling. |
| 4 | Test quality | PARTIAL | Gates pass; picker assertions miss incorrect displayed rows. |
| 5 | UI fidelity | PARTIAL | Layout preserved; native Windows/macOS QA unavailable. |
| 6 | Scope discipline | PASS | Approvals recorded; proposed limitation remains unapproved. |
| 7 | Conventions & maintainability | PASS | Project conventions followed; unresolved work recorded. |

### Findings (most severe first)

1. [FAIL] Spec conformance / Design decisions — Qt 6.11.1 fallback shows incorrect directory contents for `#` or literal `%20`, despite correct URL encoding. Resolve the backend or obtain explicit approval for the proposed spec exception.
2. [PARTIAL] Test quality — add displayed-row and actual-selection assertions when resolving the picker backend.
3. [PARTIAL] UI fidelity — complete native Windows/macOS launch and picker QA.

## Evidence map

| Scenario | Tests | Implementation |
|---|---|---|
| Terminal cwd; app-launch home; explicit absolute/relative/dot paths; unavailable cwd | `tests/unit/test_gui_startup.py`, `tests/cli/test_cli_startup_path.py`, `tests/gui/test_gui_controller.py` | `application/gui_startup.py`, CLI dispatch, GUI controller initialization |
| Preserve symlink/parent traversal, invalid intermediate components, tilde repeated separators | `tests/unit/test_gui_startup.py`, `tests/gui/test_gui_controller.py` | Pure startup policy; validated picker URL resolution |
| Installed launch marker and argument transport | `tests/unit/test_startup_launchers.py`, `tests/unit/test_macos_app_launcher.py`, `tests/gui/test_installer.py` | Installer launch adapters; Windows C# and macOS C launchers |
| Picker live root, reopening, cancellation, invalid root fallback, containment | `tests/gui/test_gui_ignore.py` | `Main.qml`, `ignorePickerFolderUrl`, existing ignore-edit validation |
| Layout preserved | `tests/gui/test_gui_snapshots.py` | Existing Filters layout |
| Correctly encoded URLs but wrong displayed reserved-character rows | Standalone FolderListModel reproducer; actual srxy fallback diagnostic | Upstream Qt 6.11.1 model; see `QT-FALLBACK-DECISION.md` |

Native Windows/macOS executable/UI verification is unavailable on this Linux host. Linux execution of the macOS C launcher uses a dyld-location shim and does not establish Finder behavior. QtWidgets replacement feasibility passed six standalone file/directory probes but is not implemented or approved.
