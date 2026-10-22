# Ignore rules: architecture and plan (approved 2026-10-21)

Source of truth for behaviour: [SPEC.md](SPEC.md). This file holds the approved interfaces and the Phase 3-4 plan.
Conventions (AGENTS.md): tab indentation, no `-> None` annotations, i18n via `srxy.i18n.tr` (EN + ES in `src/srxy/i18n/`),
quality gate `uv run task checks -- --quiet [--scope=...]`.

## Summary

- Matcher is pure domain code (`domain/ignore_rules.py`), no `re` on user input, linear time, case-folded (NFC + casefold) on all OSs.
- Walker adapter owns `.gitignore` I/O and prunes ignored folders during `os.walk` (filter BEFORE the `include_directories` yield and before archive-member expansion; independent of `match_skipped_names`). The root path is never tested.
- Search args carry only JSON-safe strings (`args.ignore: list[str]`, `args.respect_gitignore: bool`), so worker `args_to_payload` needs no change.
- `SearchFilters` keeps its all-strings convention: `ignore_patterns` is one newline-joined `str`; `respect_gitignore` is a `bool` with explicit handling in `settings._filters_from_raw`.
- Symlink to a folder counts as a folder (`link/` matches it); symlink to a file / broken link counts as a file. Deliberate difference from git.

## Interfaces

### `src/srxy/domain/exceptions.py` (append)

```python
class IgnoreReason(StrEnum):
	UNCLOSED_BRACKET = "unclosed_bracket"
	TRAILING_BACKSLASH = "trailing_backslash"
	LINE_TOO_LONG = "line_too_long"
	TOO_MANY_LINES = "too_many_lines"
	MULTILINE = "multiline"  # one CLI --ignore value containing a newline


class IgnorePatternError(ValueError):
	def __init__(self, *, line_number: int, pattern: str, reason: IgnoreReason):
		...  # line_number is 1-based in the raw text, counting blanks and comments
```

### `src/srxy/domain/ignore_rules.py` (new, pure, no I/O)

```python
MAX_USER_LINES = 1000
MAX_LINE_CHARS = 1024
MAX_GITIGNORE_BYTES = 1 << 20
MAX_GITIGNORE_LINES = 10_000

@dataclass(frozen=True, slots=True)
class IgnoreSpec:
	"""JSON-safe ignore config for one search, built from args."""
	patterns: tuple[str, ...] = ()
	respect_gitignore: bool = False

	@property
	def active(self) -> bool: ...

@dataclass(frozen=True, slots=True)
class IgnorePattern:
	raw: str
	line_number: int
	negated: bool
	dir_only: bool
	anchored: bool  # has a '/' that is not the trailing one
	segments: tuple[_Segment, ...]  # compiled, NFC + casefold; '**' is a sentinel

	def matches(self, rel_parts: tuple[str, ...], is_dir: bool) -> bool: ...

@dataclass(frozen=True, slots=True)
class IgnoreRuleSet:
	base: tuple[str, ...]  # dir parts it applies from; () = root / user list
	patterns: tuple[IgnorePattern, ...]

	def decide(self, rel_parts: tuple[str, ...], is_dir: bool) -> bool | None:
		"""Last match wins: True = ignore, False = re-included, None = no opinion."""

def normalize_part(name: str) -> str: ...  # NFC + casefold, used everywhere

def parse_ignore_lines(lines: Sequence[str], *, strict: bool, base: tuple[str, ...] = ()) -> IgnoreRuleSet:
	"""strict=True (user list): caps enforced, raises IgnorePatternError on the first bad line.
	strict=False (.gitignore): skips bad lines, truncates at MAX_GITIGNORE_LINES."""

def count_effective_patterns(lines: Sequence[str]) -> int: ...  # excludes blanks and comments

def escape_literal(name: str) -> str: ...  # backslash-escapes * ? [ \ and a leading # or !, plus trailing spaces

class IgnoreMatcher:
	"""User rules plus a stack of .gitignore rule sets (immutable)."""

	def __init__(self, user: IgnoreRuleSet, stack: tuple[IgnoreRuleSet, ...] = (), *, git_dir: bool = False): ...

	@classmethod
	def from_spec(cls, spec: IgnoreSpec) -> IgnoreMatcher: ...  # strict parse; raises IgnorePatternError

	def with_gitignore(self, rules: IgnoreRuleSet) -> IgnoreMatcher: ...

	def is_ignored(self, rel_parts: tuple[str, ...], is_dir: bool) -> bool:
		"""Order: git_dir check ('.git' dir -> True), then user.decide, then the stack deepest first
		(each sees rel_parts[len(base):]), then False. Only correct when called top-down."""
```

Matching: each segment tokenised into literal chunks, `?`, `[...]` classes, `*`; matched with the two-pointer wildcard
algorithm (O(n*m), no `re`); `**` via memoised DP over (pattern segment, path segment); fast paths for exact literal and
`*.ext`; unanchored patterns test only `rel_parts[-1]`.

### Ports / adapters / use cases

- `src/srxy/ports/outbound/content.py`: `iter_files` and `collect_files` gain `ignore: IgnoreSpec | None = None`.
- `src/srxy/adapters/outbound/content/file_walker.py`: if `ignore` is None or not `active`, skip the whole code path. Else keep
  `matchers: dict[str, tuple[IgnoreMatcher, tuple[str, ...]]]` keyed by dirpath. Per directory: if `respect_gitignore`,
  `_read_gitignore(dirpath) -> list[str] | None` (lstat; skip symlinks and non-regular files; read at most
  `MAX_GITIGNORE_BYTES`; decode utf-8 `errors="replace"`; None on OSError), then `with_gitignore(parse(..., strict=False, base=rel))`.
  Filter `dirnames` through `is_ignored(rel + (n,), True)` (symlink-to-folder entries in `dirnames` count as dirs) and files
  through `is_ignored(..., False)`. `git_dir=spec.respect_gitignore`.
- `src/srxy/application/use_cases/search_files.py`: `_execute_file_search`, `FileSearchUseCase.search`, `magic_file_search`
  gain `ignore: IgnoreSpec | None = None`, passed to BOTH walker calls (file-count probe and listing walk).
- `src/srxy/application/search_runner.py` (~line 105): pass `ignore=ignore_spec_from_args(args)`.

### `src/srxy/application/search_filters.py`

```python
@dataclass(frozen=True, slots=True)
class SearchFilters:
	...  # existing fields
	ignore_patterns: str = ""  # raw textarea text, lines joined by "\n"
	respect_gitignore: bool = False

def ignore_lines(filters: SearchFilters) -> list[str]: ...  # splitlines(), kept raw
def ignore_spec_from_args(args: argparse.Namespace) -> IgnoreSpec | None: ...  # getattr defaults [] / False
def format_ignore_error(error: IgnorePatternError) -> str: ...  # tr("filters.ignore.error_line", ...)
def validate_ignore_text(text: str) -> str: ...  # "" if OK, else the localised message
```

Changes: `validate_search_filters` strict-parses and re-raises `ValueError(format_ignore_error(e))`;
`apply_search_filters_to_args` sets `args.ignore = ignore_lines(f)` and `args.respect_gitignore`;
`search_filters_from_args` sets `ignore_patterns="\n".join(args.ignore or [])`; `default_search_filters` empty/False;
`format_search_filters_summary` appends `filters.summary.ignoring` (n) and `filters.summary.gitignore` when they apply.

### `src/srxy/application/settings.py`

- `_filters_from_raw`: take `respect_gitignore` out of the `str()` coercion (`str(False) == "False"`). Missing -> False;
  non-bool -> return None (factory fallback); missing `ignore_patterns` -> `""`.
- Add `save_persisted_filters(*, persist_filters: bool, filters: SearchFilters | None) -> bool`, touching only
  `persist_filters` / `filters` (so the TUI cannot clobber the GUI's `persist_options`).

### `src/srxy/application/ignore_edit.py` (new, Qt-free)

```python
class PathOutsideRootError(ValueError): ...

@dataclass(frozen=True, slots=True)
class IgnoreChoice:
	kind: str  # "file" | "folder" | "ext" | "this_folder" | "archive"
	pattern: str
	display: str  # name/ext shown in the label

def pattern_for_path(path: Path, root: Path, *, is_dir: bool) -> str:
	"""resolve() both; outside -> PathOutsideRootError; '/a/b' or '/a/b/', parts escaped."""

def row_ignore_choices(path: Path, root: Path, *, is_dir: bool, archive_path: Path | None) -> list[IgnoreChoice]: ...
# archive member -> only [archive]; dir result -> [this_folder];
# file -> file, plus folder when parent != root, plus ext when it has a suffix

def add_ignore_line(text: str, pattern: str) -> tuple[str, bool]: ...  # (new_text, added); duplicates are a no-op
def remove_ignore_line(text: str, pattern: str) -> str: ...  # removes the last exact occurrence only
```

### CLI (`src/srxy/adapters/inbound/cli/cli.py`)

`--ignore PATTERN` (`action="append"`, `dest="ignore"`, `default=None`), `--respect-gitignore` (`store_true`). In `main`
right after `parse_args`, before GUI/TUI/CLI dispatch: per value `parse_ignore_lines([v], strict=True)`; a value containing
`"\n"` -> `MULTILINE`; over 1,000 values -> `TOO_MANY_LINES`; on error `parser.error(f"--ignore {v!r}: {reason_text}")`
(exit 2). `--json` writer untouched.

### GUI (`adapters/inbound/gui/controller.py`, `qml/Main.qml`)

- `filtersJson` / `defaultFiltersJson` gain `ignore_patterns`, `respect_gitignore` (via `asdict`); `_parse_filters_payload` accepts them.
- New slots: `validateIgnorePatterns(str) -> str`; `ignorePatternForPick(url: str, is_dir: bool, current_text: str) -> str`
  (JSON `{"text": ...}` or `{"error": ...}`, root = current `self._path`); `resultIgnoreChoicesJson(row: int) -> str`
  (`[{kind, pattern, label}]`, root = `self._results_root`); `addIgnoreRule(pattern: str) -> str` (commit to `self._filters`,
  persist, emit `filtersSummaryChanged`, JSON `{added, toast}`); `undoLastIgnoreRule()` (removes only `self._last_added_ignore`).
- State: `self._results_root: Path | None` snapshotted in `startSearch`; `self._last_added_ignore: str | None`.
- QML: Ignore section in `filtersDialog` (`fltIgnore` TextArea, `fltRespectGitignore`, Add file... / Add folder..., inline error label);
  draft functions carry both keys; OK disabled while `validateIgnorePatterns` is non-empty; `resultContextMenu` gets a
  `Repeater` over `resultIgnoreChoicesJson`; new toast (Undo / Edit list; "Edit list" opens the dialog scrolled to the section).
  Primary buttons use `AccentButton`.

### TUI (`adapters/inbound/tui/modals.py`, `app.py`)

`SearchFiltersModal`: `TextArea(id="sf-ignore")`, `Label(id="sf-ignore-error")`, `Checkbox(id="sf-respect-gitignore")`,
`Checkbox(id="sf-persist")`; on `TextArea.Changed` validate and disable `#search-filters-apply`; returns
`FiltersModalResult(filters: SearchFilters, persist: bool) | None`. `app.py`: load persisted prefs in `__init__` like the GUI
(`controller.py` ~510-519); `action_open_search_filters` saves with `save_persisted_filters`.

### i18n (EN + ES)

`filters.ignore.{section,info,hint,placeholder,add_file,add_folder,respect_gitignore,error_line,pick_outside_root}`,
`ignore.reason.{unclosed_bracket,trailing_backslash,line_too_long,too_many_lines,multiline}`,
`filters.summary.{ignoring,gitignore}`, `gui.menu.{ignore_file,ignore_folder,ignore_ext,ignore_this_folder,ignore_archive}`,
`gui.toast.{ignoring,undo,edit_list}`, `tui.filters.{ignore_label,persist}`.

## Phase 3: tests (seven independent groups, one coder each, files do not overlap)

Names follow `test_given_..._when_..._then_...` with `# given` / `# when` / `# then`; each maps to a SPEC scenario title.

- **T1** `tests/unit/test_ignore_rules.py` (+ `tests/unit/test_ignore_rules_git_parity.py`, differential vs `git check-ignore --no-index`, skipped without git; exclude the symlink scenarios): bare name, leading slash, trailing slash, glob and re-include, double-star, comments/blank, case-insensitive, pathological pattern (`**********b` vs 255-char name < 50 ms), traversal-looking pattern, size caps (domain).
- **T2** `tests/unit/test_file_walker_ignore.py`: cannot re-include under excluded folder, beats include-hidden, beats include-noise/match-skipped-names, respect .gitignore nested, .gitignore off, user overrides .gitignore, `.git` always ignored, symlinked `.gitignore` (skip on Windows), malformed/oversized, unreadable (chmod; skip on Windows), symlink to folder counts as folder, symlink to file/broken counts as file, root never ignored, folder results (`include_directories`), archive file ignored.
- **T3** `tests/unit/test_search_filters_ignore.py`, `tests/unit/test_ignore_edit.py`, new cases in `tests/unit/test_settings_persist.py`: remember filters, not remembered when unticked, old settings load, invalid persisted list falls back, summary text, pick inside root, pick outside root rejected, duplicate not added twice, undo removes only added rule, archive member rows, escaping of `[`/`*` in picked names, TUI save does not clobber options.
- **T4** `tests/unit/test_search_ignore_flow.py`: totals and workers see only non-ignored paths (progress total, spy extractor never called for ignored paths, `args_to_payload` -> json -> Namespace round trip reproduces the same `IgnoreSpec`).
- **T5** `tests/cli/` (extend `test_cli.py` or add a new file): invalid pattern exit 2, size caps, `--json` shape unchanged, repeatable `--ignore`.
- **T6** `tests/tui/test_search_filters_modal.py`: invalid pattern, remember filters, summary text; new/refreshed snapshots (`UPDATE_TUI_SNAPSHOTS=1`).
- **T7** `tests/gui/test_gui_controller.py`, `tests/gui/test_gui_snapshots.py` (`UPDATE_GUI_SNAPSHOTS=1`), `tests/gui/test_gui_flows.py`: invalid pattern validate slots, reset clears list, ignore file/folder/extension from a row, undo, duplicate, archive rows, pick outside root, QML-load test for toast / Edit list.

## Phase 4: implementation (after tests exist and fail for the right reason)

1. Domain: `domain/exceptions.py`, `domain/ignore_rules.py` (T1 passes).
2. Parallel A: **2a** ports + `file_walker.py` + `search_files.py` + `search_runner.py` (T2, T4); **2b** `search_filters.py`, `settings.py`, `ignore_edit.py`, all i18n keys (T3, `tests/unit/test_i18n_catalog.py`).
3. Parallel B: **3a** `cli.py` (T5); **3b** TUI modals/app + snapshots (T6); **3c** GUI controller + Main.qml + snapshots (T7).
4. `utility`: `uv run task checks -- --quiet --all`; one-off benchmark of walk overhead (100k-entry temp tree, 100 patterns, <= 15%).
5. Phase 5: `code-grader` against SPEC.md.

## Known risks

- `is_ignored` is correct only when called top-down (parents first); do not reuse it for one-off path checks.
- Picked names containing glob characters must go through `escape_literal`.
- Adding a rule from a result row marks current results stale (`_refresh_stale` compares `asdict(filters)`); results stay on screen.
- Persisted filters override command-line filters at GUI/TUI startup (existing rule for all filters).
- `parser.error` prints the usage line before the error message.
