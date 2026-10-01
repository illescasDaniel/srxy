# Active Context

_Last updated: 2026-10-01_

## Branch

- `cursor/gui-search-button-top-fixed-0e77` @ `2cee201` — merged latest `origin/feature/1.8.0` (@ `e88cb39`, includes PR #40 folder-name search). Ahead of `origin/cursor/gui-search-button-top-fixed-0e77` by 1 merge commit.
- Release train **`feature/1.8.0`** @ `e88cb39`.

## Current focus

Done this session: sync branch with `feature/1.8.0` + quality gate green.

## Just changed

- Merged `origin/feature/1.8.0` into this branch (`2cee201`). `Main.qml` auto-merged (pinTop + `optFolders` coexist). Memory conflicts resolved.
- Quality gate `core,gui,tui`: autofix + verify both PASSED (no code fixes needed).

## Next steps

1. Push branch (`git push`) so PR #51 picks up the sync.
2. Await green CI on PR #51.

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
