# Phase 0 Research: Inline PR Review Comments

All Technical Context items were resolvable from the existing codebase and the
github-mcp-server tool docs; there are no open `NEEDS CLARIFICATION` markers. The
decisions below record how the feature reuses existing plumbing.

## Decision 1 — GitHub review-write flow (3 MCP calls)

**Decision**: Post findings as a single PR review using the github-mcp-server
`pull_requests` toolset in three steps, all through the existing
`backend/mcp/client.py:call_github_tool(tool_name, arguments)`:

1. `pull_request_review_write` — `{method: "create", owner, repo, pullNumber, commitID?}`
   → starts a pending review on the PR.
2. `add_comment_to_pending_review` — once per anchored finding —
   `{owner, repo, pullNumber, path, line, body, subjectType: "line", side: "RIGHT"}`
   → attaches an inline comment to the new state of the diff.
3. `pull_request_review_write` — `{method: "submit", owner, repo, pullNumber,
   event: "COMMENT", body}` → submits the review with the summary as its body.

**Rationale**: These exact tool names and argument shapes are documented in
`tools/github-mcp-server/README.md` (lines 1063–1074 for
`add_comment_to_pending_review`, 1137–1146 for `pull_request_review_write`). The
server is launched without `--read-only` (default `github_mcp_command =
"github-mcp-server stdio"` in `backend/config.py`), and the `pull_requests` toolset
is enabled by default, so no config change is required. `side: "RIGHT"` anchors to
the post-change code, which is what review feedback targets.

**Alternatives considered**:
- A single "create-and-submit with comments" call — not exposed as one tool by this
  server version; the pending-review workflow is the supported path.
- `add_reply_to_pull_request_comment` / issue comments — wrong granularity; they
  don't anchor to a diff line.

## Decision 2 — Post what the user sees (findings supplied in the request)

**Decision**: The new endpoint accepts the already-computed review (its `summary`
and `findings`) in the request body and posts that, rather than re-running the LLM
review server-side.

**Rationale**: The confirmed UX is "run the review, inspect findings, then click
Post" — posting must reflect exactly what the reviewer approved (spec FR-001/SC-002).
Re-running the LLM would be non-deterministic, slower, and could post different text
than was shown. The client already holds the `CodeReviewResult` from the existing
`GET .../review` call, so it simply hands it back.

**Alternatives considered**:
- Re-run `review_pull_request(number)` inside the post endpoint — rejected:
  non-deterministic and a wasted second LLM call; breaks "post what you see".

## Decision 3 — Reuse `CodeReviewResult` as the request body (no new request model)

**Decision**: The POST endpoint's request body is the existing
`CodeReviewResult` schema (`summary` + `findings[]`); only the response gets a new
model, `PostedReviewResult`.

**Rationale**: Constitution Principle II (YAGNI) — `CodeReviewResult` already carries
exactly `summary` and `findings`, which is all posting needs. Introducing a
near-identical `PostReviewRequest` would be a speculative duplicate. The extra
`repo`/`target`/`error` fields on `CodeReviewResult` are simply ignored on input.

**Alternatives considered**:
- A dedicated `PostReviewRequest {summary, findings}` — rejected as premature
  duplication for a single use site.

## Decision 4 — Summary folding for non-anchorable findings

**Decision**: Findings lacking a usable `file` or `line` (or whose `line` is not in
the PR diff) are not sent as inline comments; instead they are appended to the
submitted review's `body` under a clearly labeled section, alongside the AI summary.

**Rationale**: Satisfies spec FR-004 / US2 — every finding reaches the PR, with zero
silent drops — without risking a rejected inline comment for an off-diff line.

**Alternatives considered**:
- Dropping non-anchorable findings — rejected: violates SC-002.
- Posting them as general (non-review) PR comments via a separate call — rejected:
  fragments the feedback across two surfaces; the review body keeps it cohesive.

## Decision 5 — Partial-failure handling (pending-review cleanup)

**Decision**: If a step fails after the pending review is created (e.g. an
`add_comment_to_pending_review` call is rejected for an invalid line, or submit
fails), the service attempts `pull_request_review_write` with `{method: "delete"}`
to remove the stranded pending review, then returns a `PostedReviewResult` with a
clear `error` and `posted = false`.

**Rationale**: Satisfies spec FR-010 / US3 — avoid leaving a confusing half-posted
review on the PR. Aligns with Constitution Principle VI (no silent swallowing; errors
surfaced with context). A best-effort delete is acceptable because the only state
created so far is the pending (unsubmitted) review.

**Alternatives considered**:
- Submitting whatever comments succeeded — rejected: produces an incomplete review
  that misrepresents the analysis and is hard for the user to reason about.
- Skipping individual rejected comments and continuing — partially adopted: a single
  comment that GitHub rejects for an out-of-diff line is pre-empted by Decision 4
  (we only inline-post findings we believe are anchorable); genuine API failures
  trigger the cleanup path above.

## Decision 6 — Capture the posted review's link

**Decision**: Read the review URL (e.g. `html_url`) from the `submit` response and
return it as `review_url`; if absent, fall back to the pull request URL.

**Rationale**: Satisfies spec FR-011 / SC-001 — the reviewer gets a direct link to
what they just posted.

**Alternatives considered**:
- Returning no link — rejected: weakens the "one action, done" outcome.

## Decision 7 — Configuration & guards (reused)

**Decision**: Reuse `settings.github_repo`, `settings.github_token`, and
`settings.github_mcp_command` from `backend/config.py`. Posting is refused (no MCP
calls) when `github_repo` is unparseable/absent or `github_token` is empty, mirroring
the guards already in `review_pull_request`.

**Rationale**: Constitution Principle V — no new configuration concept; reuse the
single source of truth. Satisfies spec FR-006.

**Alternatives considered**: none — adding a separate write-token setting was
considered and rejected (the same PAT with `repo` scope already covers read+write).

## Decision 8 — Frontend trigger

**Decision**: In `frontend/app.js`, the existing review result panel gains a "Post to
PR" button (PR reviews only, not branch reviews). Clicking it shows a confirmation
(always, since re-posting creates a new review — spec FR-009), then calls the new
endpoint with the displayed `CodeReviewResult` and renders the returned link / counts
/ errors. Styling reuses existing CSS custom properties in `style.css`; the button
listener is attached via `addEventListener` (no inline `onclick`).

**Rationale**: Matches the confirmed explicit-trigger decision and the constitution's
frontend constraints. Branch reviews stay display-only (spec FR-007).
