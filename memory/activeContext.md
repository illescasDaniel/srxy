# Active Context

_Last updated: 2026-08-29_

## Branch

- `feature/fixes_1.6.6` — version target is now **1.7.0** (skipped shipping 1.6.6 as a patch; minor bump for UI + feature scope). Cold-start + splash already on this branch.

## Current focus

None active — 1.7.0 version bump applied from worktree `entu`; Final QA / release next.

## Done this session

- Applied worktree `entu` / `cursor/47e8aad4`: bump `1.6.6` → `1.7.0` + version-bump checklist in `docs/development.md`.
- Quality gate: `checks-win` fix + verify PASSED.
- Prior: cold-start + splash from `o850` / `cursor/d34ce3c1`.

## Next steps

1. Final QA: Windows/macOS installers (against 1.7.0 artifacts).
2. Release when Final QA is green.
3. Push `feature/fixes_1.6.6` when ready.
4. `/delete-worktree` for leftover worktrees when finished.

## Key files

- Version: `pyproject.toml`, both `installer_meta.toml`, `uv.lock`
- Docs: `docs/development.md` → Bumping the release version
- GUI splash/cold-start under `src/srxy/adapters/inbound/gui/`