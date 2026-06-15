# Feature Specification: Auto-Link RCA Cases to GitHub Pull Requests

**Feature Branch**: `002-auto-link-rca-pr`

**Created**: 2026-06-15

**Status**: Draft

**Input**: User description: "Auto-link RCA cases to GitHub PRs"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See a related pull request on the RCA report (Priority: P1)

After running an analysis, an engineer reviewing a failure group wants to know
whether someone is already fixing this issue. Instead of manually searching
GitHub for a relevant branch or pull request, the engineer sees a "Related
Pull Request" reference directly next to the failure group, showing its title,
author, status, and a link to open it.

**Why this priority**: This is the core value of the feature — turning a
manual "go check GitHub" step into an automatic surfaced reference, directly
on the report the engineer is already reading.

**Independent Test**: Can be fully tested by running an analysis for a
component/error that has a known matching open pull request (e.g. matching
branch name or PR title containing the component/error) and verifying the
resulting failure group includes a reference to that pull request with a
working link — delivers value by eliminating a manual GitHub search.

**Acceptance Scenarios**:

1. **Given** an analysis produces a failure group for a component/error that
   has a pull request whose branch name, title, or description references that
   component or error, **When** the analysis completes, **Then** the failure
   group includes a reference to that pull request (title, author, status,
   link).
2. **Given** an analysis produces a failure group with no matching pull
   request found in the configured repository, **When** the analysis
   completes, **Then** the failure group is still returned, simply without a
   related-pull-request reference.
3. **Given** no code repository is configured, **When** an analysis completes,
   **Then** the report is produced exactly as today, with no related-pull-request
   references anywhere.

---

### User Story 2 - Know whether the related fix has already shipped (Priority: P2)

An engineer looking at a recurring incident wants to know, at a glance,
whether a fix for this exact issue was already proposed or merged previously —
so they don't duplicate work or escalate something that's already resolved.

**Why this priority**: Builds directly on User Story 1 by adding the status
information needed to act on the related pull request, but the tool is still
useful with just a reference and no status context.

**Independent Test**: Can be fully tested by linking a pull request to a case,
changing that pull request's state (open → merged or closed), and verifying
the case's related-pull-request status reflects the change on the next
analysis or view — delivers value by letting users distinguish "fix in
progress" from "fix already shipped" without leaving the tool.

**Acceptance Scenarios**:

1. **Given** a failure group has a related pull request that is still open,
   **When** the user views the report, **Then** the related-pull-request
   reference indicates the "open" status.
2. **Given** a failure group has a related pull request that has been merged,
   **When** the user views the report, **Then** the related-pull-request
   reference indicates the "merged" status, signaling a fix has likely already
   shipped.
3. **Given** a failure group has a related pull request that was closed without
   merging, **When** the user views the report, **Then** the related-pull-request
   reference indicates the "closed" status.

---

### User Story 3 - Persist the link for recurring cases (Priority: P3)

When the same underlying issue recurs and is linked to an existing RCA case,
an engineer wants the previously identified related pull request to remain
visible on that case — even if a new analysis run doesn't find an even better
match — so the case's history shows what was already proposed as a fix.

**Why this priority**: This extends the recurring-issue tracking from the
baseline RCA tool with pull-request context, but is valuable on top of (not a
prerequisite for) User Stories 1 and 2.

**Independent Test**: Can be fully tested by linking a pull request to a case
on one analysis run, then running a second analysis that produces a failure
group matching the same case but does not find a new candidate pull request,
and verifying the previously linked pull request is still shown on the case —
delivers value by retaining useful context across recurrences without manual
record-keeping.

**Acceptance Scenarios**:

1. **Given** an RCA case already has a related pull request linked from a
   previous analysis, **When** a new analysis links another failure group to
   the same case without finding a new candidate pull request, **Then** the
   previously linked pull request reference remains visible on the case.
2. **Given** an RCA case already has a related pull request linked, **When** a
   new analysis finds a different, more relevant pull request for the same
   case, **Then** the case's related-pull-request reference is updated to the
   new match.

---

### Edge Cases

- What happens when multiple pull requests appear equally relevant to a
  failure group? The system should surface the single best match based on
  relevance signals (e.g. most recent activity, closest text match to
  component/error) rather than presenting an ambiguous or empty result.
- How does the system handle a pull-request search that fails (e.g. repository
  unreachable, rate-limited)? The analysis MUST still complete and return all
  other results; the related-pull-request reference is simply omitted for the
  affected failure group(s).
- What happens if the previously linked pull request for a recurring case has
  since been deleted or is otherwise inaccessible? The case should not display
  a broken reference as if it were still valid; the link should be dropped or
  clearly marked unavailable.
- What happens when a failure group's component/error text appears in many
  unrelated pull requests (false positives)? The system should prefer matches
  with stronger signals (e.g. branch name or PR title containing the exact
  component name or error code) over weak/incidental text matches, and is not
  required to guarantee a match is correct — see Assumptions.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST, as part of producing an analysis, search the
  configured code repository for pull requests potentially related to each
  failure group's component and error.
- **FR-002**: System MUST consider a pull request's branch name, title, and
  description when determining whether it relates to a failure group's
  component name or error code.
- **FR-003**: System MUST select at most one related pull request per failure
  group, preferring the strongest match when multiple candidates exist.
- **FR-004**: System MUST include, for each failure group with a related pull
  request, the pull request's title, author, status (open, merged, or closed),
  and a link to open it.
- **FR-005**: System MUST return the analysis successfully, with all other
  results intact, even when the pull request search fails, times out, or finds
  no match — in which case the related-pull-request reference is simply absent
  for the affected failure group(s).
- **FR-006**: System MUST NOT attempt pull-request matching when no code
  repository is configured, and MUST NOT alter any other part of the analysis
  output in that case.
- **FR-007**: System MUST persist the related pull request reference on the RCA
  case it is linked to, so it remains visible on later views of that case
  without re-running an analysis.
- **FR-008**: System MUST update a case's persisted related-pull-request
  reference when a later analysis finds a stronger match for the same case, and
  MUST retain the existing reference when a later analysis finds no candidate.
- **FR-009**: System MUST record, in the case's activity history, when a
  related pull request is newly linked or changed.
- **FR-010**: System MUST NOT display a previously linked pull request
  reference if it can no longer be retrieved from the code repository (e.g.
  deleted), and MUST instead omit it.

### Key Entities

- **Linked Pull Request**: A reference to a GitHub pull request associated
  with a failure group/RCA case, including its number, title, author, status
  (open, merged, closed), branch name, and URL.
- **Failure Group** *(existing, from baseline)*: A cluster of failure records
  sharing a root cause; gains an optional Linked Pull Request reference.
- **RCA Case** *(existing, from baseline)*: A persistent record tracking a
  root-cause signature over time; gains a persisted Linked Pull Request
  reference and related activity-history entries.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For failure groups with an obviously related pull request
  (matching component name or error code in the branch name or title), the
  tool surfaces that pull request without the user performing a manual GitHub
  search.
- **SC-002**: 100% of analyses complete successfully and return their full
  results even when the pull-request search fails or the repository is
  unreachable.
- **SC-003**: 100% of RCA cases with a linked pull request continue to display
  that reference (or a "no longer available" omission) on subsequent views
  without requiring a new analysis run.
- **SC-004**: Engineers can determine whether a fix for a recurring incident
  has already shipped (merged), is in progress (open), or was abandoned
  (closed) directly from the RCA report, without leaving the tool.

## Assumptions

- This feature reuses the existing code-repository configuration
  (`GITHUB_REPO`/`GITHUB_TOKEN`/GitHub MCP integration) from the baseline RCA
  tool; no new repository configuration concepts are introduced.
- Pull-request matching is heuristic (based on branch name, title, and
  description text matching component name / error code). It is a best-effort
  aid, not a guaranteed-correct link — users are expected to verify the
  suggested pull request before relying on it.
- Only the single configured repository is searched; cross-repository search
  is out of scope.
- "Related pull request" includes pull requests in any state (open, merged, or
  closed); closed-without-merge PRs are still useful context (e.g. an
  abandoned fix attempt).
- This feature extends the existing "Related Code Changes" surfaced by the
  baseline tool (see `specs/001-ai-rca-tool`) rather than replacing it.
