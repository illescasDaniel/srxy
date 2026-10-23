---
name: save-changes
description: Review and save the current srxy task's Git changes when asked to save changes, prepare a commit, commit, or push completed work.
---

# Save Changes

Read current Git instructions first. Pending review, "leave uncommitted," and "do not push" instructions persist until changed. Skill selection alone does not authorize a commit or push; if "save" is ambiguous, prepare the reviewable result and clarify the intended Git action before mutating history.

1. Inspect repository/branch, `git status --short`, staged/unstaged diffs, relevant untracked files, and recent history. Identify task changes and preserve other work, including pre-existing staged files. Never stage broadly with `git add .` or `git add -A`.
2. Review for accidental secrets, generated artifacts, and unrelated changes. Finish authorized work and summarize the concrete diff. Follow repository memory protocol through the orchestrator; do not invent memory updates to fill a commit.
3. If code changed, run the required quality gate until autofix and verify pass: `uv run task checks -- --quiet --fix`, then `uv run task checks -- --quiet`. Follow scope/environment rules in `AGENTS.md`, including `--all` before a shared-code commit. For documentation-only work, perform relevant content/skill validation without claiming a code gate ran.
4. Only when committing is explicitly authorized, stage explicit task paths or relevant hunks, verify the staged diff, and commit following repository message style. Exclude unrelated staged work without discarding it; if safe isolation is unclear, stop before committing. Use a body file or safely quoted multiline message when needed. Do not amend or rewrite earlier commits without specific authorization.
5. Only when pushing is explicitly authorized, inspect branch/upstream and ahead/behind state, then push the intended branch normally. If histories diverge or push is rejected, report it and obtain direction rather than force-pushing or silently selecting a new destination.
6. Report changed paths, checks, commit SHA if created, push result/destination if applicable, and remaining uncommitted work. When review is pending, leave the diff uncommitted and state that clearly.

Never bypass hooks, force-push, change Git configuration, or create a branch without authorization.
