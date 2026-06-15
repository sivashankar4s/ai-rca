# Phase 0 Research: Auto-Link RCA Cases to GitHub Pull Requests

## PR matching strategy

- **Decision**: Fetch open and recently-closed/merged pull requests once per
  `/api/analyze` call via the existing
  `backend/services/github_service.list_pull_requests()` (which itself wraps
  `mcp.client.call_github_tool("list_pull_requests", ...)`), then score each
  PR against each failure group using simple text matching: does the PR's
  branch name (`head.ref`), title, or body contain the failure group's
  `component` name or `error_pattern`/error code (case-insensitive substring
  match)? The highest-scoring PR per failure group (ties broken by most
  recently updated) is selected as the candidate, if its score is above zero.
- **Rationale**: Reuses existing, already-tested GitHub MCP plumbing; a single
  list call avoids N MCP round-trips (one per failure group), keeping
  `/api/analyze` within its existing latency budget (Constraint: Performance
  Goals). Simple substring scoring is transparent, debuggable, and matches the
  "best-effort, user-verifies" framing in spec Assumptions — avoids building an
  ML/embedding-based matcher that the spec explicitly does not require.
- **Alternatives considered**:
  - Per-failure-group `search_issues`/`search_pull_requests` MCP calls —
    rejected: N calls per analysis risk rate limits and latency; a single
    `list_pull_requests` (already paginated to 20, `state="open"` plus a
    second call for recently merged/closed) is sufficient for the
    "best-effort" framing.
  - Embedding-based semantic similarity between failure description and PR
    text — rejected as premature complexity (Constitution Principle II); no
    existing embedding pipeline in this codebase, and the spec does not
    require guaranteed-correct matches.

## Persisting the linked PR

- **Decision**: Add a single nullable `linked_pr` JSONB column to `rca_cases`
  (Alembic migration), storing `{number, title, author, state, url, branch,
  updated_at}`. A new `CaseActivity` row with `activity_type="pr_linked"` (or
  `"pr_updated"`) is appended whenever this column changes.
- **Rationale**: Matches the existing pattern of storing structured,
  non-relational detail as JSONB on `rca_cases` (e.g. `affected_files`); a
  single PR reference per case is all the spec requires (FR-003: "at most one
  related pull request per failure group" → one per case). Avoids a new table
  for a 1:0..1 relationship.
- **Alternatives considered**: New `linked_pull_requests` table with a FK to
  `rca_cases` — rejected as premature (Constitution Principle II): only ever
  one row per case today, and `case_signature_links`-style M:N is not needed
  since cross-repo / multi-PR linking is explicitly out of scope.

## Update vs. retain logic (User Story 3)

- **Decision**: On each analysis, if `pr_link_service` finds a candidate for a
  failure group whose case already has a `linked_pr`, replace `linked_pr` only
  if the new candidate's score is strictly greater than the persisted one's
  (recomputed using the same scoring against the current failure group); if no
  candidate is found this run, leave the existing `linked_pr` untouched
  (FR-008).
- **Rationale**: Directly implements the acceptance criteria of User Story 3
  without needing to store historical scores — recompute-on-write is cheap
  given the single `list_pull_requests` call already made.
- **Alternatives considered**: Always overwrite with the latest run's result
  (including `null`) — rejected because it would violate FR-008's "retain the
  existing reference when a later analysis finds no candidate."

## Stale/deleted PR handling (FR-010)

- **Decision**: When rendering a case's persisted `linked_pr`, no live
  re-fetch is performed on read (avoids an MCP call on every page view); the
  PR reference is refreshed/validated only as part of the next
  `/api/analyze` run, where `pr_link_service` re-resolves the PR by number via
  the same `list_pull_requests` result set. If the previously-linked PR number
  is no longer present in that result set (e.g. deleted/inaccessible) **and**
  no replacement candidate is found, `linked_pr` is cleared.
- **Rationale**: Keeps the read path (`GET` of case data) free of external
  calls, consistent with FR-005/Constraint (no added latency outside
  `/api/analyze`). "No longer present in the list" is a reasonable, low-cost
  staleness signal without a dedicated per-PR existence check.
- **Alternatives considered**: A background job to periodically re-validate
  linked PRs — rejected as out of scope/premature for this feature; no
  existing background-job infrastructure in the codebase.

## Frontend presentation

- **Decision**: Render a small "Related Pull Request" badge within each
  failure-group card in `frontend/app.js`/`style.css`, showing PR title (as a
  link), author, and a status pill (`open` / `merged` / `closed`) with
  distinct colors, placed near the existing log deep-link.
- **Rationale**: Mirrors the existing "Related Code Changes" card pattern
  already in the frontend for `code_analysis`; reuses existing dark-theme CSS
  custom properties per Constitution's frontend constraints.
- **Alternatives considered**: A separate page/section listing all linked
  PRs across cases — deferred; out of scope for this feature, which is
  per-failure-group/per-case.
