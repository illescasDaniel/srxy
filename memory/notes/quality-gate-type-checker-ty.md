---
name: quality-gate-type-checker-ty
description: Replace basedpyright with ty in the dev group; Unix scripts/quality/ty.sh and Windows checks-win.ps1 both run ty check --output-format github. Config…
type: decision
date: 2026-08-30
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** basedpyright was slow in the day-to-day gate; Astral's `ty` is far faster and already in the Astral toolchain with Ruff/uv.
- **Decision:** Replace `basedpyright` with `ty` in the `dev` group; Unix `scripts/quality/ty.sh` and Windows `checks-win.ps1` both run `ty check --output-format github`. Config lives under `[tool.ty]` with rule/override parity for the old basedpyright relaxations (unknown/attribute noise, optional semantic/windows imports). Scope remains `src` + `tests` (scripts/packaging/examples excluded).
- **Rationale:** Same gate surface on both platforms, much lower type-check wall time; github annotation format plugs into existing `gate_emit.py` counting.
