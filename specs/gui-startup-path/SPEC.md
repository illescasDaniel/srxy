# GUI initial search path

## Metadata

- **Feature:** Initialize the GUI search folder from the launch context and open ignore-list pickers at the current search root.
- **Wireframe:** [wireframes/gui-startup-path.html](../../wireframes/gui-startup-path.html). **Wireframe approved:** 2026-10-23 (chat).
- **Design decisions approved:** 2026-10-23 (chat), covering the four startup-path decisions. Picker additions approved with the spec on 2026-10-23 (chat).
- **Spec approved:** 2026-10-23 (chat).
- **Known fallback limitation accepted:** 2026-10-26 (chat), when Daniel requested commit/push after the remaining limitation was reported; see [scope amendment](QT-FALLBACK-DECISION.md).
- **Picker design:** Daniel explicitly waived an additional wireframe on 2026-10-23; layout and labels are unchanged.
- **Related:** [Ignore rules](../ignore-rules/SPEC.md), including the picker-start-directory amendment approved together on 2026-10-23 (chat).

## Design decisions

### Success criteria

- Ordinary terminal commands (`srxy`, `python -m srxy`, and development invocations that open the GUI) initialize **Where to search** to the caller's absolute current directory when no path is supplied. Installing srxy does not change terminal-command behavior.
- Installed app launches from Start menu, desktop shortcuts, application menus, Finder, and the installer's Launch action initialize to the user's home, regardless of their incidental working directory.
- Explicit search paths take precedence over default selection. Explicit `.` means the caller's current directory; relative paths retain their meaning against that directory, including paths with spaces or non-ASCII characters.
- GUI-specific app executables/bundles are app launches even if invoked from a shell; ordinary installed command shims remain command launches.
- Each Add file/Add folder click starts the ignore picker at the current **Where to search** directory, including after changing the root or previously navigating elsewhere in a picker. Detailed picker rules live in the ignore-rules amendment.
- Existing labels/layout, manual recent-search restoration, and query-triggered search behavior remain unchanged. A launch without a query does not start a search.

### Failure handling

- If the current directory cannot be determined for a command launch with no explicit path, fall back to home without starting a search.
- Preserve invalid explicit paths for existing GUI validation rather than replacing them with home. Do not add a startup directory-readability scan; access failures during search use existing handling.
- For pickers, an empty, missing, inaccessible or non-directory search root uses home as the requested starting location. The main path is not changed, and no ignore rule is added merely by opening or cancelling a picker. Native-dialog handling of an inaccessible home remains platform behavior; this change adds no directory creation or retry loop.
- Selecting outside the search root remains rejected by existing validation; starting at home as a fallback does not expand the allowed ignore scope.

### Performance & resource budget

- Startup default selection uses local path operations once per launch; no traversal, permission scan, network requests, worker processes or model imports are added.
- Each picker opening computes its start directory from the latest root with bounded local path checks. No recursive enumeration, background polling or content reads are added by srxy; normal native picker listing remains unchanged.
- No separate numerical latency target is needed for these local operations. Existing startup and search performance budgets still apply.

### Trust boundary

- Installed launchers explicitly communicate app-launch intent. TTY status, installation location and incidental cwd are not used to infer that intent. This is a behavior hint, not filesystem authorization.
- CLI arguments, edited paths and picker URLs are data. Forward arguments safely and convert native paths to local file URLs without interpreting path text as shell syntax or URL structure.
- Explicit arguments outrank app defaults. Picked paths continue through the existing root-relative validation, including rejection of paths resolving outside the root; picker navigation itself does not change the root or start a search.

## Triggers & routing

- **Command entry:** an ordinary srxy command enters the existing GUI routing, with caller cwd captured before a wrapper can replace it.
- **App entry:** generated Linux desktop entry, Windows GUI launcher/shortcuts, macOS app bundle or installer Launch action explicitly requests the home default.
- **Picker entry:** Filters → ignore list → Add file/Add folder uses the currently selected search root on every opening, as specified in [Ignore rules](../ignore-rules/SPEC.md).
- **Exit:** the normal editable GUI opens; browsing, typing, dropping folders, recent-search restoration, validation and Search continue through their existing flows. Defaulting applies at startup, not to later edits or restored paths.

## Visual & UI rules

- Match the approved startup wireframe's field values. No layout, control, label or theme changes.
- Picker directory changes require no additional wireframe, as explicitly requested by Daniel. Existing native picker appearance and inline validation remain.
- Review-only wireframe notes do not ship.

## Acceptance criteria

### Scenario: terminal launch starts at caller cwd

**Given** a shell in directory A **When** an ordinary srxy command opens the GUI without a path **Then** Where to search shows absolute A, including for an installed command shim.

### Scenario: app launch starts at home

**Given** an installed Start menu, desktop, application-menu, Finder or installer Launch entry with incidental working directory B **When** it opens without a path **Then** Where to search shows the user's home, even when B is the installation folder. Validate the generated launch routes on each supported platform.

### Scenario: explicit absolute path overrides defaults

**Given** either command or app launch with explicit absolute path C **When** the GUI initializes **Then** Where to search targets C rather than cwd or home.

### Scenario: explicit dot and relative paths retain caller meaning

**Given** a caller in A supplies `.` or a relative search path **When** the GUI initializes through either launch route **Then** the path targets A or the specified location relative to A, even if a wrapper changes its child process's working directory.

### Scenario: unavailable cwd falls back to home

**Given** a command launch with no path whose cwd cannot be obtained **When** the GUI initializes **Then** it opens at home without a startup crash or automatic search.

### Scenario: invalid explicit path is retained

**Given** a supplied search path is missing or invalid **When** the GUI initializes **Then** existing path validation explains the issue and the requested target is not silently replaced with home.

### Scenario: obtainable but unreadable cwd is not scanned during initialization

**Given** a command launch whose cwd can be obtained but cannot be listed **When** the GUI initializes without a path **Then** that directory remains selected and no new readability scan is performed; subsequent search access failures use existing handling.

### Scenario: terminal redirection does not choose the home default

**Given** an ordinary command with redirected streams that otherwise routes to the GUI **When** it initializes without a path **Then** its default is caller cwd, independently of TTY availability.

### Scenario: path characters remain data

**Given** an explicit path or search root contains spaces, non-ASCII text, `#`, or `%` **When** it passes through a launcher or is converted to a picker URL **Then** it still targets the same local location with no command execution or URL-fragment reinterpretation.

**Accepted exception:** srxy preserves native-path targets and correctly encodes picker URLs. Qt 6.11.1's non-native fallback can display incorrect contents for names containing `#` or literal `%20`; repairing or replacing that upstream backend is outside this patch. This exception does not permit changing the search root or selected paths, or relaxing outside-root rejection. Native Browse acceptance decodes its selected URL once and preserves literal percent names.

### Scenario: opening without a query does not search or restore

**Given** saved recent searches **When** the GUI opens without a query **Then** it shows the launch-context default, starts no search and restores no saved path until the user chooses restoration.

### Scenario: later edits are not overwritten by startup defaults

**Given** the GUI is open **When** the user types a path, browses, drops a folder or restores a recent search **Then** that path remains the selected target and startup default selection is not reapplied.

### Scenario: ignore pickers follow the current root

**Given** a selected search directory **When** Add file or Add folder opens **Then** the picker behavior satisfies the current-root, reopening, cancellation, fallback and containment scenarios in the [Ignore rules amendment](../ignore-rules/SPEC.md).

## Out of scope

- Changing CLI/TUI search defaults, GUI routing or query-triggered auto-search.
- Automatic last-session restoration or a new persistent default-directory setting.
- Redesigning Browse, Filters, ignore matching or picker controls.
- Restricting native picker navigation: the existing acceptance-time containment check remains the protection against adding outside-root ignore entries.
- Rewriting already-installed shortcuts automatically; changed launcher generation applies to new installs/reinstalls or updates that regenerate those artifacts.
