# Feature Specification: Per-Run Provider Selection

**Feature Branch**: `004-provider-selection`

**Created**: 2026-06-16

**Status**: Draft

**Input**: User description: "Let the user choose, per run, which failure data source (Athena or the already-persisted Postgres history) and which log backend the analysis uses, instead of it being fixed once at process start by environment variables. Add Postgres as a selectable data source, expose the available providers to the UI, and make the app's branding provider-neutral."

## User Scenarios & Testing *(mandatory)*

Today the data source (Athena vs. local file), the log backend (CloudWatch vs.
Grafana Loki), and the LLM are all fixed when the server starts, by environment
settings. An operator who wants to look at the failures the system already stored, or
who works across more than one logging stack, has to edit configuration and restart to
switch. Because every fetched failure is now persisted to the case history as soon as a
fetch runs, that stored history is itself a perfectly good data source — but there is
no way to point a run at it. This feature lets the user pick the data source and log
backend for an individual run from the screen, adds the stored history as a first-class
selectable source, and drops the AWS-specific tagline so the product reads as the
pluggable tool it actually is.

### User Story 1 - Choose the data source for a fetch (Priority: P1)

An operator opens the app and, next to the time-range controls, sees a **Source**
selector listing the data sources that are actually available — at minimum the
configured default and the stored history. They pick the stored history, run a fetch
for the last day, and get back the failures already recorded for that window without
touching any live external system. On another run they switch back to the default live
source and fetch fresh records. The selection applies only to that run; it does not
change any server-wide setting.

**Why this priority**: This is the core of the feature — turning a restart-only,
environment-pinned choice into a per-run, on-screen one, and unlocking the
already-persisted history as a usable source. It is independently shippable and
delivers value on its own.

**Independent Test**: With both the default source and the stored-history source
available, select the stored-history source, run a fetch over a window known to have
recorded failures, and confirm the results come from the stored history; then select
the default source and confirm a fetch returns live records — all without restarting or
editing environment configuration.

**Acceptance Scenarios**:

1. **Given** more than one data source is available, **When** the operator opens the
   fetch screen, **Then** a Source selector lists each available source and shows the
   configured default pre-selected.
2. **Given** the operator selects the stored-history source and runs a fetch for a
   window with recorded failures, **When** the fetch completes, **Then** the returned
   records come from the stored history for that window and that component filter.
3. **Given** the operator selects the default live source and runs a fetch, **When**
   the fetch completes, **Then** the returned records come from that live source, and
   the server-wide default is unchanged for the next user.

### User Story 2 - Choose the log backend for an analysis (Priority: P2)

When running an analysis, the operator can choose which log backend the run targets —
the configured default, or another available backend — so the generated log queries and
deep-links match the stack they actually use, for this run only. If they make no choice,
the configured default is used exactly as today.

**Why this priority**: Valuable for teams that span more than one logging stack, but the
feature is already useful with data-source selection alone (US1), and a per-run log
backend override already partially exists, so this ranks second.

**Independent Test**: With two log backends available, run an analysis selecting the
non-default backend and confirm the generated queries and deep-links target that
backend; run again with no selection and confirm the default backend is used.

**Acceptance Scenarios**:

1. **Given** more than one log backend is available, **When** the operator opens the
   analyze step, **Then** a Log Backend selector lists each available backend with the
   default pre-selected.
2. **Given** the operator selects a non-default log backend and runs an analysis,
   **When** it completes, **Then** the log queries and deep-links target the selected
   backend for that run only.
3. **Given** the operator makes no log-backend selection, **When** they run an
   analysis, **Then** the configured default backend is used, identical to today's
   behavior.

### User Story 3 - Discover what is available and a neutral identity (Priority: P3)

The screen populates its selectors from what the system reports as actually available,
rather than from a hardcoded list, so a source or backend that is not configured never
appears as a choice, and a newly configured one appears without a code change. The
header no longer advertises specific vendors; it presents the product as backed by
pluggable data, log, and AI providers.

**Why this priority**: Improves correctness and presentation and prevents users from
selecting something that cannot work, but the core selection value (US1/US2) stands
without it, so it ranks last.

**Independent Test**: Configure only one data source and confirm the Source selector
offers only that one (no non-functional options); configure a second and confirm it
appears with no code change; confirm the header shows the neutral, vendor-agnostic
tagline.

**Acceptance Scenarios**:

1. **Given** only one data source is configured, **When** the screen loads, **Then**
   the Source selector offers only that source and does not list unconfigured sources.
2. **Given** a second data source becomes configured, **When** the screen is reloaded,
   **Then** the new source appears as a selectable option without any code change.
3. **Given** the app has loaded, **When** the operator reads the header, **Then** it
   presents a provider-neutral identity rather than naming specific vendors.

### Edge Cases

- **Selected source unavailable at run time**: if the chosen source can no longer serve
  the request (e.g. credentials missing, store unreachable), the run fails with a clear
  message naming the source, rather than silently falling back to a different one.
- **Stored history empty for the window**: selecting the stored history for a window
  with no recorded failures returns an empty result set, not an error.
- **Only one provider available**: the selector still renders (showing the single
  option) and the run behaves exactly as the environment-pinned behavior does today.
- **Unknown / unsupported selection**: a request naming a source or backend the system
  does not offer is rejected with a clear message and changes nothing.
- **Concurrent users**: one user's per-run selection never changes another user's
  default or in-flight run.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST let the operator choose, per run, which available data
  source a fetch uses, defaulting to the configured default when no choice is made.
- **FR-002**: The system MUST let the operator choose, per run, which available log
  backend an analysis uses, defaulting to the configured default when no choice is made.
- **FR-003**: A per-run selection MUST affect only that run and MUST NOT change any
  server-wide default or any other user's run.
- **FR-004**: The system MUST offer the already-persisted failure history as a
  selectable data source, returning recorded failures filtered by the same time window
  and component filter used for a live fetch.
- **FR-005**: The system MUST expose the set of currently available data sources and log
  backends, together with which is the default for each, so the screen can populate its
  selectors from real availability rather than a hardcoded list.
- **FR-006**: The screen MUST list only sources and backends the system reports as
  available, and MUST reflect a newly configured provider without a code change.
- **FR-007**: When a selected source or backend cannot serve a run, the system MUST fail
  the run with a clear message identifying the selected provider, and MUST NOT silently
  substitute a different provider.
- **FR-008**: A request naming a source or backend that is not available MUST be
  rejected with a clear message and MUST change nothing.
- **FR-009**: The application header MUST present a provider-neutral identity and MUST
  NOT advertise specific named vendors.
- **FR-010**: All existing fetch and analyze behavior MUST remain unchanged when no
  per-run selection is supplied.

### Key Entities *(include if feature involves data)*

- **Provider Option**: A selectable provider the system can use for a run — its stable
  identifier, a human-readable label, the kind it serves (data source or log backend),
  and whether it is the current default. Reported to the screen; not persisted.
- **Failure History Source**: The recorded failures already stored by earlier fetches,
  presented as a data source. Queried by time window and optional component; returns the
  same shape of failure record a live fetch returns.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can switch the data source or log backend for a run entirely
  from the screen, with no server restart and no environment edit, in a single
  selection.
- **SC-002**: An operator can fetch from the stored failure history for any window and
  receive exactly the failures recorded for that window and component filter, with zero
  calls to a live external data source.
- **SC-003**: The screen never offers a source or backend that is not actually
  available, and a newly configured provider appears as an option with no code change.
- **SC-004**: When no per-run selection is made, fetch and analyze results are identical
  to the pre-feature behavior.
- **SC-005**: The header contains no vendor-specific product claim after this feature
  ships.

## Assumptions

- Earlier fetches already persist every fetched failure to the case history, so the
  stored-history source has data to serve without any new ingestion step.
- The default data source, log backend, and LLM continue to come from existing
  environment configuration; this feature adds per-run overrides layered on top of those
  defaults, not a replacement for them.
- Provider selection is global to the single configured project today; per-project
  provider selection is a separate, later concern and is out of scope here.
- The set of data sources in scope is the existing live source plus the stored history;
  the set of log backends in scope is the existing backends. Adding entirely new
  provider kinds is out of scope.
- Authentication/authorization for who may switch providers is out of scope; any
  operator using the screen may make a per-run selection.
