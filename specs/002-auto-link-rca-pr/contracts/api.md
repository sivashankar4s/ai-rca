# API Contracts: Auto-Link RCA Cases to GitHub Pull Requests

This feature extends the existing `POST /api/analyze` contract
(`specs/001-ai-rca-tool/contracts/api.md`). No new endpoints are added.

## `POST /api/analyze` (extended)

Satisfies FR-001–FR-010.

**Request**: unchanged (`AnalyzeRequest`).

**Response** (`AnalyzeResponse`): each entry in `failure_groups` MAY now
include `linked_pull_request`:

```json
{
  "failure_groups": [
    {
      "group_id": "grp-1",
      "component": "dp-lz-s3-event-processor",
      "error_pattern": "S3_PUT_FAILED on lz-processor stage",
      "root_cause": "...",
      "failure_category": "Configuration",
      "impact_count": 10,
      "cw_log_url": "https://...",
      "records": ["..."],
      "log_samples": ["..."],
      "linked_pull_request": {
        "number": 42,
        "title": "Fix S3 PutObject permission for lz-processor",
        "author": "octocat",
        "state": "open",
        "url": "https://github.com/owner/repo/pull/42",
        "branch": "fix/lz-processor-s3-put",
        "updated_at": "2026-06-14T09:00:00Z"
      }
    }
  ]
}
```

**Behavioral contract**:

- `linked_pull_request` is **absent/null** when:
  - `GITHUB_REPO` is not configured (FR-006), or
  - the PR search fails/times out (FR-005), or
  - no candidate PR scores above the relevance threshold for this group
    (FR-002, acceptance scenario 2).
- `linked_pull_request.state` is one of `"open"`, `"merged"`, `"closed"`
  (FR-004, User Story 2).
- A PR search failure MUST NOT change the HTTP status or omit
  `failure_groups`/`summary`/`code_analysis` — identical contract to the
  existing `code_analysis` degradation behavior (spec 001 FR-016).

## Persistence contract (`rca_cases`)

Not a public API, but documented for downstream consumers of the CRM tables
(spec 001 `data-model.md`):

- `rca_cases.linked_pr` (JSONB \| null) reflects the most recently
  selected `linked_pull_request` for that case, per
  `specs/002-auto-link-rca-pr/data-model.md`.
- `case_activity` rows with `activity_type` in
  `{"pr_linked", "pr_updated", "pr_unlinked"}` record changes to
  `rca_cases.linked_pr` (FR-009).
