# Data Model: Inline PR Review Comments

This feature introduces **no persisted entities** — nothing is written to Postgres.
It adds one new API response DTO and reuses two existing DTOs. All models live in
`backend/models/schemas.py` (Pydantic v2).

## CodeReviewFinding (existing — reused unchanged)

The source unit of feedback, already produced by the AI review. Reused as-is for
both inline comments and summary entries.

| Field | Type | Notes |
|---|---|---|
| `severity` | str | `critical \| high \| medium \| low \| info` |
| `category` | str | `security \| sql_injection \| bug \| code_quality \| performance \| style \| suggestion` |
| `file` | str \| null | Relative path; **required for an inline comment** |
| `line` | int \| null | Diff line; **required for an inline comment** |
| `title` | str | |
| `description` | str | |
| `recommendation` | str \| null | |

**Anchorable** = `file` is non-empty AND `line` is a positive int. Anchorable
findings become inline comments; the rest are folded into the review summary body.

## CodeReviewResult (existing — reused as the request body)

Already returned by `GET /api/github/pull-requests/{number}/review`. The post
endpoint accepts this same shape as its request body (only `summary` and `findings`
are used; `repo`/`target`/`error` are ignored on input). See research.md Decision 3.

| Field | Type | Used on input? |
|---|---|---|
| `repo` | str | ignored |
| `target` | str | ignored |
| `summary` | str | yes — becomes the review body preamble |
| `findings` | list[CodeReviewFinding] | yes — partitioned into inline vs summary |
| `error` | str \| null | ignored |

## PostedReviewResult (NEW — response DTO)

New Pydantic model in `backend/models/schemas.py`, returned by the post endpoint and
declared as its `response_model`.

| Field | Type | Notes |
|---|---|---|
| `repo` | str | `owner/name` (echoed from config), or `""` when not configured |
| `target` | str | e.g. `PR #42` |
| `posted` | bool | `true` only when a review was successfully submitted |
| `review_url` | str \| null | Link to the created review (or PR), per research.md Decision 6 |
| `inline_comment_count` | int | Number of anchorable findings posted as inline comments |
| `summary_only_count` | int | Number of non-anchorable findings folded into the summary |
| `verdict` | str | Always `"COMMENT"` (spec FR-005) |
| `error` | str \| null | Human-readable reason when `posted = false`; `null` on success |

**Rules**:
- When `findings` is empty: `posted = false`, `error` explains there is nothing to
  post, and **no** MCP calls are made (spec FR-008).
- When repo/token are not configured: `posted = false`, `error` explains what's
  missing, no MCP calls (spec FR-006).
- On partial failure after the pending review was created: the pending review is
  best-effort deleted, `posted = false`, `error` describes the failure
  (spec FR-010, research.md Decision 5).
- `inline_comment_count + summary_only_count` equals the count of input findings on a
  successful post (zero silent drops — spec SC-002).

## Relationship to the existing review flow

```
GET  .../review            -> CodeReviewResult  (existing; display-only)
        │  (client holds the result on screen)
        ▼
POST .../review/comments   (body: CodeReviewResult)  -> PostedReviewResult  (NEW)
        │
        └─> MCP: create pending review → add inline comments → submit (COMMENT)
```

No state is shared between the two calls server-side; the client carries the review
result from the GET into the POST.
