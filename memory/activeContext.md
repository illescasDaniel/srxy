# Active Context

_Last updated: 2026-10-01_

## Branch

- `cursor/gui-search-button-top-fixed-0e77` off `feature/1.8.0` — Trello `yO4X6JDM` (Search button top-fixed, multi-term).
- Release train **`feature/1.8.0`** @ `e88cb39` (includes squash-merge of PR #40 search-by-folder-name).

## Current focus

Sync this branch with latest `feature/1.8.0` (folder-name search #40), run quality gate, fix if needed, then re-push PR #51.

## Just changed

- Merged `origin/feature/1.8.0` @ `e88cb39` into this branch. `Main.qml` auto-merged cleanly (pinTop + Folder names option coexist). Conflicts only in `memory/activeContext.md` / `memory/progress.md` — resolved keeping this branch's focus plus the landed #40 Done items.

## Next steps

1. Run quality gate (`core,gui` at minimum given GUI + shared search surfaces); fix failures.
2. Push and await green CI on PR #51.

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
