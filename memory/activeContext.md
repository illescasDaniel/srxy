# Active Context

_Last updated: 2026-10-23_

## Branch

- `feature/1.8.0` @ `38e5002` — fast-forwarded from `feature/ignore-rules` and pushed to origin on 2026-10-23.

## Current focus

0. **Ignore editor alignment fix — implemented and independently graded PASS (2026-10-23):** all three approvals recorded. Original cursor y=0 regression confirmed before QML correction; focused GUI/snapshot suite passed (53), with strengthened typing/scroll tests also passing. Main.qml now owns padding/insets/top alignment and stationary empty/preedit-only placeholder. Material light/dark and narrow renders inspected; fresh Material/Fusion/FluentWinUI3 processes each passed 8 targeted regressions on Linux. Both `uv run task checks -- --quiet --fix --all` and `uv run task checks -- --quiet --all` passed with 0 errors/warnings after lockfile-only certifi 2026.10.19, Pillow 13.0.0 and pypdf 6.21.2 security updates; all four pytest buckets passed. Independent grader: 6 PASS, UI fidelity PARTIAL solely for unavailable native Windows/macOS inspection; no product defects identified. Daniel confirmed the fix and requested commit/push. Remaining follow-up: native Windows/macOS visual QA of empty/focused/filled/error/narrow/scrolling states.

0. **Codex workflow skills** — added discoverable `.agents/skills` versions of apply-worktree, delete-worktree, copy-venv, and save-changes. Four skill validations passed; instruction-only changes reuse existing venv helpers. Daniel approved committing and pushing the skill and memory changes on 2026-10-23.

1. **v1.8.0 train** — offline installer Liquid Glass + Finder open fix landed; Unlimited OCR (draft PR #38) still open.
2. Next topic / QA as Daniel directs.

## Next steps

1. Daniel GPU QA / undraft Unlimited OCR (#38) when ready.

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
