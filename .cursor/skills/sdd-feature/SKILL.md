---
name: sdd-feature
description: Run Spec-Driven Development with explicit human approval gates (wireframe, spec, architecture, then tests and implementation, then an independent grade). Use when adding or changing a user-facing feature or flow, writing a wireframe or SPEC.md, or implementing from acceptance criteria.
---

# SDD feature workflow

Build features in gated phases: **design → spec → architecture → tests → implementation → grade**. Each of the first
three phases ends with a deliverable the user reviews and approves **in chat** before the next one starts. The approved
spec is the source of truth: the code follows the spec, never the other way round.

## Project settings

Read `AGENTS.md` / `CLAUDE.md` first. The project may override any of these defaults:

| Setting | Default |
|---------|---------|
| Wireframes | `wireframes/<screen>.html` |
| Specs | `specs/<feature>/SPEC.md` |
| Domain types and interfaces (Phase 2) | the project's core layer, e.g. `domain/` + `ports/` in a hexagonal layout |
| Quality gate (lint, types, tests) | the project's documented check command |
| Test naming | `test_given_…_when_…_then_…` with `# given` / `# when` / `# then` comments (or the project's equivalent) |

Use the project's paths and commands wherever this document names a default.

## Mandatory gates (explicit human confirmation)

Do **not** skip or batch gates. After each gate deliverable, **end the turn** and ask the user to approve.

| User says | Agent may do |
|-----------|--------------|
| "Add feature X" / "implement the plan" / plan approved / "complete all todos" | **Phase 0 only** (wireframe), then end the turn for **design approval** |
| User approves the wireframe in chat | Phase 1 only (spec), then stop for **spec approval** |
| User approves the spec | Phase 2 (domain types and interfaces), then stop for **architecture approval** |
| User approves the architecture | Phases 3–4 (tests, then implementation), then Phase 5 (grade) |

An attached plan file, plan-mode approval, or a todo list that names every phase is **not** wireframe or spec
approval. The user must confirm each gate in chat (for example "wireframe approved", "spec approved").

### Anti-patterns (never do this)

- Writing the spec or production code in the **same turn** as the first wireframe.
- Treating "implement the plan" as permission to run Phases 0–4 back to back.
- Skipping the review pause: always tell the user **where** to open the wireframe and **wait** for their reply.
- Changing production source before spec approval, except refactors that keep existing specs green.
- Patching around a spec flaw found in Phase 4. Rewrite the spec (Phase 1), get re-approval, then continue.

## Phase 0 — Wireframe (design)

Create or update `wireframes/<screen>.html`: one self-contained HTML/CSS file (no build step, no network), using the
real copy, states and edge cases rather than lorem ipsum. Show every state the spec will mention (empty, loading,
error, success), and a narrow/mobile width where relevant. Notes meant only for the reviewer go in clearly labelled
"Review only" boxes that never ship.

No UI at all (library, CLI, API)? Ask the user whether to skip Phase 0 or to sketch the interface instead (usage
examples, request/response shapes). Skipping is itself a decision the user makes in chat.

**Stop. End the turn** with:

- Path: `wireframes/<file>.html`
- How to open it (`xdg-open …`, `open …` or `start …` for the user's OS)
- Ask: "Please review the wireframe — reply *wireframe approved* (or the changes you want) before I write the spec."

## Phase 1 — Spec

**Step 1 — Agree four design decisions before writing the spec body.** Draft a proposed answer for each and ask the user
to confirm or adjust. Do not silently invent them. Each must be answered or marked `N/A — <reason>`; empty is not
allowed.

| Decision | Pin down |
|----------|----------|
| Success criteria | Observable "done" beyond the scenario list: the user outcome and measurable thresholds (no data loss, idempotent re-run, …) |
| Failure handling | What can fail, what the user sees, retry / skip / quarantine, partial state and resume |
| Performance & resource budget | Latency and throughput targets, CPU / memory / disk / network cost, size limits |
| Trust boundary | Which input is untrusted (paths, uploads, network clients, subprocess arguments), what is trusted, what may touch the filesystem or network, and where it is validated |

**Step 2 — Write `specs/<feature>/SPEC.md`** from [`templates/SPEC.md`](templates/SPEC.md) (next to this file):

- `## Metadata`: feature summary, wireframe link, approval dates
- `## Design decisions`: the four above, right after Metadata
- `## Triggers & routing`: how the user enters and leaves the flow
- `## Visual & UI rules`: aligned with the approved wireframe
- `## Acceptance criteria`: `### Scenario:` blocks with **Given** / **When** / **Then**. Every failure-handling and trust-boundary decision needs at least one scenario.
- `## Out of scope`

Optionally run `python3 scripts/spec_check.py specs/<feature>/SPEC.md` (next to this file) to catch structural gaps.

**Stop.** Ask: "Please review `specs/<feature>/SPEC.md` (including Design decisions) — approve so I can add the
domain types and interfaces?" Record the approval dates in Metadata once given.

## Phase 2 — Architecture

Add or update only the core of the feature:

- Domain entities and value objects
- Inbound interface(s) for the use case (what the UI / API calls)
- Outbound interface(s) for what the use case needs from the outside world (storage, network, clock, processes)

No adapters, frameworks or UI yet. **Stop for architecture approval** before Phase 3.

## Phase 3 — Tests

Map each `### Scenario:` to at least one test named after it, for example
`test_given_long_url_when_rendered_then_stays_on_one_line`, with `# given` / `# when` / `# then` sections. Test
use cases and domain logic through their interfaces with in-memory fakes, not through HTTP routes or real I/O. Keep
them fast: no sleeps, network or subprocesses. Implementations may still be stubs; run the tests and confirm they fail
for the right reason.

## Phase 4 — Implementation

Use cases, adapters and production UI until the tests and the full quality gate pass. The UI must match the approved
wireframe; if layout or behaviour has to change, update the wireframe and/or spec and get re-approval first. If the
project keeps a memory bank or changelog, update it at milestones.

## Phase 5 — Grade

Runs automatically once Phase 4 is green. It only reads code, so it is **not** an approval gate.

1. Spawn the read-only **`code-grader`** subagent with the spec path(s) and the diff base (default `main`). If the
   project has not installed it, spawn a fresh general-purpose subagent whose prompt is the body of
   [`agents/code-grader.md`](agents/code-grader.md) (next to this file) plus the inputs. Never grade your own work in
   your own context: the grader must start fresh.
2. Fix every FAIL (and PARTIAL where cheap), re-run the quality gate, and re-spawn the grader. **At most 2 fix
   rounds**; if it still says NEEDS WORK, stop and report the remaining findings.
3. If a finding shows the spec itself is wrong, follow the spec-flaw rule: rewrite the spec and get re-approval.
4. Show the user the final scorecard verbatim (verdict, table, unresolved findings). The user makes the final call.
