---
name: ignore-rules-own-matcher
description: (1) Own matcher in domain/ignore_rules.py (no pathspec, no re on user input): git semantics (name any depth, /name root only, name/ folders only, !, #, )…
type: decision
date: 2026-10-22
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** 1.8.0 feature "ignore files/folders in search" (specs/ignore-rules/SPEC.md, branch `feature/ignore-rules`).
- **Decision:** (1) Own matcher in `domain/ignore_rules.py` (no `pathspec`, no `re` on user input): git semantics (`name` any depth, `/name` root only, `name/` folders only, `!`, `#`, `**`), linear-time two-pointer/memoised `**`, caps (1000 user lines, 1024 chars, 1 MiB / 10k lines `.gitignore`). Ignore always beats include-hidden/noise/match-skipped; per-search list overrides `.gitignore` (opt-in "respect .gitignore"). Matching is case-insensitive on all OSes (case toggle = future idea). A symlink to a folder counts as a folder; row-ignore uses a symlink's own path, picker picks resolve. (2) "Which files to scan" (six switches) moved from Search options to Filters, ignore list first; the switches persist under settings.json `scan` only with "Remember filters", with read-time migration from legacy `options` keys. (3) Perf budget (<=15% walk overhead, 100 patterns): met on realistic sets (<=~13.5%); an adversarial 50x`*q{i}*z`+25x`f?{i}x` set measures +15..+17% — **accepted by Daniel for now** (2026-10-22); revisit with a cheaper per-folder prefilter if it matters.
- **Rationale:** `pathspec` is ReDoS-prone and accepts malformed input like `[oops`; one persistence owner for the switches avoids the either-box ambiguity; Filters is the natural home next to the ignore list.
