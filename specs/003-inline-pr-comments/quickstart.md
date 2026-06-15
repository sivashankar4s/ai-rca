# Quickstart: Inline PR Review Comments

Validates the user stories in `spec.md` end-to-end. Builds on the existing AI Code
Review feature; requires a configured GitHub repository whose token can write reviews.

## Prerequisites

- Baseline app running (`uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000`).
- `GITHUB_REPO` (`owner/repo`), `GITHUB_TOKEN`, and `GITHUB_MCP_COMMAND` configured in
  `.env` (or the Configuration drawer). The `GITHUB_MCP_COMMAND` must **not** include
  `--read-only`. The token must carry the `repo` (write) scope.
- An **open** pull request in that repo with a code diff — ideally one that will
  produce at least one finding the AI can anchor to a file/line (e.g. a deliberately
  unparameterized SQL query).

## Validate User Story 1 — Post AI findings onto the PR (P1)

1. In the Source Code Intelligence area, list pull requests and run the AI review on
   your test PR (`GET /api/github/pull-requests/{number}/review`). Confirm findings
   appear in the UI as today.
2. Click **Post to PR** and confirm the warning dialog, then proceed.
3. **Expected**: The app shows success with a `review_url`, `inline_comment_count`,
   and `summary_only_count`. On GitHub, the PR now has **one** review whose inline
   comments are anchored to the expected file/line and whose body contains the AI
   summary (FR-001–FR-003, FR-011).
4. Open the returned `review_url` and confirm each inline comment shows the finding's
   severity, category, title, description, and recommendation.

## Validate User Story 2 — Non-anchorable findings still reach the PR (P2)

1. Use (or craft) a PR whose AI review yields at least one finding with no
   `file`/`line` (a repo-wide observation).
2. Run the review, then **Post to PR**.
3. **Expected**: Anchorable findings appear as inline comments; the non-anchorable
   finding appears in the submitted review's summary body. `inline_comment_count +
   summary_only_count` equals the total number of findings — nothing is dropped
   (FR-004, SC-002).

## Validate User Story 3 — Safe, transparent failures (P3)

1. **No write access**: temporarily use a token without `repo` write scope (or unset
   `GITHUB_TOKEN`) and click **Post to PR**.
   **Expected**: HTTP 200 with `posted = false` and an `error` explaining what's
   missing; nothing is created on the PR; the displayed findings are unchanged
   (FR-006, FR-012).
2. **Closed PR**: run a review on a closed/merged PR and attempt to post.
   **Expected**: `posted = false` with a clear error; no partial review left on the
   PR (FR-010, edge case).
3. **MCP unreachable**: set an invalid `GITHUB_MCP_COMMAND` and post.
   **Expected**: `posted = false` with an error; any pending review created mid-flow
   is not left stranded (FR-010).

## Validate edge cases

- **Empty findings**: run a review that yields zero findings (or post a result with an
  empty `findings` array) and click **Post to PR**.
  **Expected**: the app reports there is nothing to post; **no** empty review is
  created on the PR (FR-008).
- **Re-posting**: post once, then post again.
  **Expected**: a confirmation warns that another review will be added; on confirm, a
  second separate review appears on the PR (FR-009).
- **Branch review**: open a branch (non-PR) review.
  **Expected**: no "Post to PR" action is offered; it remains display-only (FR-007).

## Run automated tests

```bash
pytest --cov=backend --cov-fail-under=80
ruff format --check .
ruff check .
```

Coverage targets for the changed code: `services/` ≥85% (the post flow in
`code_review_service.py`), `routers/` ≥75% (the new endpoint).
