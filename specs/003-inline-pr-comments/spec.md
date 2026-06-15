# Feature Specification: Inline PR Review Comments

**Feature Branch**: `003-inline-pr-comments`

**Created**: 2026-06-15

**Status**: Draft

**Input**: User description: "Inline PR review comments — extend the AI Code Review feature so that, instead of only displaying findings in the UI, the agent can post the findings as review comments directly on the pull request, anchored to the relevant file/line."

## User Scenarios & Testing *(mandatory)*

The AI Code Review feature already analyzes a pull request and produces a list of
findings — each with a severity, category, title, description, suggested fix, and
(where the model could locate it) a file and line number. Today those findings are
only shown inside the app, so an engineer who wants the feedback on the actual pull
request must copy each finding across by hand. This feature lets the reviewer push
the findings back onto the pull request as a single native review, with each
locatable finding shown as an inline comment on the relevant line.

### User Story 1 - Post AI findings onto the pull request (Priority: P1)

A reviewer has just run the AI code review on a pull request and is looking at the
findings in the app. They decide the feedback is worth sharing on the PR, so they
trigger a single "Post to PR" action. The system creates one review on that pull
request: every finding that has a resolvable file and line becomes an inline comment
anchored to that line, and the review carries an overall summary. The reviewer is
shown a confirmation with a link to the posted review on the pull request.

**Why this priority**: This is the core value of the feature — closing the loop
between AI analysis and the place where code review actually happens. Without it,
the feature delivers nothing. It is independently shippable as the MVP.

**Independent Test**: Run an AI review on a pull request that has at least one
finding with a file/line, trigger "Post to PR", and confirm that a single review
appears on the pull request with the expected inline comments and summary, and that
the app shows a link to it.

**Acceptance Scenarios**:

1. **Given** a completed AI review with findings that include file and line
   references, **When** the reviewer triggers "Post to PR", **Then** one review is
   created on that pull request with each such finding as an inline comment anchored
   to its file and line, plus an overall summary, and the reviewer receives a link
   to the posted review.
2. **Given** a completed AI review with no findings at all, **When** the reviewer
   triggers "Post to PR", **Then** the reviewer is told there is nothing to post and
   no empty review is created on the pull request.
3. **Given** a posted review already exists from a previous run, **When** the
   reviewer triggers "Post to PR" again, **Then** they are warned that this will add
   another review, and on confirmation a new separate review is created.

### User Story 2 - Findings that can't be anchored still reach the PR (Priority: P2)

Some findings come back without a usable file or line (for example a repository-wide
observation, or a location the model could not pin down). The reviewer still wants
those points to appear on the pull request rather than be silently dropped, so when
they post, any finding that cannot be anchored to a line is collected into the
review's overall summary instead.

**Why this priority**: Ensures the posted review faithfully represents the full
analysis. Valuable, but the feature is still useful without it (P1 already covers the
anchored findings), so it ranks second.

**Independent Test**: Run an AI review that yields at least one finding without a
file/line, post to the PR, and confirm that finding appears in the review's summary
body while the locatable findings appear as inline comments — with nothing missing.

**Acceptance Scenarios**:

1. **Given** a completed AI review containing both anchored and non-anchored
   findings, **When** the reviewer posts to the PR, **Then** anchored findings appear
   as inline comments and non-anchored findings are included in the review summary.
2. **Given** a completed AI review where every finding lacks a file/line, **When**
   the reviewer posts to the PR, **Then** a review is still created with all findings
   captured in the summary and no inline comments.

### User Story 3 - Safe, transparent failures (Priority: P3)

When posting cannot succeed — the repository or access is not configured, the access
in use does not allow writing to the pull request, the pull request is closed, or the
external service is unreachable — the reviewer is told clearly why, and the pull
request is not left with a partial or confusing half-posted review. The existing
view-only review experience continues to work exactly as before.

**Why this priority**: Protects trust and avoids messing up the pull request, but
only matters once posting (P1) exists. It is a hardening layer on top of the core
flow.

**Independent Test**: Attempt to post with write access unavailable (or the external
service made unreachable) and confirm the reviewer sees a clear, actionable reason,
no partial review is left on the pull request, and the displayed findings are
unaffected.

**Acceptance Scenarios**:

1. **Given** no repository or no write-capable access is configured, **When** the
   reviewer triggers "Post to PR", **Then** the action posts nothing and returns a
   clear message explaining what is missing.
2. **Given** posting has started but a comment is rejected by the external service,
   **When** the failure occurs, **Then** the reviewer is shown an error and no
   stranded, unsubmitted review is left on the pull request where this can be
   avoided.
3. **Given** any posting attempt, **When** it fails for any reason, **Then** the
   findings already shown in the app remain visible and unchanged.

### Edge Cases

- **Closed or merged pull request**: posting is rejected with a clear message rather
  than failing obscurely.
- **A finding references a file or line not present in the pull request's diff**:
  that finding cannot be anchored, so it is folded into the summary rather than
  causing the whole post to fail.
- **Empty findings list**: the reviewer is told there is nothing to post; no review
  is created.
- **Re-posting**: each post produces a separate review; the reviewer is warned
  before adding another so duplicates are intentional, not accidental.
- **Branch-only review**: the existing branch (non-PR) review remains display-only;
  there is nothing to post inline because there is no pull request to anchor to.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST let a reviewer, in a single explicit action, post the
  findings of a completed AI code review onto the corresponding pull request as one
  review.
- **FR-002**: Each finding that has a resolvable file and line MUST be posted as an
  inline comment anchored to that file and line on the new state of the changed code.
- **FR-003**: Each inline comment MUST present the finding's severity, category,
  title, description, and recommended fix in a human-readable form.
- **FR-004**: Findings that lack a resolvable file or line MUST be included in the
  review's overall summary so that no finding is silently dropped.
- **FR-005**: The posted review MUST use a neutral, non-blocking verdict that does
  not by itself approve or request changes on the pull request.
- **FR-006**: Posting MUST require a configured repository and write-capable access;
  when these are absent, the system MUST post nothing and return a clear explanation.
- **FR-007**: The posting action MUST apply only to pull requests; reviews of a
  branch that is not associated with a pull request remain display-only.
- **FR-008**: When there are no findings to post, the system MUST inform the reviewer
  and MUST NOT create an empty review on the pull request.
- **FR-009**: Re-posting the same review MUST create a new separate review, and the
  reviewer MUST be warned before an additional review is created; the system does not
  track or deduplicate previously posted reviews.
- **FR-010**: If posting fails partway, the system MUST surface a clear error and MUST
  avoid leaving a stranded, unsubmitted review on the pull request wherever this is
  within its control.
- **FR-011**: On success, the system MUST return a reference (link) to the created
  review on the pull request.
- **FR-012**: A posting attempt — successful or failed — MUST NOT alter or remove the
  findings already displayed in the app; the existing view-only review experience is
  unchanged.

### Key Entities *(include if feature involves data)*

- **Posted PR Review**: A transient record of one posting attempt — the target pull
  request, the resulting review link, how many findings were posted as inline
  comments, how many were folded into the summary, and the verdict used. Not
  persisted between runs.
- **Code Review Finding**: The existing unit of AI feedback (severity, category,
  title, description, recommended fix, and optional file and line). Reused unchanged
  as the source of both inline comments and summary entries.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer can turn a completed AI review into a posted pull-request
  review in a single action, without leaving the app or manually copying any finding.
- **SC-002**: Every finding produced by the AI review is represented on the pull
  request after posting — inline when it can be located, in the summary otherwise —
  with zero findings silently lost.
- **SC-003**: Whenever posting cannot succeed, the reviewer is shown an actionable
  reason 100% of the time, and the pull request is left without a partial review.
- **SC-004**: For reviewers who do not post, the displayed review behaves exactly as
  it did before this feature existed (no change in the view-only experience).

## Assumptions

- The existing repository and access configuration used by the current code-review
  feature is reused; no new configuration concept is introduced.
- A single repository is configured at a time, consistent with the current feature.
- The access in use can be granted permission to write reviews and comments on pull
  requests; if it cannot, posting is expected to fail with a clear message (FR-006).
- The posted review verdict is always neutral (commentary only); mapping severity to
  an approve/request-changes verdict is out of scope.
- Posted reviews are not persisted or tracked on the server; duplicate prevention is
  limited to a pre-post warning in the app (FR-009).
- Scope is limited to pull requests; branch-only reviews remain display-only.
