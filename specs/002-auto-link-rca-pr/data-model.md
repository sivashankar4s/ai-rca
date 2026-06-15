# Data Model: Auto-Link RCA Cases to GitHub Pull Requests

This feature adds one persisted field, one new activity type, and two API DTO
additions to the baseline data model (`specs/001-ai-rca-tool/data-model.md`).
No new tables are introduced.

## RcaCase (modified)

Adds one column to the existing `rca_cases` table (`backend/db/models.py`):

| Field | Type | Notes |
|---|---|---|
| `linked_pr` | JSONB \| null | **NEW**. Structure: `{number: int, title: str, author: str \| null, state: "open"\|"merged"\|"closed", url: str, branch: str \| null, updated_at: str \| null}`. `null` when no pull request has ever been linked, or when the previously linked PR is no longer resolvable (FR-010). |

**Validation / rules**:
- Set the first time `pr_link_service` finds a candidate PR for a failure
  group linked to this case (FR-007).
- Updated only when a later analysis finds a strictly stronger-scoring
  candidate for the same case (FR-008); otherwise retained as-is.
- Cleared (`null`) if the previously linked PR number is absent from the
  current `list_pull_requests` result and no replacement candidate is found
  (FR-010).

## Case Activity (new activity_type values)

Existing `case_activity` table (`backend/db/models.py`) gains new
`activity_type` values, written via `repositories/case_repo.py`:

| `activity_type` | `payload` shape | Written when |
|---|---|---|
| `pr_linked` | `{number, title, url, state}` | `linked_pr` is set for the first time on a case (FR-009) |
| `pr_updated` | `{previous: {number, ...}, current: {number, ...}}` | `linked_pr` is replaced with a stronger match (FR-008/FR-009) |
| `pr_unlinked` | `{previous: {number, ...}}` | `linked_pr` is cleared because it's no longer resolvable (FR-010) |

## LinkedPullRequest (new API DTO)

New Pydantic model in `backend/models/schemas.py`, mirroring the persisted
`linked_pr` JSON shape:

| Field | Type | Notes |
|---|---|---|
| `number` | int | PR number |
| `title` | str | |
| `author` | str \| null | |
| `state` | `"open" \| "merged" \| "closed"` | Derived from the GitHub PR's `state` + `merged_at` (merged if `merged_at` is set, else `state`) |
| `url` | str | `html_url` |
| `branch` | str \| null | `head.ref` |
| `updated_at` | str \| null | ISO timestamp |

## Failure Group (modified, API DTO)

`FailureGroup` in `backend/models/schemas.py` gains:

| Field | Type | Notes |
|---|---|---|
| `linked_pull_request` | `LinkedPullRequest \| null` | **NEW**. Present only when `pr_link_service` found a candidate above the relevance threshold for this group (FR-003, FR-004); `null`/absent otherwise (FR-002, FR-005, FR-006). |

## AnalyzeResponse

No structural change — `failure_groups[].linked_pull_request` is additive and
backward compatible; existing consumers that ignore unknown fields are
unaffected.
