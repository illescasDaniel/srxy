# KDE Browse conversion bug fix — 2026-10-26

The Browse handler previously stripped the file URL scheme without decoding, leaving # encoded as %23. It now passes the selected QUrl to a typed controller slot and calls toLocalFile() once. Manually typed native paths are not decoded.

Regression evidence: the original QML handler failed three reserved-character cases (#, literal %23 and literal %20), while the current loaded-QML acceptance handler followed by real search passed all four cases including Unicode. Focused controller/flow suite: 131 passed, one unrelated OCR test deselected. Both full gates then passed all core/gui/tui/heavy buckets with zero errors/warnings:

- `uv run task checks -- --quiet --fix --all` — 21.310s.
- `uv run task checks -- --quiet --all` — 8.302s.

Independent read-only targeted review (`kde_review_finish`):

## Verdict: PASS

| # | Criterion | Score |
|---|-----------|-------|
| 1 | Spec conformance | PASS |
| 2 | Design decisions honoured | PASS |
| 3 | Architecture & layering | PASS |
| 4 | Test quality | PASS |
| 5 | UI fidelity | PARTIAL |
| 6 | Scope discipline | PASS |
| 7 | Conventions & maintainability | PASS |

Unresolved finding: native KDE interaction remains unverified. The offscreen test passed through the actual QML acceptance handler and successfully searched the selected folder.

The separate Qt fallback picker defect remains unchanged.
