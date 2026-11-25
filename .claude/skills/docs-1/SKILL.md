---
name: docs-1
description: Set up and maintain project documentation that AI agents can navigate fast and trust - one subject per Markdown doc with a stable ID, status, dates and the code paths it covers, a generated one-line-per-doc index, and a checker for stale docs, broken links and duplicate IDs. Use when asked to set up, organize, restructure or index project docs, write or update a doc (architecture, how-to, reference, runbook, decision record), find the docs for a file, or check that docs are up to date. Not for code comments, docstrings, generated API reference, or project status and session notes (those belong in project memory).
license: MIT
metadata:
  author: Daniel Illescas Romero <illescas.daniel@protonmail.com>
  version: "1.2.0"
  tags: [documentation, docs, index, frontmatter, staleness]
---

# docs-1

## Purpose

Docs live in `docs/` as plain Markdown. An agent reads `docs/INDEX.md` (one line per doc), opens only the docs it needs,
and can tell from each doc's frontmatter whether the doc is current and which code it describes. The index is generated
from the frontmatter by `scripts/docs_index.py` (next to this file, standard library only), so it never drifts.

```
docs/
  INDEX.md               generated: one line per doc, grouped by area; History last
  <area>/<slug>.md       one subject per doc (areas: a component, feature or audience: api, ops, frontend)
  archive/               deprecated and superseded docs, kept for history
```

Docs that belong next to their code (`specs/<feature>/SPEC.md`, `packaging/README.md`) can stay there: any Markdown file
in the repository with docs-1 frontmatter is indexed, under its top-level folder.

## How to trust what you read

- **Code and config at HEAD win** over a doc. If a doc disagrees with the code, say so, answer from the code, and fix
  the doc in the same change.
- **Check freshness before relying on a doc**: if the doc's `covers` paths changed after `verified`, the doc may be stale.
  `docs_index.py check` lists these docs. Verify the claim you need against the code.
- **`status: deprecated` or `superseded` is history**, never the current answer. Follow `superseded_by`.

## Reading

1. Read `docs/INDEX.md`. Open a doc only when its line says it answers the question.
2. Before changing code, find the docs that cover the files you will touch:
   `python3 <skill dir>/scripts/docs_index.py covers <path>...`. Update them in the same change.
3. Cite docs by ID ("see DOC-012"). IDs survive renames and moves; paths do not.

## Writing a doc

Start from `templates/doc.md`. One subject per doc; split a doc that covers two subjects or passes about 300 lines.

```markdown
---
id: DOC-012
title: Release process
summary: How a version is tagged, built and published to PyPI, who approves it, and how to roll back
type: how-to
status: current
updated: 2026-11-15
verified: 2026-11-15 a1b2c3d
covers: [.github/workflows/release.yml, scripts/release.sh]
related: [DOC-003]
supersedes:
superseded_by:
---

# Release process

Tag `vX.Y.Z` on main; the release workflow builds, waits for approval in the `pypi` environment, then publishes.
Use this when cutting a release or fixing a failed one.

## Steps
...
```

- `id`: `DOC-` plus the next free number (`docs_index.py next-id`). Never reuse or change an ID.
- `summary`: one line that lets a reader decide whether to open the doc without opening it. It becomes the index line.
  Name the specifics: "PyPI, approval, rollback", not "about releases".
- `type`: `tutorial` (learn by doing), `how-to` (steps for a task), `reference` (facts to look up: config keys,
  commands, API), `explanation` (architecture, how and why it works), `decision` (one decision record: context, choice,
  rejected options, consequences), `runbook` (what to do when something breaks).
- `updated`: the last change to the content. `verified`: the date and short commit when the doc was last checked
  against the code; set it only after checking.
- `covers`: the files, folders or globs (`src/auth/**`) the doc describes. This is what makes stale docs detectable.
- Open the body with 1-3 sentences: what this is and when you need it. A reader that needs nothing more stops there.
- Use specific, searchable headings ("Rolling back a bad release", not "Other"). Keep exact commands, paths, versions,
  limits and error messages verbatim; those are what readers search for.
- Point at code (`src/auth/token.py:refresh`) instead of copying it; copied code goes stale silently.

## Changing docs

- **Behaviour changed**: edit the doc in place in the same commit as the code, and update `updated` and `verified`.
  Git keeps the old text.
- **`check` says a doc may be stale**: compare the doc with the code it covers. Fix the doc if it is wrong; then run
  `docs_index.py verify DOC-n` to stamp today's date and commit. A flag does not always mean the doc is wrong.
- **A doc is replaced by another**: set `status: superseded` and `superseded_by: DOC-n` in the old doc, `supersedes` in
  the new one, and move the old file to `docs/archive/`.
- **A feature is removed**: set `status: deprecated`, say what replaced it if anything, and move it to `docs/archive/`.
- **A decision changes**: write a new `decision` doc that supersedes the old one; do not rewrite the old decision.
- After any change, run `python3 <skill dir>/scripts/docs_index.py write` to regenerate `docs/INDEX.md`, then
  `docs_index.py check`.

## Setting up or reorganizing existing docs

0. Create the `docs/` folder if the project has none; the script exits with `no docs folder at docs` without it.
1. Inventory: list the Markdown docs (`docs/`, `README.md`, `ARCHITECTURE.md`, other top-level guides). Leave `README.md`,
   `AGENTS.md`, `CLAUDE.md`, `CHANGELOG.md` and license files where they are; they are not indexed docs.
2. Show the user the plan before moving files: which files get frontmatter, which move into which area, which are split.
   Moving files breaks links from outside the repo, so prefer adding frontmatter in place.
3. Add frontmatter to each doc. Read the doc and the code it describes to fill `summary`, `type` and `covers`. Set
   `verified` only for docs whose claims you checked; otherwise leave it empty.
4. Run `docs_index.py write` and `docs_index.py check`, and fix what it reports.
5. Add the docs paragraph from this skill's README to `AGENTS.md` (or `CLAUDE.md`) so every agent starts at the index.

## Scripts

Run it with `python3 <skill dir>/scripts/docs_index.py [--docs DIR] <command>`.

| Script | Purpose | Main arguments |
| --- | --- | --- |
| `docs_index.py write` | Regenerate `INDEX.md` from the docs' frontmatter | none |
| `docs_index.py check` | Print `ERROR`, `STALE?` and `WARN` lines; exit 1 if there are errors | none |
| `docs_index.py covers` | List the docs whose `covers` match the given files | one or more paths |
| `docs_index.py next-id` | Print the next free `DOC-n` | none |
| `docs_index.py verify` | Stamp `verified: <today> <HEAD>` on the given docs; exit 1 if an ID is unknown | one or more IDs |

`--docs DIR` defaults to `docs`; run from the repository root.

## Examples

- "Organize our docs": inventory the Markdown files, show the plan, add frontmatter in place, run `write` and `check`.
- "Write a runbook for rotating the API key": `next-id`, start from `templates/doc.md`, fill `covers` with the config
  file, then `write`.
- "I'm changing `src/billing.py`": `covers src/billing.py`, read those docs, and update them in the same change.

## Requirements

- Python 3.9 or newer, standard library only. Without a shell, keep the frontmatter and `docs/INDEX.md` consistent by hand.
- `git` is optional: staleness needs a repository with history. Outside git, or if `git` is missing, every command still
  works and `check` validates fields and links but cannot flag stale docs.

## Limitations

- A shallow clone may lack the `verified` commit; `check` then compares by date.
- `check` reads every Markdown file under the repository (skipping `node_modules`, `vendor`, `dist`, `build`, `target`
  and virtualenvs). It only reads files and runs read-only `git` commands; `write` regenerates the index files and `verify` edits the frontmatter of the docs you name.
- `ERROR` lines must be fixed (`check` exits 1). `STALE?` and `WARN` lines are prompts to re-check, not failures.
- A `STALE?` flag means the covered code changed, not that the doc is wrong; only reading both tells.

## Troubleshooting

| Error | Cause | Fix |
| --- | --- | --- |
| `no docs folder at docs` | No `docs/` yet, or not run from the repository root | Create `docs/`, or pass `--docs DIR` |
| `ERROR duplicate id DOC-n` | Two docs share an ID (often a copied doc) | Keep the older doc's ID; give the other `next-id` and fix links to it |
| `ERROR ...: broken link` | A link points at a moved or renamed file | Point it at the current path, or link by ID |
| `STALE?` right after checking a doc | `verified` holds only a date, and commits from that same day count | Run `verify DOC-n` inside the repository so it stores the commit |
| `WARN ...: never verified against the code` | `covers` is set but `verified` is empty | Check the doc against the code, then `verify DOC-n` |

## Rules

- Never delete a doc that has history value; supersede or deprecate it and move it to `docs/archive/`.
- Never invent facts to fill a template section; leave it out or mark it `TODO`.
- Do not record status, plans or session history in docs; they go in the project's memory or issue tracker.
- No secrets, tokens or internal credentials in docs.
