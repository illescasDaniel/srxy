# Codenav MCP pinned to 1.0.1 and tested

2026-11-25 · Decision · Verified by probe sessions

`codenav-mcp` is pinned to `==1.0.2` in all four agent configs (`.mcp.json`, `.codex/config.toml`, `.cursor/mcp.json`; the old `>=0.2.1,<0.3` pin would never have selected 1.x). 1.0.2 adds did-you-mean suggestions to unknown-argument refusals.

Probe runs (driven through `claude -p` with `.claude/demo-hooks/` logging every tool call to `/tmp/codenav-demo/`):

- find → read → edit → verify → undo → re-verify works end-to-end on two files; both undos restored byte-identical content (git diff empty).
- Editing marks an edit id; `undo_edit(id=...)` reverts it. `verify_changes` reports files changed since HEAD.
- Argument names differ from what descriptions suggest: `outline` takes `file_path` (not `file`), `edit` takes `old_string`/`new_string` (also `new_text`/`apply`). Errors are self-describing and print the allowed args, so agents self-corrected on retry.
- No plain read-file tool; docstring reading goes through `symbol_info`.
- There is no plain read-file tool; `symbol_info` (docstring + first lines) is the read path.
- In non-interactive `claude -p`, codenav tools must be allow-listed (`--allowedTools 'mcp__codenav__*'`) or the model correctly reports a permission refusal and makes no fallback call.
- `build/` is excluded from the server's diagnostics by default.
