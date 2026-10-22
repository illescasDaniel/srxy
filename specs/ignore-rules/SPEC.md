# Ignore files & folders in search

## Metadata

- **Feature:** Users can exclude files and folders from a search with gitignore-style patterns (typed or picked), optionally also honouring `.gitignore` files, from the GUI, TUI and CLI. Ignored entries are skipped entirely (name and content).
- **Wireframe:** [wireframes/ignore-rules.html](../../wireframes/ignore-rules.html). **Wireframe approved** 2026-10-21 (chat); **revised 2026-10-21** (“Which files to scan” moves into Filters) — approved 2026-10-21 (chat)
- **Design decisions approved:** 2026-10-21 (chat)
- **Spec approved:** 2026-10-21 (chat)
- **Related:** none (extends persisted Filters, `SearchFilters`)

## Design decisions

### Success criteria

- An ignored entry is never yielded by the file walker. Ignored directories are pruned during the walk, so nothing beneath them is stat'ed, read, hashed, cached, extracted or sent to a worker.
- Matching follows git semantics exactly:
  - `start` matches any file or folder named `start` at any depth;
  - `/start` matches only at the search root;
  - `start/` matches folders only;
  - `*`, `?`, `[...]`, `**`, `!` re-include, `#` comments, blank lines, and `\` escape work as in gitignore;
  - a file cannot be re-included when a parent folder is excluded.
- Ignore always wins over `include_hidden`, `include_noise`, `include_noise_files` and `match_skipped_names`: an ignored path is never searched and never name-matched.
- The file-count probe (progress total) and the listing walk apply the same rules, so totals agree with what is searched.
- The search root itself is never ignored. Paths are matched as root-relative `/`-separated strings.
- Precedence: the per-search list beats deeper `.gitignore` files, which beat shallower ones. Within one source, the last matching line wins. A user `!x` re-includes something a `.gitignore` excludes.
- Matching is **case-insensitive on every OS**, consistent with srxy's case-insensitive search. (A future case-sensitivity toggle would also drive this; out of scope here.)
- With the list empty and "respect .gitignore" off, results are identical to 1.7 behaviour.

### Failure handling

- Invalid pattern in the per-search list (unclosed `[`, trailing `\`, over the size caps): GUI/TUI show an inline error naming the line, OK is disabled and nothing is saved; the CLI prints `srxy: error: --ignore '<pattern>': <reason>` and exits with code 2 before any search work.
- Invalid lines inside a `.gitignore` are skipped silently (as git does). An unreadable `.gitignore` contributes no rules and no warning; the search completes.
- A hand-edited invalid persisted ignore list makes the persisted filters fall back to factory defaults (today's rule for invalid persisted filters). A 1.7 settings file with no ignore keys loads with an empty list and `.gitignore` off.
- Picking a file or folder outside the search root is rejected with a message; nothing is added.
- Adding a rule that already exists in the list is a no-op.
- Undo removes only the rule just added, never other lines.

### Performance & resource budget

- No patterns and checkbox off: no measurable overhead (matching code path skipped).
- Up to 100 patterns: at most 15% walk-time overhead on a 100k-entry tree; typically faster because ignored folders are pruned.
- Matching time is linear in path-segment length for any pattern/name; no pattern can cause catastrophic backtracking (own matcher, no backtracking regexes on user input).
- Caps: 1,000 lines and 1,024 characters per line in the per-search list; each `.gitignore` is read up to 1 MiB and 10,000 lines (the rest is ignored).
- Pattern strings are plain JSON-safe values in the search args; worker subprocesses compile them themselves. The content cache gets no new reads or writes; existing entries for newly ignored paths are left in place.

### Trust boundary

- Pattern text from any source (typed, CLI, persisted settings, `.gitignore`) is untrusted. It is used only for matching strings, never to open, stat or resolve a path. `..` segments never match anything.
- `.gitignore` files are read only from directories the walk visits (the search root and below), decoded as UTF-8 with replacement, never followed through symlinks. They are read even when hidden-file skipping is on. With "respect .gitignore" on, `.git/` is always ignored.
- Symlinks are matched by their own path (not their target); `followlinks` behaviour is unchanged. A symlink to a folder counts as a folder (so `link/` matches it), a deliberate difference from git; links to files or broken links count as files.
- Paths are normalised to `/` on Windows; picked paths are always written with `/`. `\` remains the gitignore escape character.
- Picked paths are made root-relative via `resolve()`; any pick that resolves outside the root is rejected.
- Persistence: the ignore list and the checkbox are saved to user settings only when "Remember filters" is ticked (the existing filters rule, extended to the TUI). Within a session, the list stays for all searches regardless. Anchored patterns (`/src/old/`) apply to whatever root the next search uses.

## Triggers & routing

- **Entry:**
  - GUI: Filters dialog → "Which files to scan" section (first section; the ignore list is its first item); result-row context menu → "Ignore this file", "Ignore folder “x/”", "Ignore all “*.ext” files" (archive member rows offer only "Ignore archive").
  - TUI: Filters button → Filters modal → "Which files to scan" section (first section; scrollable), ignore box and checkbox first.
  - CLI: `--ignore PATTERN` (repeatable) and `--respect-gitignore`.
- **Exit:** GUI OK closes the dialog with rules applied to the next search; Cancel discards edits. Row-ignore stays on the results screen with a toast (Undo / Edit list). CLI invalid pattern exits 2; otherwise the normal search output (the `--json` shape is unchanged: still a top-level array).

## Visual & UI rules

- **"Which files to scan" moves from Search options to Filters** (GUI and TUI): subdirectories, archives, hidden, cache & vendor folders, junk & lock files, skipped file names and the binary-looking-files hint. The Search options dialog/modal keeps only "Where to search" and "How to match". These six switches keep their meaning, defaults, storage (search options) and CLI flags; Filters OK applies filters and switches together, Cancel discards both; "Reset to defaults" in Filters resets them, the Options reset no longer does.
- Persistence of the moved switches: they are saved under Filters (settings.json `scan`, written only when "Remember filters" is ticked) and are no longer part of the persisted search options. Simple migration: when loading, if `scan` is absent but the old persisted `options` blob has those keys, they are used as the scan switches (and dropped from `options` on the next save). A 1.7 settings file therefore keeps its values, provided "Persist options" was on and "Remember filters" is ticked next time they are saved.
- GUI and TUI follow `wireframes/ignore-rules.html`: the Ignore list is the first item of the new first section of Filters, same scroll area, same OK-disabled-on-error behaviour, info button, "Add file…" / "Add folder…" (GUI only), "Respect .gitignore files" checkbox, summary text "ignoring N patterns (+.gitignore)" in the filters summary.
- Reset in the Filters dialog clears the list and unticks the checkbox.
- When "respect .gitignore" is on but the list is empty, the filters summary reads "ignoring .gitignore matches" (`filters.summary.gitignore_only`) instead of "ignoring N patterns (+.gitignore)".
- All strings are localised (EN, ES) via the existing i18n layer. Primary buttons use `AccentButton`.
- TUI changes add snapshot tests; GUI changes add/refresh text-tree snapshots.
- "Review only" boxes and the `--json` example line in the wireframe's CLI block that shows an `ignore` key do not ship (wireframe to be corrected).

## Acceptance criteria

### Scenario: bare name matches files and folders at any depth

**Given** the rule `start` **When** searching a tree with `a/start` (file) and `b/start/` (folder with files) **Then** both are skipped, and nothing beneath `b/start/` is read.

### Scenario: leading slash anchors to the root

**Given** the rule `/start` **When** searching **Then** `<root>/start` is skipped and `a/start` is searched.

### Scenario: trailing slash matches folders only

**Given** the rule `logs/` **When** searching a tree with a folder `logs` and a file named `logs` **Then** the folder is pruned and the file is searched.

### Scenario: glob and re-include

**Given** the rules `*.log` and `!keep.log` **When** searching **Then** `debug.log` is skipped and `keep.log` is searched.

### Scenario: cannot re-include under an excluded folder

**Given** the rules `build/` and `!build/keep.txt` **When** searching **Then** `build/keep.txt` is still skipped.

### Scenario: double-star in the middle

**Given** the rule `docs/**/draft*` **When** searching **Then** `docs/a/b/draft1.md` and `docs/draft2.md` are skipped.

### Scenario: comments and blank lines

**Given** a list with `# note` and blank lines **When** parsed **Then** no rule is created from them.

### Scenario: case-insensitive on every OS

**Given** the rule `Build/` **When** searching a tree with `build/` on any OS **Then** the folder is skipped.

### Scenario: ignore beats include-hidden

**Given** the rule `.cache/` and `include_hidden` on **When** searching **Then** `.cache/` is still skipped.

### Scenario: ignore beats include-noise and match-skipped-names

**Given** the rule `node_modules/` with `include_noise` and `match_skipped_names` on **When** searching **Then** no content is searched and no file name from `node_modules/` is matched.

### Scenario: totals and workers see only non-ignored paths

**Given** an ignored folder with 1,000 files **When** a search runs (including the subprocess/heavy path) **Then** the progress total excludes them and no extractor, cache or worker receives them.

### Scenario: respect .gitignore with nested files

**Given** "respect .gitignore" on, a root `.gitignore` with `*.tmp`, and `sub/.gitignore` with `!keep.tmp` **When** searching **Then** `a.tmp` is skipped and `sub/keep.tmp` is searched.

### Scenario: .gitignore off has no effect

**Given** "respect .gitignore" off and a `.gitignore` with `*.tmp` **When** searching **Then** `*.tmp` files are searched.

### Scenario: user list overrides .gitignore

**Given** "respect .gitignore" on, `.gitignore` excluding `x.txt` and user rule `!x.txt` **When** searching **Then** `x.txt` is searched.

### Scenario: .git is always ignored with .gitignore support on

**Given** "respect .gitignore" on **When** searching a repository **Then** nothing under `.git/` is searched.

### Scenario: symlinked .gitignore is not read

**Given** "respect .gitignore" on and `.gitignore` is a symlink to a file with `*` **When** searching **Then** its rules are not applied.

### Scenario: malformed or oversized .gitignore

**Given** a `.gitignore` with invalid lines, or one larger than 1 MiB **When** searching **Then** valid lines within the caps apply and the search completes.

### Scenario: unreadable .gitignore

**Given** a `.gitignore` that cannot be read **When** searching **Then** the search runs without its rules and shows no error.

### Scenario: pathological pattern stays linear

**Given** the rule `**********b` and 255-character file names **When** matching **Then** each match completes in linear time (no stall).

### Scenario: traversal-looking pattern

**Given** the rule `../etc/passwd` **When** searching **Then** nothing outside the root is touched and nothing matches.

### Scenario: symlink to a folder counts as a folder

**Given** a symlink `link` pointing to a folder (e.g. `.cursor/skills -> .claude/skills`) **When** searching with rule `link` or `link/` **Then** the symlink entry is matched by its own path in both cases. This deliberately differs from git, where `link/` does not match a symlink. Contents behind the link are never searched either way (links are not followed).

### Scenario: symlink to a file or a broken symlink counts as a file

**Given** a symlink `link` pointing to a file (or to nothing) **When** searching with rule `link/` **Then** it is not matched; rule `link` matches it.

### Scenario: invalid pattern in the GUI

**Given** the Ignore box contains `[oops` on line 2 **When** the user views the dialog **Then** an inline error names line 2, OK is disabled and nothing is saved.

### Scenario: invalid pattern in the TUI

**Given** the Ignore box contains `[oops` **When** the user views the modal **Then** a red error line shows under the box and OK is disabled.

### Scenario: invalid pattern on the CLI

**Given** `srxy q . --ignore '[oops'` **When** run **Then** it prints `srxy: error: --ignore '[oops': …` to stderr, exits 2 and searches nothing.

### Scenario: size caps

**Given** a list of 1,001 lines or a line over 1,024 characters **When** validated in the GUI, TUI or CLI **Then** the same inline error / exit code 2 applies.

### Scenario: remember filters persists the list

**Given** "Remember filters" ticked and rules plus the .gitignore checkbox set **When** the app restarts **Then** the rules and checkbox are restored (GUI and TUI).

### Scenario: not remembered when unticked

**Given** "Remember filters" unticked **When** the app restarts **Then** the ignore list is empty, while within the session it applied to every search.

### Scenario: old settings load

**Given** a 1.7 settings file without ignore keys **When** loaded **Then** the list is empty, `.gitignore` is off and other filters are intact.

### Scenario: invalid persisted list falls back

**Given** a hand-edited persisted ignore list that is invalid **When** loaded **Then** filters fall back to factory defaults and the app starts.

### Scenario: scan switches live in Filters, not in Search options

**Given** the Filters dialog/modal **When** it opens **Then** "Which files to scan" is its first section with the ignore list first, followed by subdirectories, archives, hidden, cache & vendor, junk & lock, skipped names and the binary hint; and the Search options dialog/modal no longer shows that section.

### Scenario: moved switches apply and cancel with Filters

**Given** the user toggles "Hidden files & folders" and edits the ignore list in Filters **When** they press Cancel **Then** neither changes; **When** they press OK **Then** both apply to the next search.

### Scenario: moved switches persist with Remember filters

**Given** "Hidden files & folders" is ticked and "Remember filters" is ticked **When** the app restarts **Then** the switch is restored; with "Remember filters" unticked it is not (even if "Persist options" is on), and the persisted options contain none of the six keys.

### Scenario: old settings migrate

**Given** a 1.7 settings file whose persisted `options` contain the six scan keys and no `scan` key **When** the app starts **Then** those values are used as the scan switches, and the next save writes them under `scan` (when Remember filters is on) and not under `options`.

### Scenario: reset clears the list

**Given** rules and the checkbox set **When** the user presses Reset in the Filters dialog **Then** the list is empty and the checkbox unticked.

### Scenario: ignore a file from a result row

**Given** a result row for `app/debug.log` **When** the user chooses "Ignore this file" **Then** `/app/debug.log` is appended, a toast with Undo / Edit list appears and the current results stay.

### Scenario: ignore folder or extension from a row

**Given** a result row **When** the user chooses "Ignore folder “logs/”" or "Ignore all “*.log” files" **Then** `/app/logs/` (anchored) or `*.log` is appended.

### Scenario: undo removes only the added rule

**Given** a rule was just added via the toast **When** the user chooses Undo **Then** only that line is removed and the persisted list updates.

### Scenario: duplicate rule is not added twice

**Given** the list already contains `*.log` **When** the user ignores `*.log` again **Then** the list is unchanged.

### Scenario: archive member rows

**Given** a result row inside an archive **When** the context menu opens **Then** only "Ignore archive" is offered (the archive's own path).

### Scenario: picking a folder inside the root

**Given** search root `~/work` **When** the user picks `~/work/src/old` via "Add folder…" **Then** `/src/old/` is appended.

### Scenario: picking a path outside the root is rejected

**Given** search root `~/work` **When** the user picks `~/other/x` **Then** a message explains it is outside the search root and nothing is added.

### Scenario: edit list from the toast

**Given** the toast is showing **When** the user chooses "Edit list" **Then** the Filters dialog opens scrolled to the Ignore section.

### Scenario: summary text

**Given** 3 patterns and "respect .gitignore" on **When** the filters summary renders **Then** it reads "ignoring 3 patterns (+.gitignore)" (GUI and TUI).

### Scenario: root is never ignored

**Given** the search root is a file or a folder whose name matches a rule **When** searching **Then** the root is still searched.

### Scenario: CLI json shape unchanged

**Given** `--ignore '*.log' --json` **When** run **Then** output is still a top-level JSON array of results.

## Out of scope

- `.gitignore` files above the search root, `.git/info/exclude` and `core.excludesFile`.
- Applying patterns to entries inside archives (only the archive's own path is matched).
- A file chooser in the TUI (typed patterns only).
- Showing counts of ignored files in results.
- Evicting content-cache entries for newly ignored paths.
- A case-sensitive/insensitive toggle (future idea; would also affect ignore matching).
- Ignore rules stored in the searched folder (e.g. a `.srxyignore` file).
