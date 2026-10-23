# <Feature name>

## Metadata

- **Feature:** <one or two sentences: what the user gets>
- **Wireframe:** [wireframes/<screen>.html](../../wireframes/<screen>.html). **Wireframe approved** <YYYY-MM-DD> (chat)
- **Design decisions approved:** <YYYY-MM-DD> (chat)
- **Spec approved:** <YYYY-MM-DD> (chat)
- **Related:** <links to other specs this one depends on or changes>

## Design decisions

### Success criteria

- <Observable outcome for the user, beyond the scenario list.>
- <Measurable threshold: no data loss, idempotent re-run, …>

### Failure handling

- <What can fail → what the user sees → retry / skip / quarantine.>
- <Partial state and how the user resumes.>

### Performance & resource budget

- <Latency / throughput target, CPU / memory / disk / network cost, size limits.> (or `N/A — <reason>`)

### Trust boundary

- <Untrusted input and where it is validated.>
- <What is trusted, and what may touch the filesystem or network.>

## Triggers & routing

- **Entry:** <screen, route, command or event that starts the flow>
- **Exit:** <where the user ends up on success, cancel and failure>

## Visual & UI rules

- <Layout, components, states and copy, matching the approved wireframe.>
- Wireframe-only notes ("Review only") do not ship.

## Acceptance criteria

### Scenario: <happy path>

**Given** <context> **When** <action> **Then** <observable result>.

### Scenario: <failure from Failure handling>

**Given** <context> **When** <it fails> **Then** <what the user sees and what state is left>.

### Scenario: <untrusted input from Trust boundary>

**Given** <hostile or malformed input> **When** <it reaches the inbound adapter> **Then** <it is rejected, nothing is touched>.

## Out of scope

- <Things a reader might expect but this feature will not do.>
