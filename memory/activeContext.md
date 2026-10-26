# Active Context

_Last updated: 2026-10-26_

## Branch

- `feature/1.8.0` @ `05a0d27` — task changes remain uncommitted; baseline includes Codex workflow skills.

## Current focus

- **CLI Ctrl+C traceback — fixed (2026-10-26):** plain CLI catches KeyboardInterrupt during preflight, search and result output; finishes progress/spinner cleanup, closes the output writer, prints `Search cancelled.` to stderr and returns 130. Six regression cases failed before the fix; all 114 CLI tests pass. Real subprocess SIGINT during search returned 130 without a traceback. Required autofix and verify gates passed all four buckets with zero errors/warnings. Changes remain uncommitted.

- **KDE Browse URL decoding regression — fixed (2026-10-26):** main Browse now passes selectedFolder as a typed QUrl to setBrowsedPath(), which calls toLocalFile() once. Regression proves native #, literal %23/%20 and Unicode paths display, validate and search correctly; typed/drop/ignore and symlink semantics covered. Focused suite 131 passed (one unrelated OCR test deselected); both full gates passed all four buckets with zero errors/warnings (autofix 21.310s, verify 8.302s). Independent targeted grade PASS, native KDE interaction PARTIAL because offscreen tests inject the actual QML selection URL. No commits requested. Separate upstream fallback listing issue remains unwaived.

- **GUI startup search path + ignore picker directory (2026-10-26):** startup policy, installed launchers, live-root ignore pickers and KDE Browse decoding fix implemented and reviewed. Daniel accepted proceeding after the documented Qt fallback limitation and requested commit/push after full checks. Narrow fallback exception recorded in both specs and QT-FALLBACK-DECISION.md; original grade retained as historical evidence. Native KDE/Windows/macOS QA remains a follow-up. Fresh full precommit autofix/verify gates both passed (core/gui/tui/heavy exit 0, zero errors/warnings). Implementation and validation complete; Daniel authorized committing the task files and pushing feature/1.8.0. Diff base 05a0d276034a4a88e6dfcd592023e1cbddac294a.

0. **Ignore editor alignment fix — implemented and independently graded PASS (2026-10-23):** all three approvals recorded. Original cursor y=0 regression confirmed before QML correction; focused GUI/snapshot suite passed (53), with strengthened typing/scroll tests also passing. Main.qml now owns padding/insets/top alignment and stationary empty/preedit-only placeholder. Material light/dark and narrow renders inspected; fresh Material/Fusion/FluentWinUI3 processes each passed 8 targeted regressions on Linux. Both `uv run task checks -- --quiet --fix --all` and `uv run task checks -- --quiet --all` passed with 0 errors/warnings after lockfile-only certifi 2026.10.19, Pillow 13.0.0 and pypdf 6.21.2 security updates; all four pytest buckets passed. Independent grader: 6 PASS, UI fidelity PARTIAL solely for unavailable native Windows/macOS inspection; no product defects identified. Daniel confirmed the fix and requested commit/push. Remaining follow-up: native Windows/macOS visual QA of empty/focused/filled/error/narrow/scrolling states.

0. **Codex workflow skills** — added discoverable `.agents/skills` versions of apply-worktree, delete-worktree, copy-venv, and save-changes. Four skill validations passed; instruction-only changes reuse existing venv helpers. Daniel approved committing and pushing the skill and memory changes on 2026-10-23.

1. **v1.8.0 train** — offline installer Liquid Glass + Finder open fix landed; Unlimited OCR (draft PR #38) still open.
2. Next topic / QA as Daniel directs.

## Next steps

- Daniel approved the CLI interrupt fix and authorized commit/push to `feature/1.8.0`; save after fresh autofix/verify gates. The bare `srxy` command still uses the separately installed copy; `.venv/bin/srxy` runs the fixed checkout.

- Full precommit gates passed; task is ready for the authorized commit/push to feature/1.8.0. After saving, continue with native-picker QA or other work as Daniel directs. Keep Qt fallback backend repair and native picker QA tracked as follow-ups; the documented limitation is accepted for this patch.

1. Daniel GPU QA / undraft Unlimited OCR (#38) when ready.

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
