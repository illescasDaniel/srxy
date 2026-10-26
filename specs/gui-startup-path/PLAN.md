# GUI startup path: architecture and implementation plan

Architecture approval: **2026-10-23 (chat)**. Behavioral source of truth: approved [SPEC.md](SPEC.md) and the approved picker amendment in [Ignore rules](../ignore-rules/SPEC.md).

## Design

- Add a small pure application function for startup path selection. No new domain entity, persistent setting, dependency or filesystem port is needed.
- Generated app entrypoints pass hidden `--app-launch`; ordinary command shims do not. An argument avoids an environment marker leaking into child command invocations. The flag chooses the default only; existing GUI/TUI/CLI routing stays unchanged.
- Preserve omitted versus explicit paths until GUI initialization. Internally the parser uses `None` for an omitted positional path; restore `.` before non-GUI dispatch so CLI/TUI retain their existing behavior. Explicit empty text remains explicit.
- Windows GUI launcher inherits the caller's cwd instead of setting the child cwd to the install prefix. Interpreter, vendor and log paths are already absolute. This preserves explicit relative paths without a second cwd transport argument.
- Startup selection runs only when initializing the controller. Later edits, searches, ignore picks and restored sessions use the actual selected path, without reapplying launch defaults.
- Both ignore dialogs request a fresh start URL immediately before every `.open()`. Retain existing acceptance handlers and outside-root validation.

## Interface declarations

As in the existing ignore-rules plan, declarations are documented here for review. No unused production stubs are introduced before architecture approval.

### Application startup policy

New module: `src/srxy/application/gui_startup.py`.

```python
def initial_gui_search_path(
	raw: str | None,
	*,
	app_launch: bool,
	cwd: str | None,
	home: str,
) -> str: ...
```

Contract:

- Omitted (`raw is None`): app launch returns home; command launch returns cwd, falling back to home when cwd is unavailable.
- Explicit absolute input retains its target. Explicit dot/relative input is anchored to captured caller cwd without existence checks or symlink resolution.
- Invalid explicit input remains available to existing validation; empty explicit text stays empty. If cwd is unavailable for explicit relative input, preserve it rather than interpreting it relative to home.
- Keep existing home-expansion semantics. Native path text is not URL-parsed or percent-decoded.
- Function receives cwd/home as values: no filesystem, environment, network or Qt calls. The GUI adapter captures cwd once and handles `OSError`.

### Parser and dispatch boundaries

```text
GUI:     args.path: str | None; args.app_launch: bool
CLI/TUI: args.path: str         # omitted restored to "."
```

Add `--app-launch` with `store_true`, default false and suppressed help. Keep `run_gui(args, *, auto_start=False)` unchanged. Audit parser consumers and direct controller constructors for internal-default assumptions.

### Picker operation

New Qt adapter slot on `SearchController`:

```python
@Slot(result=QUrl)
def ignorePickerFolderUrl(self) -> QUrl: ...
```

Contract:

- Read the current `self._path` on each invocation.
- Use bounded local directory/access checks; expand paths according to existing semantics and catch filesystem/path errors.
- Return `QUrl.fromLocalFile` for the valid accessible directory; otherwise return home's local file URL, including when the root names a file.
- Do not enumerate directories, create paths, poll or mutate the main root, ignore draft or search state. Native handling of an inaccessible home remains unchanged.
- The chosen starting folder is not the validation root. `ignorePatternForPick` continues validating against the live main root; outside-root and escaping-symlink picks remain rejected.

QML assigns `currentFolder = controller.ignorePickerFolderUrl()` immediately before opening either dialog. Add stable dialog object names for testing; do not rely on a binding that native navigation may replace.

Implementation note: Qt 6.11's FolderDialog applies its requested initial directory only on the first show of its helper. Create a fresh folder dialog per opening, assign the live-root URL, and dispose of it after closing. The file dialog can remain reusable. Preserve acceptance/cancellation behavior and avoid leaking dialog instances. This is an adapter workaround for the approved repeated-opening behavior, not a new user flow.

## Launcher integration

| Route | App marker | Working directory / argument transport |
|---|---|---|
| Ordinary `srxy`, Unix wrapper, Windows `srxy.cmd`, module/development command | No | Preserve command cwd and arguments. |
| Linux generated desktop entry | Yes | Desktop-entry quoting for executable paths; incidental cwd does not affect omitted path. |
| Windows GUI `Srxy.exe` | Yes, both pythonw and console-script fallback | Inherit caller cwd; preserve argument boundaries with correct Windows escaping, including quoted trailing backslashes. |
| macOS app executable | Yes | Forward original argv, adjusting argv allocation for the added marker. |
| Installer Launch | Yes through app entrypoint or explicitly on command fallback | Existing detached process behavior retained; LaunchServices uses the marked app bundle. |

Marker placement must preserve user positional arguments and explicit `--` handling. Existing installed artifacts change only when regenerated, as specified.

Implementation note: GLib checks the desktop entry's executable before expanding literal `%%`. For an installation path containing `%`, use the existing OS `/usr/bin/env` executable with the quoted srxy path as its argument; ordinary paths execute srxy directly. Real Gio launch probes cover both routes and reserved path characters. This changes argument transport only.

## Phase 3: tests first

All Python test additions belong to `coder-python`. Run targeted tests and confirm failures exercise the new behavior before implementation.

| Spec scenarios | Test ownership / coverage |
|---|---|
| Terminal/app defaults; explicit absolute/dot/relative/empty/invalid inputs | New `tests/unit/test_gui_startup.py`: pure policy matrix. |
| Unavailable cwd and obtainable unreadable cwd | Pure-policy and controller tests; mock cwd errors and assert no startup directory enumeration/readability probe. |
| Redirected streams; unchanged CLI/TUI defaults; no-query/query behavior | New `tests/cli/test_cli_startup_path.py`, existing `tests/unit/test_launch.py`: mock dispatch, inspect namespace and auto-start. |
| Later edits/browse/drop/recent restoration retained | Existing `tests/gui/test_gui_controller.py`, `tests/gui/test_gui_flows.py`; replace old explicit-dot-means-home expectation. Verify search synchronization preserves selected root. |
| App entrypoints and explicit path argument transport | New `tests/unit/test_startup_launchers.py`, existing `tests/unit/test_macos_app_launcher.py` and `tests/gui/test_installer.py`: generated entries, fallback routes, native launch probes where available. |
| Both pickers use current root and reset on reopening | Existing `tests/gui/test_gui_ignore.py`: actual QML clicks, stable dialog object names, deterministic non-native dialogs; exercise changed root via typing/Browse/drop/restore. |
| Empty/missing/inaccessible/file root fallback; cancellation | Picker slot and real-QML tests: home requested without mutating root/draft or starting search. |
| Special path characters; outside-root and symlink containment | Launcher argument and picker URL round trips; existing acceptance checks and ignore-pattern semantics retained. |

Maintain a scenario-to-test checklist for all 12 startup scenarios and six added picker scenarios. Native executable probes are required on their supported hosts; source-text assertions alone do not prove argument transport.

## Phase 4: implementation ownership

1. **coder-python — policy and GUI boundary:** `application/gui_startup.py`, `adapters/inbound/cli/cli.py`, `adapters/inbound/gui/controller.py`. Implement the pure helper, omission handling, marker parser, initialization and picker slot. Remove startup defaulting from later search/ignore paths; handle all current `resolve_gui_search_path` callers.
2. **coder-python — installer generation:** `adapters/inbound/installer/install.py`, `adapters/inbound/installer/launch_app.py`. Add explicit app intent to desktop and installer launch routes; leave command shims with command semantics. Coordinate sequentially with step 1 through the documented marker contract.
3. **coder — native launchers:** `resources/windows/SrxyLauncher.cs`, `resources/macos/SrxyAppLauncher.c`. Add marker, preserve caller cwd and safe argv transport. May run alongside steps 1–2 because files do not overlap.
4. **coder — QML:** `adapters/inbound/gui/qml/Main.qml`. Set start folder on each click, add dialog object names. No label/layout/acceptance changes. May run alongside steps 1–3 against the declared slot contract.
5. **Orchestrator:** documentation and memory, reviewing diffs and all approvals. All workers must preserve other agents' edits.

## Verification and grade

- Run focused startup, dispatch, installer and real-QML picker tests, plus GUI startup/import and snapshot regressions. Refresh snapshots only for an intentional visible change; none is expected.
- **utility** runs the required full gate outside the sandbox, serialized:

```text
uv run task checks -- --quiet --fix --all
uv run task checks -- --quiet --all
```

- Fix failures and repeat both commands until clean. No Taskipy command changes are planned.
- Validate generated native launchers on Windows/macOS where available; explicitly report any unavailable platform checks.
- After green gates, independent **code-grader** reviews both approved specs against the task's starting HEAD and changes. Fix FAILs within the SDD limit and show the scorecard.

## Risks and boundaries

- Internal parser consumers may expect `.` immediately; audit them while preserving observable CLI/TUI behavior.
- Windows argument quoting needs correct handling of backslashes before quotes. Preserve path characters as data throughout all launch routes.
- Picker access checks are advisory; filesystem access can change after the URL is returned. Do not add traversal to prove access.
- Scope includes no search-root persistence schema, matching change, TUI UI change or new binary dependency.
