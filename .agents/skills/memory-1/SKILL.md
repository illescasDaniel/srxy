---
name: memory-1
description: Keep a portable, git-tracked memory of what the code cannot tell a future session (what we are doing and what is next, decisions and why, reversals, user preferences, incidents) as a short status file plus one-fact Markdown notes with dates and supersession, and an optional archive of condensed session transcripts. Use at session start, when the user asks why the code is the way it is or what was decided before, after a decision or reversal, when the user states a preference or corrects you, after an incident is resolved, before ending a session, and when asked to set up memory or export past sessions. Not for project documentation, rules the agent must always follow (AGENTS.md or CLAUDE.md), or secrets.
license: MIT
metadata:
  author: Daniel Illescas Romero <illescas.daniel@protonmail.com>
  version: "1.2.0"
  tags: [memory, notes, decisions, sessions]
---

# memory-1

## Purpose

Project memory lives in `memory/` as plain Markdown, so any agent that can read files can use it (Claude Code, Codex,
Cursor, others). No service and no database: `grep` is the search engine.

```
memory/
  NOW.md                 status: what we are doing, what was just done, what is next, open questions (overwritten)
  LATER.md               optional: open items that are not next, one line each (not read at session start)
  MEMORY.md              index: one line per note (small memory) or one line per topic page (large memory)
  notes/<slug>.md        one fact per file, dated, with status and supersession links
  topics/<topic>.md      optional wiki page per subject: summary, how it evolved, links to its notes (see Growing)
  sessions/              optional, local only (git-ignored): condensed transcripts of past sessions (exported, redacted)
  sessions/INDEX.md      one line per session: date, file, what it was about (also local, never committed)
  .gitignore             one line, `/sessions`: keeps the archive out of git
```

## How to trust what you read

- **Code and config at HEAD win** for what the code does today. If a note says otherwise, the note is stale: say so,
  answer from the code, and fix or supersede the note.
- **Notes win** for why something is the way it is, what was decided before, what the user prefers, and what happened.
  The code cannot confirm these, so do not discount a note because the repository does not mention it.
- **The newest current note wins** between notes. A note with `status: superseded` is history: use it to answer "what
  did we decide before / what changed", never as the current answer.
- **Sessions hold the detail.** A note is a summary; when you need exact numbers, names, commands or the sequence of
  events, open the session file named in the note's `source`, or search `memory/sessions/` directly.

## Session start

1. Read `memory/NOW.md` and `memory/MEMORY.md`. Check `NOW.md` against `git log` and `git status` since its date:
   work listed as next may already be done. If `memory/` is missing and the user wants memory, set it up from
   `templates/` next to this file (NOW.md, MEMORY.md, and, only if transcripts will be archived, sessions/INDEX.md and
   `templates/.gitignore` as `memory/.gitignore`; if that file exists already, append its `/sessions` line instead).
   While setting up, look for an existing project memory: a `memory/` folder in another layout, `memory-bank/`,
   `.agemem/`, notes or status files, memory sections in `AGENTS.md` or `CLAUDE.md`. If you find one, tell the user what
   it is and propose a migration: current status to `NOW.md`, open items to `LATER.md`, each durable fact or decision to
   a note with its original date, then the index. Keep the old files until the user confirms they can be removed.
2. When the user says "continue" or "where were we", answer from `NOW.md` (checked against git), then the notes.
3. Open individual notes only when the task touches them. For history questions, read the topic page if there is
   one, then search `memory/notes/` and `memory/sessions/` with grep before answering. Topic pages summarise: take
   exact numbers, names and preferences from the linked notes, not from the page.

## What to save

Save what a future session cannot derive from the code or `git log`:

- **decision**: what was chosen, the reason, and the rejected alternatives. Keep the specific facts that justify it
  (numbers, versions, error messages, file names): "per-line requests: detection 0.87 vs 0.37 when batched".
- **preference**: how the user wants work done, including corrections ("do not X; do Y"), with their reason if given.
- **incident**: something that went wrong, its cause, and how it was resolved or recovered.
- **gotcha**: a non-obvious constraint or trap in tools, libraries or the environment.
- **context**: who, why or when facts about the project that are not in the repository.

Do not save in notes: what the code, tests or docs already say; git history; work in progress, current status or next
steps (they go in `NOW.md`); secrets.

## NOW.md: what we are doing and what is next

One short file (at most 50 lines) that the next session, in any agent, reads first. Rewrite it from scratch each time
for the work as it stands now; never append to the previous text or keep an "Earlier:" trail.

```markdown
# Now
Updated: 2026-11-15 (session 2026-11-15-ab12cd34.md)

## Doing
Settings screen: moving the in-app help pages to the native WebView.
## Done recently
- Replaced the bundled Chromium view on the login screen (commit 1a2b3c4).
## Next
1. Port the help pages; keep JS bridge off (see notes/webview-native-over-chromium.md).
## Open questions / blocked
- Does Android 9 need the AndroidX WebKit fallback? Waiting for the user.
```

- Write it whenever the plan changes and always before ending a session in which work happened, even if the user did
  not ask. A session that ends without updating `NOW.md` leaves the next agent guessing.
- `Next` starts with the next step the user named, in their words; your own follow-ups go after it, marked as yours.
- Name decisions only by linking their note; the reason lives in the note, not here.
- Keep it small, section by section: `Updated` names one session; `Doing` is the current work only (up to 5 lines);
  `Done recently` has at most 5 one-line items from the latest sessions (delete older ones: git and the notes keep
  them); `Next` has at most 7 items; no other sections.
- Open items that are not among the next steps go to `memory/LATER.md` (see below), not into extra sections here.

## LATER.md: open items that are not next

A short backlog (at most 40 lines), not read at session start. Read it when the user asks what is pending, when `Next`
is empty, and grep it for the subject before starting work on that subject.

```markdown
# Later
## Releases
- 2026-11-12 (User) Decide whether Linux arm64 gets a build.
## Help pages
- 2026-11-15 (User) Test on a real device: FAQ grid on Ubuntu 20.04, search box on Android 9, dark mode.
## Suggestions
- 2026-11-15 Fix the dependency audit before the next release: it fails on two advisories and the last two releases skipped it ([note](notes/release-audit-skipped.md)).
```

It has two kinds of line. Under subject headings: **what the user owes** (`(User)`: a decision, a test only they can
run, something they asked to do later). Under `## Suggestions`, always the last section: **your own follow-ups**, at
most 8.

- **What goes in:** something a person would actually act on later. A caveat about finished work ("not tried on a real
  phone") belongs in that work's note, not here. Do not add "check that X finished" items for routine steps.
- **One line per thing to do or decide, at most 240 characters.** Each line starts with a date. Say what to do and link
  the note; the detail (versions, file names, what was tried) stays in the note. Before adding, look for a line asking
  for the same action and extend it (as the device-test line above does), keeping its oldest date. Do not join separate
  actions into one line to save lines: a line that needs "and" or ";" between two different actions is two items.
- **Delete, do not keep:** lines that are done, and lines overtaken by events (a check on release 1.2 once 1.4 is out;
  a question about code that was since rewritten). Git keeps the history.
- **A suggestion must matter.** Add one only when skipping it has a cost you can name: a bug or failing check left in
  place, a risk to data or security, something that will block or break a coming release. Say what to do and when
  ("before the next release", "when touching the importer"), and why if the line does not make it obvious. No
  nice-to-haves, no "could also", nothing the user already declined.
- **Suggestions are raised, then settled.** When the work reaches a suggestion's moment (its subject is being changed,
  the release is being prepared) or the user asks what is pending, tell the user about it. If they accept, it moves to
  `NOW.md` Next or becomes a `(User)` line; if they decline, delete it and, when the reason is a preference, save a
  note. A suggestion older than 30 days that was never raised is raised once at the next natural pause, then deleted
  unless accepted. When there are more than 8, delete the ones with the lowest cost first.
- **When the file passes 40 lines, prune in this order:** delete done and overtaken lines; merge lines that ask for the
  same action; delete suggestions down to the 3 that matter most. Never silently delete a `(User)` line that is still
  open: if `(User)` lines alone exceed the limit, or some are older than 30 days, list them to the user at the next
  natural pause and ask which to keep, then delete the rest. If the user is not there, put that question first in
  `NOW.md` under Open questions.

## How to write a note

One fact per file in `memory/notes/`, named `<slug>.md` (short, kebab-case, specific: `secret-scan-per-line-requests`).

```markdown
---
name: secret-scan-per-line-requests
description: Secret scanner sends one candidate line per model request because batching hurt detection
type: decision
date: 2026-10-05
status: current
supersedes:
superseded_by:
source: 2026-10-05-1a2b3c4d.md
---

The secret scanner sends each candidate line to the local model in its own request.

**Why:** batching several lines dropped detection from 0.87 to 0.37 (position effects); the extra cost is ~70 ms/line.
**Rejected:** batches of 8 lines.
**How to apply:** do not batch candidate lines when changing the scanner.
```

- Use absolute dates (`date:` is when the fact was established). Convert "today" or "yesterday" from the session date.
- `source:` names the session file in `memory/sessions/` when the archive exists; leave it empty otherwise.
- Write `**Why:**` for decisions and preferences; add `**Rejected:**` and `**How to apply:**` when they exist.

## Before saving: update, supersede, or add

Read `MEMORY.md` and grep `memory/notes/` for the subject first.

- **Same fact, more detail**: edit the existing note.
- **The decision or preference changed** (a reversal): never edit the old note's fact. Create a new note that states
  the new choice and why it changed ("Reversal: ... replaced X because ..."), with `supersedes: <old slug>`. In the old
  note set `status: superseded` and `superseded_by: <new slug>`. Move the old index line to the History section.
- **The note was simply wrong**: fix it, or delete it if it has no historical value.
- **New subject**: add a note and an index line.
- If the subject has a topic page, update the page's summary and note list in the same edit.

## MEMORY.md

```markdown
# Memory

Code at HEAD wins for current behaviour; notes win for why and history; newest current note wins; open `source` sessions for detail.

## Decisions
- [Secret scan: one line per request](notes/secret-scan-per-line-requests.md) 2026-10-05: batching dropped detection 0.87 → 0.37
## Preferences
## Incidents
## Gotchas
## Context
## History (superseded)
- [Task MCP: one tool per task](notes/task-mcp-tool-per-task.md) 2026-10-01 → superseded by task-mcp-single-tool
```

One line per note: link, date, and a hook specific enough to decide whether to open it. Keep it under about 150 lines
(it is read at the start of every session, so its size is paid every time); past that, switch to topic pages.

## Growing: topic pages

When `MEMORY.md` passes 150 lines (the check says so), or one subject has about 8 or more notes, group notes by subject into
`memory/topics/<topic>.md`, one page per subject (a feature, component or area: `phone-picker`, `releases`). Notes stay
where they are; a page is a map and a synthesis, not a copy.

```markdown
# Help pages
Updated: 2026-11-20. Related: [installer](installer.md), [security](security.md)

## Now
Help pages render in a bundled Chromium (CEF) view ([help-view-cef](../notes/help-view-cef-backend.md)); JS bridge off
([help-js-bridge-off](../notes/help-js-bridge-off.md)).
## How it got here
- 2026-11-12 native system WebView chosen: Chromium added ~38 MB to the installer ([note](../notes/help-view-native-webview.md)).
- 2026-11-15 reversed to CEF: WebKitGTK on Ubuntu 20.04 broke the FAQ's CSS grid ([note](../notes/help-view-cef-backend.md)).
## Notes
- [Help view: bundled CEF](../notes/help-view-cef-backend.md) 2026-11-15: consistent rendering over installer size
- [Help pages: JS bridge off](../notes/help-js-bridge-off.md) 2026-11-12: security; no page-to-app calls
## History (superseded)
- [Help view: native WebView](../notes/help-view-native-webview.md) 2026-11-12 → superseded by help-view-cef-backend
```

- Do the switch in the session where the limit is passed, starting with the subjects that have the most notes; it
  does not have to cover every note at once.
- `MEMORY.md` then holds the trust line, one line per topic page (link, note count, what it covers), the newest ~20
  notes, and notes that fit no topic.
- Keep each page shorter than the notes it covers; it should abstract, not repeat. Every claim links its note.
- Keep superseded choices in "How it got here" and History: "what did we decide first" must stay answerable.
- One page per subject, edited by one session at a time; do not merge subjects into one long page.

## Session archive (optional)

The archive keeps the detail that notes summarise away. Export past sessions with the script next to this file:

```bash
python3 <skill dir>/scripts/export_sessions.py --project .
```

It reads Claude Code (`~/.claude/projects/`), Codex (`~/.codex/sessions/`) and opencode (its SQLite database,
read-only) transcripts for this project, keeps only
user and assistant prose, redacts credential-like strings, and writes one file per session. It prints only the files
that are new or changed (a session that grew since the last export is rewritten), so it is safe to run every time.

After exporting, add one line per new session to `memory/sessions/INDEX.md` (and refresh the line of an updated one):
`- 2026-10-05 [2026-10-05-1a2b3c4d.md](2026-10-05-1a2b3c4d.md): secret scanner batching vs per-line requests; moved v0.3.0 tag`.

Transcripts are personal working history: the whole archive, `INDEX.md` included, stays on this machine, ignored by
`memory/.gitignore` (`/sessions`). To share a decision or a reason with the team, write a note in `memory/notes/`.
In a linked git worktree the archive lives in the main checkout: the exporter writes there, collects the sessions of
every worktree, and links `memory/sessions` to it when it can.

If `git ls-files memory/sessions` lists anything (an older setup committed it), run `git rm -r --cached memory/sessions`
and add the `/sessions` rule to `memory/.gitignore`; the old copies stay in git history.

## End of session

Before finishing a session in which work happened (when the user says thanks, stop, that's all, or the task is done):
rewrite `NOW.md`, write or supersede the notes, update `MEMORY.md` and any affected topic page, and, if the archive
is used, export the session and add its `INDEX.md` line. Keep edits small; do not rewrite notes that did not change.

Then run the check and do what each `FIX` line says (it reports a `NOW.md`, `LATER.md` or index that grew past its limit, notes
missing from the index, and broken supersession links):

```bash
python3 <skill dir>/scripts/memory_check.py --memory memory
```

Without a shell, count instead: `NOW.md` at most 50 lines, `LATER.md` at most 40 (each at most 240 characters, at most 8 suggestions), `MEMORY.md` at most 150.

## Alongside other memory

- Rules the agent must always follow belong in `AGENTS.md` or `CLAUDE.md`. Point `AGENTS.md` at `memory/MEMORY.md`
  so agents that do not load skills still find the memory.

## Scripts

Run them with `python3 <skill dir>/scripts/<name>`.

| Script | Purpose | Main arguments |
| --- | --- | --- |
| `memory_check.py` | Check the memory folder: size limits, index coverage, supersession links; prints `FIX` lines | `--memory DIR` (default `memory`) |
| `export_sessions.py` | Export condensed, redacted transcripts of this project's past sessions | `--project DIR`, `--out DIR`, `--since YYYY-MM-DD`, `--max-chars N`, `--claude-dir DIR` (repeatable), `--dry-run` |

## Examples

- "Set up memory": create `memory/` from `templates/`, migrate any existing project memory, and fill `NOW.md`.
- "We chose SQLite over Postgres because we run one node": grep the notes, then write a dated `decision` note and its
  index line; if it reverses an earlier note, supersede that note.
- "Why are retries capped at 3?": search `MEMORY.md` and `memory/notes/`, answer from the note, and cite it.

## Requirements

- Python 3.9 or newer, standard library only. Without a shell, do the checks by hand (limits are under End of session).
- `git` is optional: without it, `NOW.md` cannot be checked against `git log` and worktrees are not detected.

## Limitations

- Transcript export is opt-in: run it only when the user wants an archive.
- It reads the local transcript stores of Claude Code, Codex and opencode, read-only, and keeps only sessions whose
  working directory is inside this project or one of its git worktrees. Other projects' sessions are not written.
- The output stays on this machine, in the git-ignored `memory/sessions/`.
- Redaction is pattern-based and can miss things: skim an export before sharing anything from it.
- If a source is missing, or opencode's database is locked or unreadable, the script skips it with a note on stderr.
  Re-run it later.

## Troubleshooting

| Error | Cause | Fix |
| --- | --- | --- |
| `FIX` lines from `memory_check.py` | A file passed its size limit, a note is missing from the index, or a supersession link is broken | Do what each line says, then re-run the check |
| `no Claude Code, Codex or opencode sessions found` | No transcripts for this folder, or they live elsewhere | Run from the project root; pass `--claude-dir DIR` for a non-default Claude Code folder |
| `opencode: cannot open its database` | opencode is writing to it, or it is unreadable | Close opencode or wait, then re-run; the other sources are still exported |
| `could not link ...` | The filesystem does not allow symlinks (common on Windows) | Nothing to fix: sessions are in the main checkout's `memory/sessions/` |
