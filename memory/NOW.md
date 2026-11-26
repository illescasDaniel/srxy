# Now
Updated: 2026-11-25 (codenav test + jevmem removal)

## Doing
v1.8.0 release scope on `feature/1.8.0`: native Windows/macOS review, then a normal release.

## Done recently
- jevmem fully removed (hooks, MCP server entries, tool references, skills); memory-1/docs-1 migration stands. `codenav-mcp` pinned to 1.0.1 everywhere and end-to-end tested ([memory note](notes/codenav-mcp-1-0-1-pinned.md)).
- Migrated project memory to memory-1 (`NOW.md`, `MEMORY.md`, `notes/`) and docs to docs-1 frontmatter plus a generated `docs/INDEX.md`; old memory files are archived under `memory/archive/` ([memory note](notes/memory-layout-memory-1.md), [docs note](notes/docs-layout-docs-1.md)).
- CLI Ctrl+C returns 130 with `Search cancelled.` and no traceback; 114 CLI tests plus real SIGINT smoke pass.
- KDE Browse passes the typed `QUrl` to the controller and decodes once; `#`, literal `%23`/`%20` and Unicode paths search correctly.
- GUI startup search path, `--app-launch` intent and live-root ignore pickers landed; full four-bucket gates passed.
- Ignore-editor padding/placeholder fix landed; independent grade PASS except native-platform visual QA.

## Next
1. Review `feature/1.8.0` on native Windows and macOS: ignore-editor states and native folder-picker behavior.
2. Cut the normal v1.8.0 release once native review passes.
3. Repair the Qt 6.11.1 fallback picker defect for reserved-character paths when its scope is approved.
4. Leave the Unlimited OCR draft PR #38 untouched; it is not a v1.8.0 requirement.

## Open questions / blocked
- Qt 6.11.1 fallback picker lists the wrong directory for `#` / literal `%20`; limitation accepted for the startup-path patch, backend repair still open.
- Native Windows/macOS visual QA of the ignore editor and folder picker is still outstanding.
