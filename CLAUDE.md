@AGENTS.md

## Agents and delegation

You are the orchestrator: delegate to the `architect`, `coder`, `code-grader` and `utility` subagents in
`.claude/agents/`, and own every approval gate and memory write. Routing, briefs and the memory protocol:

@.claude/development-workflow.md

## Memory bank

Project state lives in `memory/` (git-tracked, so it follows the branch). At session start, read
`memory/activeContext.md` then `memory/progress.md`. Update on these triggers only: a task is completed or discovered
(`progress.md`); focus changes, a blocker is hit or work concludes (`activeContext.md`); a significant technical
decision is made (`decisions.md`, append-only, newest first). Full protocol: the `memory-bank` skill.

## Phase Gate Protocol (Spec-Driven Development)

Every feature or user-facing change goes through these phases. Full workflow: the `sdd-feature` skill.

| Phase | Deliverable | Gate |
|-------|-------------|------|
| **0 — Design** | `wireframes/<screen>.html` (self-contained HTML/CSS) | **Stop.** Ask for design approval. |
| **1 — Spec** | `specs/<feature>/SPEC.md`: agreed Design decisions (success criteria, failure handling, performance/resource budget, trust boundary), BDD scenarios, Out of scope | **Stop.** Ask for spec approval. |
| **2 — Architecture** | Domain types and interfaces only | **Stop.** Ask for approval before tests/adapters. |
| **3 — Tests** | Unit tests from the BDD scenarios | Run them. |
| **4 — Implementation** | Use cases, adapters, UI | Until tests pass; must match the approved wireframe. |
| **5 — Grade** | Read-only `code-grader` subagent scores the branch against the spec | Automatic: fix FAILs, max 2 rounds, show the scorecard. |

- **Never skip a gate.** "Implement the plan", "complete all todos", an attached plan file or plan-mode approval is
  **not** design or spec approval; approval must be explicit, in chat. One gate per approval: after the wireframe, end
  the turn and wait.
- If implementation reveals a spec flaw, rewrite the spec, get re-approval, then continue. Don't patch around a bad spec.
- No production code before spec approval. Allowed before it: `wireframes/`, `specs/` and docs.
