# API Contracts: Inline PR Review Comments

One new endpoint is added to the existing GitHub router
(`backend/routers/github.py`). The existing `GET .../review` endpoints are
unchanged. No endpoints are removed.

## `POST /api/github/pull-requests/{number}/review/comments` (NEW)

Posts the findings of a completed AI review onto pull request `{number}` as one
native GitHub review (inline comments + summary). Satisfies FR-001–FR-012.

**Path parameter**:
- `number` (int) — the pull request number.

**Request body** (`CodeReviewResult` — the result the client already holds from
`GET .../review`; only `summary` and `findings` are read):

```json
{
  "repo": "owner/repo",
  "target": "PR #42",
  "summary": "Two security issues and one code-quality nit. Overall medium risk.",
  "findings": [
    {
      "severity": "high",
      "category": "sql_injection",
      "file": "app/db.py",
      "line": 42,
      "title": "Unparameterized SQL query",
      "description": "User input is concatenated directly into the query string.",
      "recommendation": "Use a parameterized query / bound parameters."
    },
    {
      "severity": "low",
      "category": "code_quality",
      "file": null,
      "line": null,
      "title": "Repo-wide: inconsistent logging",
      "description": "Some modules use print() instead of the logging module.",
      "recommendation": "Standardize on logging.getLogger(__name__)."
    }
  ]
}
```

**Response** (`PostedReviewResult`) — success example (HTTP 200):

```json
{
  "repo": "owner/repo",
  "target": "PR #42",
  "posted": true,
  "review_url": "https://github.com/owner/repo/pull/42#pullrequestreview-123456789",
  "inline_comment_count": 1,
  "summary_only_count": 1,
  "verdict": "COMMENT",
  "error": null
}
```

**Behavioral contract**:

- One submitted review is created on the PR with `event = COMMENT` (never
  approves/blocks — FR-005).
- Each finding with a resolvable `file` + `line` is posted as an inline comment
  anchored to the new side of the diff (FR-002); its comment body renders severity,
  category, title, description, and recommendation (FR-003).
- Findings without a resolvable `file`/`line` are included in the review summary body
  (FR-004); `inline_comment_count + summary_only_count` == number of input findings
  (SC-002).
- `review_url` links to the created review (FR-011).

**Degradation / error contract** (all return HTTP 200 with `posted = false` and a
populated `error`, mirroring the existing `CodeReviewResult.error` pattern):

- `findings` empty → no MCP calls, `error` = "nothing to post" (FR-008).
- `GITHUB_REPO` not configured or `GITHUB_TOKEN` missing → no MCP calls, `error`
  explains what's missing (FR-006).
- The PR is closed/merged, the token lacks write scope, or the MCP server is
  unreachable → `posted = false`, `error` describes the failure; any pending review
  created mid-flow is best-effort deleted so the PR is not left with a stranded
  review (FR-010).
- A posting attempt never alters the `GET .../review` response or the findings shown
  in the app (FR-012).

**Scope**: Applies to pull requests only. There is no equivalent post action for
branch reviews — `GET /api/github/branches/review` remains display-only (FR-007).

## Unchanged endpoints (for reference)

- `GET /api/github/pull-requests/{number}/review` → `CodeReviewResult` (display-only;
  produces the body the POST consumes).
- `GET /api/github/branches/review` → `CodeReviewResult` (display-only; out of scope).
- `GET /api/github/repo`, `GET /api/github/branches`, `GET /api/github/pull-requests`
  — unchanged.
