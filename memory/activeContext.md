# Active Context

_Last updated: 2026-10-21_

## Branch

- `feature/ignore-rules` — topic branch off `feature/1.8.0` for the ignore-rules feature (uncommitted).
- `feature/1.8.0` @ `879dbab` — PR #53 macOS offline installer SDK 26 / Mach-O launcher squash-merged.

## Current focus

0. **Ignore files/folders in search** — SDD Phase 5 done (2 fix rounds used; final grade PASS with 6 PARTIAL findings awaiting Daniel's call: adversarial-glob perf +15-17% vs 15% budget, row-ignore follows symlinks, stale fltMatchSkipped binding after Options Cancel, missing hint sentence, untested gitignore_only summary, misleading toast on cap rejection). Gate green except pre-existing pip-audit CVEs (pillow, pypdf, certifi). Uncommitted. progress.md/decisions.md/jevmem notes still to write.

1. **v1.8.0 train** — offline installer Liquid Glass + Finder open fix landed; Unlimited OCR (draft PR #38) still open.
2. Next topic / QA as Daniel directs.

## Next steps

1. Daniel GPU QA / undraft Unlimited OCR (#38) when ready.

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
