# Active Context

_Last updated: 2026-10-03_

## Branch

- Working branch: `cursor/macos-sdk26-offline-pyside-8bf8` → PR into `feature/1.8.0` (draft; do not merge).
- Just merged latest `origin/feature/1.8.0` (`1deb4ef`: media preview #39, recent searches #42, path DnD #41, Search button top-fixed #51, folder-name search #40, develop sync).

## Current focus

1. **macOS offline installer SDK 26 restamp** — finish merge conflict resolution, run quality gate, fix any fallout.
2. **Unlimited OCR** — draft PR #38 → `feature/1.8.0`; Daniel GPU QA before undraft.

## Next steps

1. Complete merge commit; run `checks-fix-quiet` then `checks-quiet`; fix failures.
2. Daniel GPU QA / undraft Unlimited OCR (#38) when ready.

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
